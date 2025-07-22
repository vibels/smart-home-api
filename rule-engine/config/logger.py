import logging
import os
from logging.handlers import RotatingFileHandler

def get_logger(name):
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        logger.setLevel(getattr(logging, log_level))
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        log_file = os.getenv('LOG_FILE')
        if log_file:
            file_handler = RotatingFileHandler(
                log_file, maxBytes=10*1024*1024, backupCount=5
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
    
    return logger