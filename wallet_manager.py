# wallet_manager.py
from pqc_primitives import generate_pqc_key_pair
from db_manager import WalletDBManager, UTXODBManager
from transaction import Transaction, TxInput, TxOutput
from logger import logger

class WalletManager:
    def __init__(self):
        self.wdb = WalletDBManager()
        self.utxodb = UTXODBManager()

    def create_new_wallet(self, alias):
        pub, priv = generate_pqc_key_pair()
        if self.wdb.save_wallet(pub, priv, alias):
            return pub, priv
        return None, None

    def get_keys(self, alias=None, pub_key=None):
        if alias and not pub_key:
            # Helper to find pubkey from alias
            wallets = self.wdb.get_all_wallets()
            # row is (pub_key, alias) - sqlite3.Row or tuple
            for row in wallets:
                if row[1] == alias:
                    pub_key = row[0]
                    break
        
        priv = self.wdb.get_private_key(public_key=pub_key, alias=alias)
        return pub_key, priv

    def get_balance(self, public_key):
        utxos = self.utxodb.get_unspent_outputs(public_key)
        bal = sum(u.amount for u in utxos)
        return bal, utxos

    def create_transaction(self, sender_alias, recipient_pub, amount, fee=0.0):
        pub, priv = self.get_keys(alias=sender_alias)
        if not pub:
            return None
        
        balance, utxos = self.get_balance(pub)
        if balance < (amount + fee):
            logger.error(f"Insufficient funds: {balance} < {amount+fee}")
            return None

        # Select UTXOs
        selected = []
        current_sum = 0.0
        # Sort by amount desc to minimize dust
        utxos.sort(key=lambda u: u.amount, reverse=True)
        
        for u in utxos:
            selected.append(u)
            current_sum += u.amount
            if current_sum >= (amount + fee):
                break
        
        inputs = [TxInput(u.txid, u.output_index, pub_key=pub) for u in selected]
        outputs = [TxOutput(amount, recipient_pub)]
        
        change = current_sum - (amount + fee)
        if change > 0:
            outputs.append(TxOutput(change, pub))
            
        tx = Transaction(inputs, outputs)
        
        # Sign
        for i in range(len(tx.inputs)):
            tx.sign_input(i, priv)
            
        return tx

    def close(self):
        self.wdb.close()
        self.utxodb.close()
