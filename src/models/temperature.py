from datetime import datetime
from typing import List, Optional
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import pandas as pd
import warnings
from src.config.settings import config
from src.config.logger import get_logger

warnings.filterwarnings("ignore", category=UserWarning, module="influxdb_client")

logger = get_logger(__name__)


class TemperatureModel:
    def __init__(self):
        self.client = None
        self.bucket = config.get("influxdb.bucket", "temperature-events")
        self.org = config.get("influxdb.org", "smart-home")
        self._connect()

    def _connect(self):
        try:
            self.client = InfluxDBClient(
                url=config.get("influxdb.url", "http://localhost:8086"),
                token=config.get("influxdb.token", "smart-home-token"),
                org=self.org
            )
            logger.info("Connected to InfluxDB")
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB: {e}")
            raise

    def get_temperature_data(self, start_time: str = "-1h", device_ids: Optional[List[str]] = None) -> pd.DataFrame:
        query = f'''
        from(bucket: "{self.bucket}")
        |> range(start: {start_time})
        |> filter(fn: (r) => r["_measurement"] == "temperature_events")
        |> filter(fn: (r) => r["_field"] == "temperature")
        '''
        
        if device_ids:
            device_filter = ' or '.join([f'r["device_id"] == "{device_id}"' for device_id in device_ids])
            query += f'|> filter(fn: (r) => {device_filter})'
        
        query += '|> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'
        
        try:
            query_api = self.client.query_api()
            result = query_api.query_data_frame(query)
            
            if result.empty:
                return pd.DataFrame(columns=['_time', 'temperature', 'device_id', 'location'])
            
            result['_time'] = pd.to_datetime(result['_time'])
            return result[['_time', 'temperature', 'device_id', 'location']]
        except Exception as e:
            logger.error(f"Error querying temperature data: {e}")
            return pd.DataFrame(columns=['_time', 'temperature', 'device_id', 'location'])

    def get_devices(self) -> List[str]:
        query = f'''
        from(bucket: "{self.bucket}")
        |> range(start: -24h)
        |> filter(fn: (r) => r["_measurement"] == "temperature_events")
        |> distinct(column: "device_id")
        |> keep(columns: ["device_id"])
        '''
        
        try:
            query_api = self.client.query_api()
            result = query_api.query_data_frame(query)
            
            if result.empty:
                return []
            
            return result['device_id'].unique().tolist()
        except Exception as e:
            logger.error(f"Error getting devices: {e}")
            return []

    def close(self):
        if self.client:
            self.client.close()