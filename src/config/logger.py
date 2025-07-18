import logging
import sys
from datetime import datetime


def setup_logger(name: str = __name__, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(level)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = __name__) -> logging.Logger:
    return setup_logger(name)