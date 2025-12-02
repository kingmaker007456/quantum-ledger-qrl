# app.py
from flask import Flask, jsonify, request
from ledger import QuantumLedger, Block
from transaction import Transaction
from wallet_manager import WalletManager
from network import P2PNetwork
from config import NODE_PORT, NODE_URL, MINER_ADDRESS_ALIAS

app = Flask(__name__)

# --- INIT ---
wm = WalletManager()
miner_pub, _ = wm.get_keys(alias=MINER_ADDRESS_ALIAS)
if not miner_pub:
    miner_pub, _ = wm.create_new_wallet(MINER_ADDRESS_ALIAS)

ledger = QuantumLedger(miner_pub)
network = P2PNetwork(NODE_URL, ledger)
network.start_gossip_daemon()

@app.route('/mine', methods=['GET'])
def mine():
    block = ledger.mine_block()
    if block:
        network.announce_new_block(block)
        return jsonify(block.to_dict()), 200
    return jsonify({'message': 'No transactions or mining failed'}), 200

@app.route('/chain', methods=['GET'])
def get_chain():
    chain_data = [b.to_dict() for b in ledger.chain]
    return jsonify({'length': len(chain_data), 'chain': chain_data}), 200

@app.route('/transactions/create', methods=['POST'])
def send_tx():
    data = request.json
    tx = wm.create_transaction(
        data['sender_alias'], 
        data['recipient_pub_key'], 
        data['amount'], 
        data.get('fee', 0.1)
    )
    if tx:
        if ledger.add_transaction(tx):
            network.announce_new_transaction(tx)
            return jsonify({'txid': tx.txid}), 201
    return jsonify({'error': 'Failed to create TX'}), 400

@app.route('/transactions/receive', methods=['POST'])
def receive_tx():
    try:
        tx = Transaction.from_dict(request.json)
        if ledger.add_transaction(tx):
            return jsonify({'status': 'added'}), 200
        return jsonify({'status': 'rejected'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/block/receive', methods=['POST'])
def receive_block():
    try:
        # Reconstruct Block manually from JSON
        data = request.json
        txs = [Transaction.from_dict(t) for t in data['transactions']]
        block = Block(
            data['index'], txs, data['previous_hash'], 
            data['proof'], data['timestamp'], 
            merkle_root=data.get('merkle_root')
        )
        if ledger.add_block_from_peer(block):
            return jsonify({'status': 'accepted'}), 200
        return jsonify({'status': 'ignored'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/peers/register', methods=['POST'])
def register_peer():
    addr = request.json.get('address')
    if network.register_peer(addr):
        return jsonify({'message': 'Peer added'}), 201
    return jsonify({'error': 'Invalid peer'}), 400

@app.route('/wallets/<alias>/balance', methods=['GET'])
def balance(alias):
    pub, _ = wm.get_keys(alias=alias)
    if pub:
        bal, _ = wm.get_balance(pub)
        return jsonify({'alias': alias, 'balance': bal}), 200
    return jsonify({'error': 'Wallet not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=NODE_PORT, threaded=True)
