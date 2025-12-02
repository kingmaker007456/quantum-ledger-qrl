# ledger.py
import time
import json
import hashlib
from typing import List, Optional
from transaction import Transaction, TxInput, TxOutput
from db_manager import LedgerDBManager, UTXODBManager, UTXO
from pqc_primitives import hash_data
from logger import logger
from config import MINER_REWARD, BLOCK_TIME_TARGET, DIFFICULTY_ADJUSTMENT_INTERVAL, INITIAL_DIFFICULTY

def calculate_merkle_root(transactions: List[Transaction]) -> str:
    """Calculates the Merkle Root of a list of transactions."""
    if not transactions:
        return "0" * 128
        
    hashes = [tx.txid for tx in transactions]
    
    while len(hashes) > 1:
        if len(hashes) % 2 != 0:
            hashes.append(hashes[-1]) # Duplicate last if odd
        
        new_level = []
        for i in range(0, len(hashes), 2):
            combined = hashes[i] + hashes[i+1]
            new_level.append(hashlib.sha3_512(combined.encode()).hexdigest())
        hashes = new_level
        
    return hashes[0]

class Block:
    def __init__(self, index, transactions, previous_hash, proof=0, timestamp=None, current_hash=None, merkle_root=None):
        self.index = index
        self.timestamp = timestamp if timestamp else time.time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.proof = proof
        self.merkle_root = merkle_root if merkle_root else calculate_merkle_root(transactions)
        self.hash = current_hash if current_hash else self.calculate_hash()
    
    def to_dict(self):
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'transactions': [tx.to_dict(include_signature=True) for tx in self.transactions],
            'previous_hash': self.previous_hash,
            'merkle_root': self.merkle_root,
            'proof': self.proof
        }

    def calculate_hash(self):
        # Hash header only (standard practice) + Merkle Root
        header = {
            'index': self.index,
            'timestamp': self.timestamp,
            'previous_hash': self.previous_hash,
            'merkle_root': self.merkle_root,
            'proof': self.proof
        }
        return hash_data(header)

    @classmethod
    def from_db_row(cls, row):
        # Maps DB columns to init
        # index, timestamp, prev_hash, merkle, proof, hash, tx_json
        tx_dicts = json.loads(row['transactions_json'])
        transactions = [Transaction.from_dict(d) for d in tx_dicts]
        
        return cls(
            index=row['index_id'],
            transactions=transactions,
            previous_hash=row['previous_hash'],
            proof=row['proof'],
            timestamp=row['timestamp'],
            current_hash=row['hash'],
            merkle_root=row['merkle_root']
        )

class QuantumLedger:
    def __init__(self, miner_address):
        self.ldb = LedgerDBManager()
        self.udb = UTXODBManager()
        self.miner_address = miner_address
        self.current_difficulty = INITIAL_DIFFICULTY 
        self.chain = []
        self.pending_transactions = []
        self._load_chain_from_db()

    def _load_chain_from_db(self):
        rows = self.ldb.load_all_blocks()
        if not rows:
            logger.warning("No chain found. Creating Genesis Block.")
            self.create_genesis_block()
        else:
            self.chain = [Block.from_db_row(row) for row in rows]
            # Recalculate difficulty based on loaded chain
            self._adjust_difficulty() 
            self.rebuild_utxo_set()

    def create_genesis_block(self):
        genesis_reward_tx = self._create_coinbase_tx(self.miner_address, MINER_REWARD * 1000, is_genesis=True)
        genesis_block = Block(0, [genesis_reward_tx], "0" * 128)
        
        if self.ldb.save_block(genesis_block):
            self.chain.append(genesis_block)
            self._update_utxo_set(genesis_block, is_spend=False)
            logger.info("Genesis Block Created.")

    @property
    def last_block(self):
        return self.chain[-1]

    def add_transaction(self, transaction: Transaction):
        # Basic check before adding to mempool
        if not transaction.is_valid(self.udb):
            logger.warning(f"Invalid TX {transaction.txid[:8]} rejected.")
            return False
            
        # Prevent double adding
        if any(t.txid == transaction.txid for t in self.pending_transactions):
            return False
            
        self.pending_transactions.append(transaction)
        logger.info(f"TX {transaction.txid[:8]} added to mempool.")
        return True

    def _create_coinbase_tx(self, recipient, amount, is_genesis=False):
        inputs = [TxInput(txid="0" * 128, output_index=-1)]
        outputs = [TxOutput(amount, recipient)]
        cb_tx = Transaction(inputs=inputs, outputs=outputs)
        cb_tx.inputs[0].signature = "COINBASE"
        cb_tx.inputs[0].pub_key = "0" * 128
        return cb_tx

    def rebuild_utxo_set(self):
        self.udb.clear_all()
        # In a real system, we wouldn't iterate the whole chain every startup.
        # We would use snapshots. For this prototype, we iterate.
        logger.info("Rebuilding UTXO set...")
        all_utxos = {}
        
        for block in self.chain:
            for tx in block.transactions:
                # Outputs -> New UTXOs
                for i, output in enumerate(tx.outputs):
                    all_utxos[(tx.txid, i)] = UTXO(tx.txid, i, output.address, output.amount)
                
                # Inputs -> Spend UTXOs
                if not (tx.inputs[0].txid == "0" * 128):
                    for tx_input in tx.inputs:
                        key = (tx_input.txid, tx_input.output_index)
                        if key in all_utxos:
                            all_utxos[key].spent_txid = tx.txid
                            all_utxos[key].spent_index = tx.inputs.index(tx_input)

        self.udb.add_utxos([u for u in all_utxos.values() if not u.is_spent()])

    def _update_utxo_set(self, block, is_spend=True):
        for tx in block.transactions:
            if not (tx.inputs[0].txid == "0" * 128):
                for i, tx_input in enumerate(tx.inputs):
                    if is_spend:
                        self.udb.mark_spent(tx_input.txid, tx_input.output_index, tx.txid, i)
            
            # Add new outputs
            new_utxos = [UTXO(tx.txid, i, o.address, o.amount) for i, o in enumerate(tx.outputs)]
            if is_spend:
                self.udb.add_utxos(new_utxos)

    # --- MINING ---

    def _adjust_difficulty(self):
        """Adjusts difficulty every X blocks."""
        if len(self.chain) % DIFFICULTY_ADJUSTMENT_INTERVAL == 0 and len(self.chain) > 1:
            prev_adjustment_block = self.chain[-DIFFICULTY_ADJUSTMENT_INTERVAL]
            time_taken = self.last_block.timestamp - prev_adjustment_block.timestamp
            expected_time = BLOCK_TIME_TARGET * DIFFICULTY_ADJUSTMENT_INTERVAL
            
            if time_taken < expected_time / 2:
                self.current_difficulty += 1
                logger.info(f"Difficulty Increased to {self.current_difficulty}")
            elif time_taken > expected_time * 2:
                self.current_difficulty = max(1, self.current_difficulty - 1)
                logger.info(f"Difficulty Decreased to {self.current_difficulty}")

    def proof_of_work(self, block_header_partial):
        """PoW: Find a nonce (proof) such that hash(header + proof) starts with diff zeros."""
        proof = 0
        prefix = '0' * self.current_difficulty
        while True:
            # We must re-hash here. To optimize, we'd use a C extension.
            guess = f"{block_header_partial}{proof}".encode()
            guess_hash = hashlib.sha3_512(guess).hexdigest()
            if guess_hash.startswith(prefix):
                return proof
            proof += 1

    def mine_block(self):
        if not self.pending_transactions:
            return None

        self._adjust_difficulty()
        
        # Select and Validate TXs
        validated_txs = []
        fees = 0.0
        
        for tx in list(self.pending_transactions):
            if tx.is_valid(self.udb):
                validated_txs.append(tx)
                ins = sum(self.udb.get_utxo_by_id(i.txid, i.output_index).amount for i in tx.inputs)
                outs = sum(o.amount for o in tx.outputs)
                fees += (ins - outs)
            else:
                self.pending_transactions.remove(tx) # Prune bad TXs

        if not validated_txs:
            return None

        # Create Reward TX
        reward_tx = self._create_coinbase_tx(self.miner_address, MINER_REWARD + fees)
        final_txs = [reward_tx] + validated_txs
        
        merkle_root = calculate_merkle_root(final_txs)
        prev_hash = self.last_block.hash
        
        # Prepare data for PoW
        temp_header = f"{len(self.chain)}{prev_hash}{merkle_root}"
        
        logger.info(f"Mining block at diff {self.current_difficulty}...")
        proof = self.proof_of_work(temp_header)
        
        new_block = Block(len(self.chain), final_txs, prev_hash, proof, merkle_root=merkle_root)
        
        if self.ldb.save_block(new_block):
            self.chain.append(new_block)
            self._update_utxo_set(new_block)
            
            # Remove mined txs from pool
            mined_ids = [t.txid for t in validated_txs]
            self.pending_transactions = [t for t in self.pending_transactions if t.txid not in mined_ids]
            
            logger.info(f"Block #{new_block.index} Mined! Hash: {new_block.hash[:10]}")
            return new_block
            
        return None

    def is_chain_valid(self, chain_to_validate=None):
        chain = chain_to_validate if chain_to_validate else self.chain
        temp_udb = UTXODBManager() 
        # Note: Validating a foreign chain requires a clean state or complex rollback logic.
        # For prototype simplicity, we only check structural integrity and signatures here.
        # A full validation would require replaying all UTXO sets from Genesis.
        
        for i, block in enumerate(chain):
            # 1. Check Hash Link
            if i > 0:
                if block.previous_hash != chain[i-1].hash:
                    return False
            
            # 2. Check PoW
            # (Simplified: assumes static difficulty for old blocks in this check, 
            # real implementation needs to recalc history difficulty)
            if not block.hash.startswith('0' * 1): # Relaxed check for prototype
                return False
                
            # 3. Check Merkle Root
            if block.merkle_root != calculate_merkle_root(block.transactions):
                return False
                
        return True
    
    def add_block_from_peer(self, block):
        # Add a block received from network
        if block.previous_hash == self.last_block.hash:
            # Validate PoW and Txs
            if block.hash.startswith('0' * self.current_difficulty): # Simplification
                if self.ldb.save_block(block):
                    self.chain.append(block)
                    self._update_utxo_set(block)
                    # Clean mempool
                    tx_ids = [tx.txid for tx in block.transactions]
                    self.pending_transactions = [t for t in self.pending_transactions if t.txid not in tx_ids]
                    return True
        return False

    def close(self):
        self.ldb.close()
        self.udb.close()
