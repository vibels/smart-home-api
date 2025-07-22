from datetime import datetime
from typing import List, Optional
from enum import Enum
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import pandas as pd
import warnings
from src.config.settings import config
from src.config.logger import get_logger

warnings.filterwarnings("ignore", category=UserWarning, module="influxdb_client")

logger = get_logger(__name__)


class SensorType(Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    MOTION = "motion"
    GAS = "gas"


class SensorModel:
    def __init__(self, sensor_type: SensorType):
        self.client = None
        self.sensor_type = sensor_type.value
        self.bucket = config.get("influxdb.bucket", "sensor-events")
        self.org = config.get("influxdb.org", "smart-home")
        self._connect()

    def _connect(self):
        try:
            self.client = InfluxDBClient(
                url=config.get("influxdb.url", "http://localhost:8086"),
                token=config.get("influxdb.token", "smart-home-token"),
                org=self.org
            )
            logger.info(f"Connected to InfluxDB for {self.sensor_type} sensors")
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB: {e}")
            raise

    def get_sensor_data(self, start_time: str = "-1h", device_ids: Optional[List[str]] = None, **extras) -> pd.DataFrame:
        query = f'''
        from(bucket: "{self.bucket}")
        |> range(start: {start_time})
        |> filter(fn: (r) => r["_measurement"] == "sensor_events")
        |> filter(fn: (r) => r["_field"] == "value")
        |> filter(fn: (r) => r["type"] == "{self.sensor_type}")
        '''
        
        if device_ids:
            device_filter = ' or '.join([f'r["device_id"] == "{device_id}"' for device_id in device_ids])
            query += f'|> filter(fn: (r) => {device_filter})'
        
        for key, value in extras.items():
            if isinstance(value, str):
                query += f'|> filter(fn: (r) => r["{key}"] == "{value}")'
            elif isinstance(value, list):
                filter_values = ' or '.join([f'r["{key}"] == "{v}"' for v in value])
                query += f'|> filter(fn: (r) => {filter_values})'
        
        query += '|> pivot(rowKey:["_time", "device_id", "location", "type"], columnKey: ["_field"], valueColumn: "_value")'
        
        try:
            query_api = self.client.query_api()
            result = query_api.query_data_frame(query)
            
            if result.empty:
                return pd.DataFrame(columns=['_time', 'value', 'device_id', 'location', 'type'])
            
            result['_time'] = pd.to_datetime(result['_time'])
            
            for col in ['location', 'type']:
                if col not in result.columns:
                    result[col] = None
            
            deduplicated_data = []
            for device_id in result['device_id'].unique():
                device_data = result[result['device_id'] == device_id].copy().reset_index(drop=True)
                if len(device_data) > 1:
                    try:
                        current_values = device_data['value'].iloc[1:]
                        previous_values = device_data['value'].iloc[:-1]
                        comparison = current_values.values != previous_values.values
                        mask = [True] + comparison.tolist()
                        deduplicated_device_data = device_data[mask]
                    except Exception as e:
                        deduplicated_device_data = device_data
                else:
                    deduplicated_device_data = device_data
                deduplicated_data.append(deduplicated_device_data)
            
            if deduplicated_data:
                result = pd.concat(deduplicated_data, ignore_index=True)
            
            return result[['_time', 'value', 'device_id', 'location', 'type']]
        except Exception as e:
            logger.error(f"Error querying {self.sensor_type} data: {e}")
            return pd.DataFrame(columns=['_time', 'value', 'device_id', 'location', 'type'])

    def get_devices(self, **extras) -> List[str]:
        query = f'''
        from(bucket: "{self.bucket}")
        |> range(start: -7d)
        |> filter(fn: (r) => r["_measurement"] == "sensor_events")
        |> filter(fn: (r) => r["type"] == "{self.sensor_type}")
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
            logger.error(f"Error getting {self.sensor_type} devices: {e}")
            return []

    def get_latest_device_data(self, **extras) -> pd.DataFrame:
        query = f'''
        from(bucket: "{self.bucket}")
        |> range(start: -24h)
        |> filter(fn: (r) => r["_measurement"] == "sensor_events")
        |> filter(fn: (r) => r["_field"] == "value")
        |> filter(fn: (r) => r["type"] == "{self.sensor_type}")
        |> group(columns: ["device_id"])
        |> last()
        |> pivot(rowKey:["_time", "device_id", "location", "type"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        try:
            query_api = self.client.query_api()
            result = query_api.query_data_frame(query)
            
            if result.empty:
                return pd.DataFrame(columns=['_time', 'value', 'device_id', 'location', 'type'])
            
            result['_time'] = pd.to_datetime(result['_time'])
            
            for col in ['location', 'type']:
                if col not in result.columns:
                    result[col] = None
            
            return result[['_time', 'value', 'device_id', 'location', 'type']]
        except Exception as e:
            logger.error(f"Error querying latest {self.sensor_type} device data: {e}")
            return pd.DataFrame(columns=['_time', 'value', 'device_id', 'location', 'type'])

    def close(self):
        if self.client:
            self.client.close()


class TemperatureModel(SensorModel):
    def __init__(self):
        super().__init__(SensorType.TEMPERATURE)


class HumidityModel(SensorModel):
    def __init__(self):
        super().__init__(SensorType.HUMIDITY)


class MotionModel(SensorModel):
    def __init__(self):
        super().__init__(SensorType.MOTION)


class GasModel(SensorModel):
    def __init__(self):
        super().__init__(SensorType.GAS)