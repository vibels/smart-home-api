#!/usr/bin/env python3

from datetime import datetime
from models import ActionableDeviceModel, ActionableDevice, DeviceCapability, CapabilityType, DeviceStatus


def populate_actionable_devices():
    actionable_model = ActionableDeviceModel()
    
    sample_devices = [
        ActionableDevice(
            device_id="door_001",
            device_type="smart_door",
            location="front_entrance",
            name="Front Door",
            status=DeviceStatus.ONLINE,
            capabilities=[
                DeviceCapability("locked", CapabilityType.TOGGLE, {"labels": ["Unlocked", "Locked"]}, True),
                DeviceCapability("open", CapabilityType.TOGGLE, {"labels": ["Closed", "Open"]}, False)
            ],
            last_updated=datetime.now()
        ),
        ActionableDevice(
            device_id="thermostat_001",
            device_type="thermostat",
            location="living_room",
            name="Living Room Thermostat",
            status=DeviceStatus.ONLINE,
            capabilities=[
                DeviceCapability("target_temperature", CapabilityType.ABSOLUTE_VALUE, {"min": 10, "max": 30, "unit": "°C", "step": 0.5}, 23.0),
                DeviceCapability("mode", CapabilityType.DISCRETE_VALUES, {"values": ["off", "heat", "cool", "auto"]}, "heat")
            ],
            last_updated=datetime.now()
        ),
        ActionableDevice(
            device_id="light_001",
            device_type="smart_light",
            location="kitchen",
            name="Kitchen Lights",
            status=DeviceStatus.ONLINE,
            capabilities=[
                DeviceCapability("on", CapabilityType.TOGGLE, {"labels": ["Off", "On"]}, True),
                DeviceCapability("brightness", CapabilityType.ABSOLUTE_VALUE, {"min": 0, "max": 100, "unit": "%", "step": 1}, 80),
                DeviceCapability("color", CapabilityType.DISCRETE_VALUES, {"values": ["warm_white", "cool_white", "red", "blue", "green"]}, "warm_white")
            ],
            last_updated=datetime.now()
        ),
        ActionableDevice(
            device_id="garage_001",
            device_type="garage_door",
            location="garage",
            name="Garage Door",
            status=DeviceStatus.TRIGGERED,
            capabilities=[
                DeviceCapability("open_close", CapabilityType.TRIGGER, {"action": "toggle_door", "duration_seconds": 15}, None)
            ],
            last_updated=datetime.now()
        ),
        ActionableDevice(
            device_id="valve_001",
            device_type="water_valve",
            location="garden",
            name="Garden Sprinkler Valve",
            status=DeviceStatus.ONLINE,
            capabilities=[
                DeviceCapability("open", CapabilityType.TOGGLE, {"labels": ["Closed", "Open"]}, False),
                DeviceCapability("flow_rate", CapabilityType.ABSOLUTE_VALUE, {"min": 0, "max": 10, "unit": "L/min", "step": 0.1}, 5.0)
            ],
            last_updated=datetime.now()
        )
    ]
    
    print("Populating actionable devices...")
    for device in sample_devices:
        success = actionable_model.add_device(device)
        if success:
            print(f"Added device: {device.name} ({device.device_id})")
        else:
            print(f"Failed to add device: {device.name} ({device.device_id})")
    
    print(f"\nSuccessfully populated {len(sample_devices)} sample actionable devices")
    print(f"Database path: {actionable_model.db_path}")


if __name__ == "__main__":
    populate_actionable_devices()