🌐 README.md for GitHub
# quantum-ledger-qrl

## Quantum Ledger: A UTXO-Based, Post-Quantum Cryptography Simulation

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Project Status](https://img.shields.io/badge/Status-Simulation-orange.svg)](https://github.com/kingmaker007456/quantum-ledger-qrl)

The *Quantum Ledger* project is a robust, end-to-end simulation of a modern, post-quantum secure blockchain. It integrates the *Unspent Transaction Output (UTXO)* model with a simulated *CRYSTALS-Dilithium-3* PQC scheme for key generation and signing. The project includes a full database persistence layer for blocks and UTXOs, a Proof-of-Work (PoW) consensus mechanism, and a multi-node P2P network for conflict resolution.

## ✨ Features

* *Post-Quantum Cryptography (PQC) Simulation:* Uses a mock implementation of the NIST Round 3 winner, *CRYSTALS-Dilithium-3*, for wallet key pairs and transaction signatures.
* *UTXO Model Implementation:* Tracks the state of the network using the authoritative *Unspent Transaction Output (UTXO)* set, enabling complex transaction validation, fee calculation, and change generation.
* *Proof-of-Work (PoW) Consensus:* Simple PoW algorithm to secure blocks and manage mining difficulty.
* *SQLite Persistence:* Stores the full blockchain, the UTXO set, and local wallet keys in separate, managed SQLite databases (.db files).
* *P2P Network Gossip:* Simulates peer-to-peer communication via Flask endpoints for block/transaction broadcasting and the *Longest Chain Rule* for conflict resolution.
* *Modular Design:* Separates concerns into dedicated modules for configuration, logging, database management, transactions, wallet logic, and the core ledger.

## 📁 Project Structure


quantum-ledger-qrl/
├── config.py             # Global constants for node, network, DB names, and PQC scheme.
├── logger.py             # Structured logging setup.
├── pqc_primitives.py     # PQC simulation (hashing, key generation, sign/verify).
├── db_manager.py         # Handles all SQLite database interactions (Blocks, Peers, Wallets, UTXOs).
├── transaction.py        # Defines TxInput, TxOutput, and the core Transaction signing/validation logic.
├── wallet_manager.py     # Manages key pairs, calculates UTXO balance, and creates signed transactions.
├── ledger.py             # Core Blockchain logic (Block structure, PoW, mining, UTXO set management).
├── network.py            # P2P logic (Peer discovery, block/TX gossip, chain synchronization).
├── app.py                # Flask API endpoints for node interaction and P2P communication.
└── main.py     # Script to demonstrate end-to-end functionality (Wallets, TX, Mining).

## 🛠 Getting Started

### Prerequisites

You need *Python 3.8+* and the following libraries:

```bash
pip install Flask requests

Running the Simulation
The run_simulation.py script provides a non-networked demonstration of the core UTXO and mining logic.
 * Execute the simulation script:
   python run_simulation.py

 * View Output: This script will:
   * Initialize wallets for Miner, Alice, and Bob.
   * Create the Genesis Block.
   * Mine Block #1 (initial miner reward).
   * Create a transaction (Miner sends 100.0 to Alice, paying 1.0 fee).
   * Mine Block #2 (confirms the transaction, pays miner the new reward + fee).
   * Print the final UTXO balances for all parties.
Running the P2P Network (Multi-Node Setup)
To test the P2P networking and conflict resolution:
 * Open two terminal windows (Node A and Node B).
 * Start Node A on the default port (5000):
   # In Terminal 1
python app.py

 * Start Node B on an alternate port (5001) by modifying config.py temporarily or setting an environment variable (e.g., in a real setup):
   (For this simulation, run Node A on default, and Node B will need manual config adjustment or separate environments to change config.NODE_PORT to 5001 before running the second instance).
 * Register Node A to Node B (if not already handled by initial peers):
   # Example using curl to register Node A to a running Node B (on 5001)
curl -X POST [http://127.0.0.1:5001/nodes/register](http://127.0.0.1:5001/nodes/register) -H "Content-Type: application/json" -d '{"address": "[http://127.0.0.1:5000](http://127.0.0.1:5000)"}'

 * Mine blocks and create transactions on either node to observe gossip and chain sync.
💡 Core Concepts
Post-Quantum Cryptography (PQC)
The system simulates the use of a PQC algorithm for key pairs. Unlike traditional schemes like ECDSA, PQC algorithms (like Dilithium) use much larger keys and signatures to resist attacks from quantum computers. The pqc_primitives.py module manages this simulation, ensuring that all transactions are signed with these large, mock PQC signatures.
UTXO Model
The system utilizes the UTXO (Unspent Transaction Output) model, where a wallet's balance is the sum of all unspent outputs owned by that wallet's public key.
 * Transactions consume one or more UTXOs (inputs) and create new UTXOs (outputs).
 * Change is created as a new UTXO sent back to the sender's address.
 * Fees are the difference between the total input amount and the total output amount, claimed by the miner.
🔗 API Endpoints (Flask)
The app.py exposes the following RESTful API endpoints:
| Endpoint | Method | Description |
|---|---|---|
| /mine | GET | Initiates the Proof-of-Work process to mine a new block with pending transactions. |
| /chain | GET | Returns the full blockchain (used for network sync). |
| /transactions/create | POST | Creates, signs, and submits a new UTXO transaction to the pending pool. |
| /transactions/receive | POST | P2P endpoint to accept a gossiped transaction from a peer. |
| /block/receive | POST | P2P endpoint to accept a newly mined block from a peer. |
| /nodes/register | POST | Registers a new node address to the peer list. |
| /wallets/<alias>/balance | GET | Retrieves the current UTXO balance for a specified local wallet alias. |
⚙ Configuration
Key constants can be adjusted in config.py:
| Constant | Default Value | Description |
|---|---|---|
| MINING_DIFFICULTY | 4 | Number of leading '0's required for PoW. |
| MINER_REWARD | 10.0 | Base reward for mining a block. |
| PQC_SCHEME_NAME | "CRYSTALS-Dilithium-3" | The simulated PQC scheme. |
| GOSSIP_INTERVAL | 30 | Seconds between P2P network gossip/sync checks.