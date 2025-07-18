#!/usr/bin/env python3

import time
import random
from datetime import datetime, timezone, timedelta
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import os

def populate_dummy_data():
    client = InfluxDBClient(
        url=os.getenv("INFLUXDB_URL", "http://localhost:8086"),
        token=os.getenv("INFLUXDB_TOKEN", "smart-home-token"),
        org=os.getenv("INFLUXDB_ORG", "smart-home")
    )
    
    write_api = client.write_api(write_options=SYNCHRONOUS)
    bucket = os.getenv("INFLUXDB_BUCKET", "temperature-events")
    
    devices = [
        {"device_id": "sensor_001", "location": "living_room", "base_temp": 22.5},
        {"device_id": "sensor_002", "location": "kitchen", "base_temp": 21.0},
        {"device_id": "sensor_003", "location": "bedroom", "base_temp": 19.5},
        {"device_id": "sensor_004", "location": "bathroom", "base_temp": 23.0},
        {"device_id": "sensor_005", "location": "office", "base_temp": 20.5},
    ]
    
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=24)
    
    points = []
    
    current_time = start_time
    while current_time <= now:
        for device in devices:
            temp_variation = random.uniform(-3, 3)
            time_variation = random.uniform(-0.5, 0.5)
            
            hour = current_time.hour
            daily_pattern = 2 * (1 + 0.5 * (1 - abs(hour - 14) / 12))
            
            temperature = device["base_temp"] + temp_variation + daily_pattern
            
            point = Point("temperature_events") \
                .tag("device_id", device["device_id"]) \
                .tag("location", device["location"]) \
                .field("temperature", round(temperature, 1)) \
                .time(current_time + timedelta(minutes=time_variation))
            
            points.append(point)
        
        current_time += timedelta(minutes=5)
    
    print(f"Writing {len(points)} temperature data points to InfluxDB...")
    
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        write_api.write(bucket=bucket, record=batch)
        print(f"Written batch {i//batch_size + 1}/{(len(points) + batch_size - 1)//batch_size}")
    
    print("Successfully populated dummy temperature data!")
    print(f"Data covers: {start_time.strftime('%Y-%m-%d %H:%M')} to {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"Devices: {', '.join([d['device_id'] for d in devices])}")
    print(f"Locations: {', '.join([d['location'] for d in devices])}")
    
    client.close()

if __name__ == "__main__":
    populate_dummy_data()