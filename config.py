import os

# --- NODE AND NETWORK CONFIGURATION ---
NODE_PORT = int(os.environ.get("NODE_PORT", 5000))
NODE_URL = f"http://127.0.0.1:{NODE_PORT}"
MINER_ADDRESS_ALIAS = "Miner_Node_Wallet"

# --- MINING AND CONSENSUS CONFIGURATION ---
INITIAL_DIFFICULTY = 4
MINER_REWARD = 10.0
BLOCK_TIME_TARGET = 10  # Seconds per block
DIFFICULTY_ADJUSTMENT_INTERVAL = 5 # Blocks (Adjust difficulty every X blocks)

# --- DATABASE CONFIGURATION ---
DB_NAME = f'quantum_ledger_{NODE_PORT}.db'
WALLET_DB_NAME = f'wallets_{NODE_PORT}.db'
UTXO_DB_NAME = f'utxo_set_{NODE_PORT}.db'

# --- P2P NETWORK CONFIGURATION ---
GOSSIP_INTERVAL = 10 # Seconds
INITIAL_PEERS = [] # Can be populated via env vars or manually
MAX_CHAIN_SYNC_ATTEMPTS = 3
NETWORK_TIMEOUT = 5 # Seconds

# --- CRYPTOGRAPHY CONFIGURATION ---
PQC_SCHEME_NAME = "CRYSTALS-Dilithium-3"
TRANSACTION_VERSION = 1

# --- LOGGING CONFIGURATION ---
LOG_LEVEL = 'INFO'
LOG_FILE = f'qrl_node_{NODE_PORT}.log'
