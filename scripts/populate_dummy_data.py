#!/usr/bin/env python3

import time
import random
from datetime import datetime, timezone, timedelta
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import os

def clean_influxdb_data(client, bucket, org, token):
    """Clean all existing data from the specified bucket"""
    try:
        delete_api = client.delete_api()
        delete_api.delete(
            start='1970-01-01T00:00:00Z',
            stop='2099-12-31T23:59:59Z',
            predicate='',
            bucket=bucket,
            org=org
        )
        print(f"Successfully cleaned existing data from bucket '{bucket}'")
    except Exception as e:
        print(f"Warning: Could not clean existing data: {e}")
        print("Continuing with data population...")

def populate_dummy_data():
    client = InfluxDBClient(
        url=os.getenv("INFLUXDB_URL", "http://localhost:8086"),
        token=os.getenv("INFLUXDB_TOKEN", "smart-home-token"),
        org=os.getenv("INFLUXDB_ORG", "smart-home")
    )
    
    write_api = client.write_api(write_options=SYNCHRONOUS)
    bucket = os.getenv("INFLUXDB_BUCKET", "sensor-events")
    org = os.getenv("INFLUXDB_ORG", "smart-home")
    token = os.getenv("INFLUXDB_TOKEN", "smart-home-token")

    print("Cleaning existing data...")
    clean_influxdb_data(client, bucket, org, token)
    
    devices = [
        {"device_id": "temp_001", "location": "living_room", "type": "temperature", "base_value": 22.5, "range": (-3, 3), "unit": "°C"},
        {"device_id": "temp_002", "location": "kitchen", "type": "temperature", "base_value": 21.0, "range": (-3, 3), "unit": "°C"},
        {"device_id": "temp_003", "location": "bedroom", "type": "temperature", "base_value": 19.5, "range": (-3, 3), "unit": "°C"},
        {"device_id": "humid_001", "location": "living_room", "type": "humidity", "base_value": 45.0, "range": (-10, 15), "unit": "%"},
        {"device_id": "humid_002", "location": "bathroom", "type": "humidity", "base_value": 65.0, "range": (-15, 20), "unit": "%"},
        {"device_id": "motion_001", "location": "hallway", "type": "motion", "base_value": 0, "range": (0, 1), "unit": ""},
        {"device_id": "motion_002", "location": "entrance", "type": "motion", "base_value": 0, "range": (0, 1), "unit": ""},
        {"device_id": "gas_001", "location": "kitchen", "type": "gas", "base_value": 0.1, "range": (0, 0.3), "unit": "ppm"},
        {"device_id": "gas_002", "location": "basement", "type": "gas", "base_value": 0.05, "range": (0, 0.2), "unit": "ppm"},
    ]
    
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=24)
    
    points = []
    
    current_time = start_time
    while current_time <= now:
        for device in devices:
            time_variation = random.uniform(-0.5, 0.5)
            
            if device["type"] == "temperature":
                variation = random.uniform(*device["range"])
                hour = current_time.hour
                daily_pattern = 2 * (1 + 0.5 * (1 - abs(hour - 14) / 12))
                value = device["base_value"] + variation + daily_pattern
                value = round(value, 1)
            elif device["type"] == "humidity":
                variation = random.uniform(*device["range"])
                hour = current_time.hour
                daily_pattern = 5 * (1 + 0.3 * (1 - abs(hour - 6) / 12))
                raw_value = device["base_value"] + variation + daily_pattern
                value = max(0.0, min(100.0, round(raw_value, 1)))
            elif device["type"] == "motion":
                value = 1.0 if random.random() < 0.05 else 0.0
            elif device["type"] == "gas":
                variation = random.uniform(*device["range"])
                base_noise = random.uniform(-0.01, 0.01)
                raw_value = device["base_value"] + base_noise + (variation if random.random() < 0.1 else 0)
                value = round(max(0.0, raw_value), 3)
            
            point = Point("sensor_events") \
                .tag("device_id", device["device_id"]) \
                .tag("location", device["location"]) \
                .tag("type", device["type"]) \
                .field("value", value) \
                .time(current_time + timedelta(minutes=time_variation))
            
            points.append(point)
        
        current_time += timedelta(minutes=5)
    
    print(f"Writing {len(points)} sensor data points to InfluxDB...")
    
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        write_api.write(bucket=bucket, record=batch)
        print(f"Written batch {i//batch_size + 1}/{(len(points) + batch_size - 1)//batch_size}")
    
    print("Successfully populated dummy sensor data!")
    print(f"Data covers: {start_time.strftime('%Y-%m-%d %H:%M')} to {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"Devices: {', '.join([d['device_id'] for d in devices])}")
    print(f"Locations: {', '.join(set([d['location'] for d in devices]))}")
    print(f"Types: {', '.join(set([d['type'] for d in devices]))}")
    
    client.close()

if __name__ == "__main__":
    populate_dummy_data()