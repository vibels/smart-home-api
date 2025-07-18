import pytest
import time
import os
from influxdb_client import InfluxDBClient


@pytest.fixture(scope="session")
def influxdb_client():
    """Create InfluxDB client with environment variable configuration."""
    client = InfluxDBClient(
        url=os.getenv("INFLUXDB_URL", "http://localhost:8086"),
        token=os.getenv("INFLUXDB_TOKEN", "smart-home-token"),
        org=os.getenv("INFLUXDB_ORG", "smart-home")
    )
    
    # Wait for InfluxDB to be ready (initialization can take some time)
    time.sleep(10)
    
    yield client
    client.close()