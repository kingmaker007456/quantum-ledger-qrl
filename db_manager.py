# db_manager.py
import sqlite3
import json
import threading
from typing import List, Optional, Tuple
from config import DB_NAME, WALLET_DB_NAME, UTXO_DB_NAME
from logger import logger

# --- UTXO CLASS ---
class UTXO:
    def __init__(self, txid, output_index, address, amount, spent_txid=None, spent_index=None):
        self.txid = txid
        self.output_index = output_index
        self.address = address
        self.amount = amount
        self.spent_txid = spent_txid
        self.spent_index = spent_index

    def is_spent(self):
        return self.spent_txid is not None

    def to_tuple(self):
        return (self.txid, self.output_index, self.address, self.amount, self.spent_txid, self.spent_index)

    @classmethod
    def from_tuple(cls, row):
        return cls(row[0], row[1], row[2], row[3], row[4], row[5])

# --- BASE DATABASE MANAGER ---

class BaseDBManager:
    def __init__(self, db_name):
        self.db_name = db_name
        self.conn = None
        self.lock = threading.Lock()
        self.connect()

    def connect(self):
        try:
            # check_same_thread=False is needed for Flask + Background threads
            self.conn = sqlite3.connect(self.db_name, check_same_thread=False, timeout=20)
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            logger.critical(f"Database connection error for {self.db_name}: {e}")
            raise

    def execute_query(self, query: str, params: tuple = (), fetch_one=False, fetch_all=False, commit=False):
        """Thread-safe query execution helper."""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(query, params)
                
                result = None
                if fetch_one:
                    result = cursor.fetchone()
                elif fetch_all:
                    result = cursor.fetchall()
                
                if commit:
                    self.conn.commit()
                
                return result
            except sqlite3.Error as e:
                logger.error(f"DB Error in {self.db_name}: {e} | Query: {query}")
                return None

    def close(self):
        if self.conn:
            self.conn.close()

# --- LEDGER DB MANAGER ---

class LedgerDBManager(BaseDBManager):
    def __init__(self):
        super().__init__(DB_NAME)
        self._setup_tables()

    def _setup_tables(self):
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS blocks (
                index_id INTEGER PRIMARY KEY,
                timestamp REAL NOT NULL,
                previous_hash TEXT NOT NULL,
                merkle_root TEXT NOT NULL,
                proof INTEGER NOT NULL,
                hash TEXT UNIQUE NOT NULL,
                transactions_json TEXT NOT NULL
            )
        """, commit=True)
        
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS peers (
                address TEXT PRIMARY KEY,
                last_seen REAL NOT NULL,
                reputation INTEGER DEFAULT 10
            )
        """, commit=True)

    def save_block(self, block) -> bool:
        tx_json = json.dumps([tx.to_dict(include_signature=True) for tx in block.transactions])
        query = """INSERT INTO blocks VALUES (?, ?, ?, ?, ?, ?, ?)"""
        params = (block.index, block.timestamp, block.previous_hash, block.merkle_root, block.proof, block.hash, tx_json)
        
        try:
            with self.lock:
                self.conn.execute(query, params)
                self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Block {block.index} already exists.")
            return False

    def load_last_block_row(self):
        return self.execute_query("SELECT * FROM blocks ORDER BY index_id DESC LIMIT 1", fetch_one=True)

    def load_all_blocks(self):
        return self.execute_query("SELECT * FROM blocks ORDER BY index_id ASC", fetch_all=True) or []
    
    def clear_blocks(self):
        self.execute_query("DELETE FROM blocks", commit=True)

    # Peer Management
    def save_peer(self, address):
        import time
        t = time.time()
        self.execute_query("""
            INSERT INTO peers (address, last_seen) VALUES (?, ?) 
            ON CONFLICT(address) DO UPDATE SET last_seen = ?
        """, (address, t, t), commit=True)

    def load_all_peers(self):
        rows = self.execute_query("SELECT address FROM peers", fetch_all=True)
        return [row[0] for row in rows] if rows else []

# --- UTXO DB MANAGER ---

class UTXODBManager(BaseDBManager):
    def __init__(self):
        super().__init__(UTXO_DB_NAME)
        self._setup_tables()

    def _setup_tables(self):
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS utxos (
                txid TEXT NOT NULL,
                output_index INTEGER NOT NULL,
                address TEXT NOT NULL,
                amount REAL NOT NULL,
                spent_txid TEXT,
                spent_index INTEGER,
                PRIMARY KEY (txid, output_index)
            )
        """, commit=True)

    def add_utxos(self, utxos_list: List[UTXO]):
        data = [u.to_tuple()[:4] for u in utxos_list] # Only insert unspent info
        with self.lock:
            self.conn.executemany("""
                INSERT OR IGNORE INTO utxos (txid, output_index, address, amount) 
                VALUES (?, ?, ?, ?)
            """, data)
            self.conn.commit()

    def mark_spent(self, input_txid, input_index, spent_txid, spent_index):
        with self.lock:
            cur = self.conn.execute("""
                UPDATE utxos SET spent_txid = ?, spent_index = ? 
                WHERE txid = ? AND output_index = ? AND spent_txid IS NULL
            """, (spent_txid, spent_index, input_txid, input_index))
            self.conn.commit()
            return cur.rowcount > 0

    def get_unspent_outputs(self, address=None):
        query = "SELECT * FROM utxos WHERE spent_txid IS NULL"
        params = ()
        if address:
            query += " AND address = ?"
            params = (address,)
        
        rows = self.execute_query(query, params, fetch_all=True)
        return [UTXO.from_tuple(row) for row in rows] if rows else []

    def get_utxo_by_id(self, txid, output_index):
        row = self.execute_query(
            "SELECT * FROM utxos WHERE txid = ? AND output_index = ?", 
            (txid, output_index), fetch_one=True
        )
        return UTXO.from_tuple(row) if row else None

    def clear_all(self):
        self.execute_query("DELETE FROM utxos", commit=True)

# --- WALLET DB MANAGER ---

class WalletDBManager(BaseDBManager):
    def __init__(self):
        super().__init__(WALLET_DB_NAME)
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS wallets (
                public_key TEXT PRIMARY KEY,
                private_key TEXT NOT NULL,
                alias TEXT UNIQUE
            )
        """, commit=True)

    def save_wallet(self, public_key, private_key, alias):
        try:
            self.execute_query("INSERT INTO wallets VALUES (?, ?, ?)", 
                               (public_key, private_key, alias), commit=True)
            return True
        except sqlite3.IntegrityError:
            return False

    def get_private_key(self, public_key=None, alias=None):
        if public_key:
            row = self.execute_query("SELECT private_key FROM wallets WHERE public_key = ?", (public_key,), fetch_one=True)
        elif alias:
            row = self.execute_query("SELECT private_key FROM wallets WHERE alias = ?", (alias,), fetch_one=True)
        else:
            return None
        return row[0] if row else None

    def get_all_wallets(self):
        return self.execute_query("SELECT public_key, alias FROM wallets", fetch_all=True) or []
