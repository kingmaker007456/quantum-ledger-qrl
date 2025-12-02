# pqc_primitives.py
import random
import time
import hashlib
import json
from typing import Tuple, Union, Dict, Any
from logger import logger
from config import PQC_SCHEME_NAME

# --- HASHING ---
def hash_data(data: Union[Dict, str, bytes]) -> str:
    """Generates a SHA3-512 hash of the input data."""
    if isinstance(data, dict) or isinstance(data, list):
        # sort_keys=True is CRITICAL for consistent hashing across nodes
        encoded_data = json.dumps(data, sort_keys=True).encode('utf-8')
    elif isinstance(data, str):
        encoded_data = data.encode('utf-8')
    else:
        encoded_data = data
        
    return hashlib.sha3_512(encoded_data).hexdigest()

# --- PQC ALGORITHM BASE CLASS ---

class PQCAlgorithm:
    """Base class for Post-Quantum Cryptography Schemes."""
    def __init__(self, name: str, key_size_kb: float, signature_size_kb: float, security_level: int):
        self.name = name
        self.key_size = key_size_kb  
        self.signature_size = signature_size_kb 
        self.security_level = security_level 
        logger.debug(f"PQC Scheme loaded: {self.name}")

    def generate_key_pair(self) -> Tuple[str, str]:
        """Simulates key generation latency and returns size-accurate mock keys."""
        time.sleep(self.security_level * 0.005) 
        
        pub_key_hex_len = int(self.key_size * 2 * 1024)
        priv_key_hex_len = int(self.key_size * 4 * 1024)
        
        # Generate keys using secure random seeding simulation
        pub_key_seed = str(random.getrandbits(256))
        priv_key_seed = str(random.getrandbits(512))
        
        pub_key = hashlib.sha3_512(pub_key_seed.encode()).hexdigest() * 100
        priv_key = hashlib.sha3_512(priv_key_seed.encode()).hexdigest() * 100
        
        return pub_key[:pub_key_hex_len], priv_key[:priv_key_hex_len]

    def sign(self, private_key: str, data_hash: str) -> str:
        """Simulates signing time and returns a size-accurate mock signature."""
        time.sleep(self.security_level * 0.001)
        sig_hex_len = int(self.signature_size * 2 * 1024)
        
        # Deterministic signature generation for simulation stability
        sig_input = private_key[:100] + data_hash
        signature = hashlib.sha3_512(sig_input.encode()).hexdigest() * 100
        
        return signature[:sig_hex_len]
        
    def verify(self, public_key: str, data_hash: str, signature: str) -> bool:
        """Simulates verification."""
        time.sleep(self.security_level * 0.0005)
        
        expected_sig_len = int(self.signature_size * 2 * 1024)
        
        if len(signature) != expected_sig_len:
            logger.warning("PQC Verify: Invalid signature length.")
            return False
            
        return True

# --- NIST ROUND 3 SIMULATION ---

class Dilithium(PQCAlgorithm):
    """Lattice-based digital signature scheme."""
    def __init__(self):
        super().__init__(
            name="CRYSTALS-Dilithium-3",
            key_size_kb=2.7,     
            signature_size_kb=3.3, 
            security_level=3
        )

if PQC_SCHEME_NAME == "CRYSTALS-Dilithium-3":
    PQC_SIGNATURE_SCHEME = Dilithium()
else:
    raise ValueError(f"Unknown PQC scheme: {PQC_SCHEME_NAME}")

def generate_pqc_key_pair() -> Tuple[str, str]:
    return PQC_SIGNATURE_SCHEME.generate_key_pair()

def pqc_sign(private_key: str, data_hash: str) -> str:
    return PQC_SIGNATURE_SCHEME.sign(private_key, data_hash)

def pqc_verify(public_key: str, data_hash: str, signature: str) -> bool:
    return PQC_SIGNATURE_SCHEME.verify(public_key, data_hash, signature)
