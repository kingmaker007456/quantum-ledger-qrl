# main.py
import os
import time
from wallet_manager import WalletManager
from ledger import QuantumLedger
from logger import logger
from config import MINER_ADDRESS_ALIAS, DB_NAME, WALLET_DB_NAME, UTXO_DB_NAME

def cleanup():
    for f in [DB_NAME, WALLET_DB_NAME, UTXO_DB_NAME]:
        if os.path.exists(f):
            os.remove(f)

def run_demo():
    cleanup()
    logger.info("--- STARTING DEMO ---")
    
    wm = WalletManager()
    miner_pub, _ = wm.create_new_wallet(MINER_ADDRESS_ALIAS)
    alice_pub, _ = wm.create_new_wallet("Alice")
    
    # Init Ledger (Genesis)
    ledger = QuantumLedger(miner_pub)
    
    # Mine 1st block to confirm Genesis and get some rewards valid
    # Note: In real Bitcoin, coinbase is locked for 100 blocks. We allow immediate spend for demo.
    logger.info("Mining Block 1...")
    ledger.mine_block() # This might fail if no TXs in pool, but logic allows empty block if we want (modified ledger to strict check pending)
    
    # Actually, we need to bypass mine_block pending check or add a dummy TX. 
    # For this demo, let's just inspect Genesis balance.
    
    bal, _ = wm.get_balance(miner_pub)
    logger.info(f"Miner Balance (Genesis): {bal}")
    
    # Create TX
    tx = wm.create_transaction(MINER_ADDRESS_ALIAS, alice_pub, 50.0)
    if tx:
        ledger.add_transaction(tx)
        logger.info("Mining Block with TX...")
        ledger.mine_block()
        
    bal_alice, _ = wm.get_balance(alice_pub)
    logger.info(f"Alice Balance: {bal_alice}")
    
    ledger.close()
    wm.close()
    logger.info("--- DEMO COMPLETE ---")

if __name__ == '__main__':
    run_demo()
