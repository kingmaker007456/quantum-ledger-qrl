# transaction.py
import time
import json
from typing import List, Optional, Dict
from pqc_primitives import pqc_sign, pqc_verify, hash_data
from logger import logger
from config import TRANSACTION_VERSION
from db_manager import UTXODBManager

class TxInput:
    def __init__(self, txid: str, output_index: int, signature: str = None, pub_key: str = None):
        self.txid = txid
        self.output_index = output_index
        self.signature = signature
        self.pub_key = pub_key

    def to_dict(self):
        # Sort keys for consistent hashing
        return {
            'output_index': self.output_index,
            'pub_key': self.pub_key,
            'signature': self.signature,
            'txid': self.txid
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(data['txid'], data['output_index'], data.get('signature'), data.get('pub_key'))

class TxOutput:
    def __init__(self, amount: float, address: str):
        self.amount = float(amount)
        self.address = address

    def to_dict(self):
        return {'address': self.address, 'amount': self.amount}
    
    @classmethod
    def from_dict(cls, data):
        return cls(data['amount'], data['address'])

class Transaction:
    def __init__(self, inputs: List[TxInput] = None, outputs: List[TxOutput] = None, version=TRANSACTION_VERSION, timestamp=None):
        self.version = version
        self.timestamp = timestamp if timestamp else time.time()
        self.inputs = inputs if inputs else []
        self.outputs = outputs if outputs else []
        self._txid = self._calculate_txid()

    @property
    def txid(self):
        return self._txid

    def _calculate_txid(self):
        tx_data = self.to_dict(include_signature=False)
        return hash_data(tx_data)

    def to_dict(self, include_signature=True):
        inputs_list = [i.to_dict() for i in self.inputs]
        
        if not include_signature:
            for i in inputs_list:
                i['signature'] = None
        
        # Consistent key sorting is mandatory for Merkle Trees and Signatures
        return {
            'inputs': inputs_list,
            'outputs': [o.to_dict() for o in self.outputs],
            'timestamp': self.timestamp,
            'version': self.version
        }

    @classmethod
    def from_dict(cls, data):
        inputs = [TxInput.from_dict(i) for i in data.get('inputs', [])]
        outputs = [TxOutput.from_dict(o) for o in data.get('outputs', [])]
        tx = cls(inputs, outputs, data.get('version', TRANSACTION_VERSION), data.get('timestamp'))
        tx._txid = data.get('txid') or tx._calculate_txid()
        return tx

    def sign_input(self, input_index, private_key):
        if input_index >= len(self.inputs):
            raise IndexError("Input index out of range.")
        
        # The signature signs the TXID (which is the hash of the invariant parts of the TX)
        data_to_sign = self._txid 
        signature = pqc_sign(private_key, data_to_sign)
        self.inputs[input_index].signature = signature
        return signature

    def is_valid(self, utxo_set_manager: UTXODBManager, is_coinbase=False):
        if not self.outputs:
            return False

        if is_coinbase:
            if len(self.inputs) != 1 or self.inputs[0].txid != "0" * 128:
                return False
            return True

        if not utxo_set_manager:
            logger.error("Validation Error: UTXO manager missing.")
            return False

        input_sum = 0.0
        output_sum = sum(o.amount for o in self.outputs)
        data_to_verify = self._txid

        for i, tx_input in enumerate(self.inputs):
            utxo = utxo_set_manager.get_utxo_by_id(tx_input.txid, tx_input.output_index)
            
            if not utxo:
                logger.error(f"Input {i} references unknown UTXO.")
                return False
            if utxo.is_spent():
                logger.error(f"Input {i} references SPENT UTXO.")
                return False
            if utxo.address != tx_input.pub_key:
                logger.error(f"Input {i} key mismatch.")
                return False
            
            if not pqc_verify(tx_input.pub_key, data_to_verify, tx_input.signature):
                logger.error(f"Signature verification failed for input {i}.")
                return False
                
            input_sum += utxo.amount

        if input_sum < output_sum:
            logger.error(f"Insufficient funds: In {input_sum} < Out {output_sum}")
            return False
            
        return True
