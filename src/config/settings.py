import os
from typing import Dict, Any
from src.config.logger import get_logger

logger = get_logger(__name__)


class ConfigManager:
    
    def __init__(self):
        self._config = self._load_from_env()
        logger.info("Configuration loaded from environment variables")
    
    def _load_from_env(self) -> Dict[str, Any]:
        return {
            "influxdb": {
                "url": os.getenv("INFLUXDB_URL", "http://localhost:8086"),
                "token": os.getenv("INFLUXDB_TOKEN", "smart-home-token"),
                "org": os.getenv("INFLUXDB_ORG", "smart-home"),
                "bucket": os.getenv("INFLUXDB_BUCKET", "sensor-events")
            },
            "logging": {
                "level": os.getenv("LOG_LEVEL", "INFO")
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        if self._config is None:
            return default
        
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_logging_config(self) -> Dict[str, Any]:
        return self.get('logging', {})


config = ConfigManager()