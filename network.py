# network.py
import requests
import time
import threading
from urllib.parse import urlparse
from ledger import QuantumLedger, Block
from transaction import Transaction
from logger import logger
from config import GOSSIP_INTERVAL, NETWORK_TIMEOUT, INITIAL_PEERS

class P2PNetwork:
    def __init__(self, node_url, ledger: QuantumLedger):
        self.node_url = node_url
        self.ledger = ledger
        self.peers = set()
        self.lock = threading.Lock()
        self._initialize_peers()

    def _initialize_peers(self):
        db_peers = self.ledger.ldb.load_all_peers()
        for peer in db_peers:
            if peer != self.node_url:
                self.peers.add(peer)
        for peer in INITIAL_PEERS:
            if peer != self.node_url:
                self.peers.add(peer)

    def register_peer(self, address):
        parsed = urlparse(address)
        if parsed.netloc:
            peer_url = parsed.geturl().strip('/')
            if peer_url != self.node_url:
                with self.lock:
                    self.peers.add(peer_url)
                self.ledger.ldb.save_peer(peer_url)
                return True
        return False

    def broadcast(self, endpoint, data):
        """Generic broadcast helper."""
        for peer in list(self.peers):
            threading.Thread(target=self._send_request, args=(peer, endpoint, data)).start()

    def _send_request(self, peer, endpoint, data):
        try:
            url = f"{peer}{endpoint}"
            requests.post(url, json=data, timeout=NETWORK_TIMEOUT)
        except Exception:
            # Silent fail is okay for gossip
            pass

    def announce_new_block(self, block):
        self.broadcast('/block/receive', block.to_dict())

    def announce_new_transaction(self, transaction):
        self.broadcast('/transactions/receive', transaction.to_dict(include_signature=True))

    def resolve_conflicts(self):
        with self.lock:
            longest_chain = None
            max_length = len(self.ledger.chain)

            for peer in list(self.peers):
                try:
                    resp = requests.get(f"{peer}/chain", timeout=NETWORK_TIMEOUT)
                    if resp.status_code == 200:
                        data = resp.json()
                        length = data['length']
                        chain_data = data['chain']

                        if length > max_length:
                            # Reconstruct chain
                            new_chain = []
                            for b_data in chain_data:
                                # Reconstruct block object from dict
                                txs = [Transaction.from_dict(t) for t in b_data['transactions']]
                                blk = Block(
                                    b_data['index'], txs, b_data['previous_hash'], 
                                    b_data['proof'], b_data['timestamp'], 
                                    merkle_root=b_data.get('merkle_root')
                                )
                                new_chain.append(blk)
                            
                            # Validate
                            if self.ledger.is_chain_valid(new_chain):
                                max_length = length
                                longest_chain = new_chain
                                
                except Exception as e:
                    logger.warning(f"Error syncing with {peer}: {e}")

            if longest_chain:
                self.ledger.chain = longest_chain
                self.ledger.ldb.clear_blocks()
                for blk in longest_chain:
                    self.ledger.ldb.save_block(blk)
                self.ledger.rebuild_utxo_set()
                logger.warning("Local chain replaced by longer peer chain.")
                return True
            return False

    def start_gossip_daemon(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while True:
            time.sleep(GOSSIP_INTERVAL)
            self.resolve_conflicts()
