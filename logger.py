import logging
import sys
from config import LOG_FILE, LOG_LEVEL

def setup_logger(name):
    """Initializes a structured logger for modular use."""
    # Configure root logger once
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.getLevelName(LOG_LEVEL))
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler = logging.FileHandler(LOG_FILE, mode='w')
        file_handler.setFormatter(formatter)
        
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        
    return logger

logger = setup_logger('QRL')
