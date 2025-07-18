import pytest
import time
import os
from datetime import datetime, timezone, timedelta
from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS

class TestInfluxDBIntegration:

    def test_write_temperature_event(self, influxdb_client):
        write_api = influxdb_client.write_api(write_options=SYNCHRONOUS)
        
        point = Point("temperature_events") \
            .tag("device_id", "test_device_001") \
            .tag("location", "living_room") \
            .field("temperature", 23.5) \
            .time(datetime.now(timezone.utc))
        
        write_api.write(bucket="temperature-events", record=point)
        
        query_api = influxdb_client.query_api()
        query = '''
            from(bucket: "temperature-events")
            |> range(start: -1h)
            |> filter(fn: (r) => r._measurement == "temperature_events")
            |> filter(fn: (r) => r.device_id == "test_device_001")
        '''
        
        result = query_api.query(query)
        assert len(result) > 0
        assert result[0].records[0].values["device_id"] == "test_device_001"
        assert result[0].records[0].values["location"] == "living_room"
        assert result[0].records[0].values["_value"] == 23.5

    def test_write_multiple_events(self, influxdb_client):
        write_api = influxdb_client.write_api(write_options=SYNCHRONOUS)
        
        now = datetime.now(timezone.utc)
        points = [
            Point("temperature_events")
            .tag("device_id", "test_device_002")
            .tag("location", "kitchen")
            .field("temperature", 21.0)
            .time(now),
            
            Point("temperature_events")
            .tag("device_id", "test_device_003")
            .tag("location", "bedroom")
            .field("temperature", 19.5)
            .time(now + timedelta(seconds=1))
        ]
        
        write_api.write(bucket="temperature-events", record=points)
        
        # Wait a moment for write to complete
        time.sleep(1)
        
        query_api = influxdb_client.query_api()
        query = '''
            from(bucket: "temperature-events")
            |> range(start: -1h)
            |> filter(fn: (r) => r._measurement == "temperature_events")
            |> filter(fn: (r) => r.device_id == "test_device_002" or r.device_id == "test_device_003")
            |> group()
        '''
        
        result = query_api.query(query)
        assert len(result) > 0
        assert len(result) == 1, f"Expected 1 table, got {len(result)}"
        
        device_ids = [record.values["device_id"] for record in result[0].records]
        assert "test_device_002" in device_ids
        assert "test_device_003" in device_ids

    def test_retention_policy(self, influxdb_client):
        query_api = influxdb_client.query_api()
        
        bucket_query = '''
            buckets()
            |> filter(fn: (r) => r.name == "temperature-events")
        '''
        
        result = query_api.query(bucket_query)
        assert len(result) > 0
        retention_period = result[0].records[0].values["retentionPeriod"]
        # InfluxDB returns retention period in nanoseconds, convert to seconds
        retention_seconds = retention_period // 1_000_000_000
        assert retention_seconds == 604800  # 1 week in seconds