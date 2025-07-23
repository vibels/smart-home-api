import psycopg2
import psycopg2.extras
import json
import os
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CapabilityType(Enum):
    TOGGLE = "toggle"
    ABSOLUTE_VALUE = "absolute_value" 
    DISCRETE_VALUES = "discrete_values"
    TRIGGER = "trigger"


class DeviceStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    TRIGGERED = "triggered"


@dataclass
class DeviceCapability:
    name: str
    capability_type: CapabilityType
    config: Dict[str, Any]
    current_value: Any


@dataclass
class Action:
    capability_name: str
    action_type: CapabilityType
    value: Any

@dataclass
class ToggleAction(Action):
    action_type: CapabilityType = CapabilityType.TOGGLE
    value: str = "on"  # "on", "off", or "toggle"

@dataclass 
class AbsoluteValueAction(Action):
    action_type: CapabilityType = CapabilityType.ABSOLUTE_VALUE
    value: float = 0.0

@dataclass
class DiscreteValueAction(Action):
    action_type: CapabilityType = CapabilityType.DISCRETE_VALUES
    value: str = ""  # Should match one of the values from capability config

@dataclass
class TriggerAction(Action):
    action_type: CapabilityType = CapabilityType.TRIGGER
    value: int = 30  # Duration in seconds, default 30

@dataclass
class Rule:
    device_id: str
    rule_name: str
    condition_tree: Dict[str, Any]
    actions: List[Action]
    rule_id: Optional[int] = None
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

def create_action_from_dict(capability_name: str, action_data: Dict[str, Any]) -> Action:
    if 'toggle' in action_data:
        return ToggleAction(
            capability_name=capability_name,
            value=action_data['toggle']
        )
    elif 'absolute_value' in action_data:
        return AbsoluteValueAction(
            capability_name=capability_name,
            value=action_data['absolute_value']
        )
    elif 'discrete_value' in action_data:
        discrete_config = action_data['discrete_value']
        value = next(iter(discrete_config.values())) if discrete_config else ""
        return DiscreteValueAction(
            capability_name=capability_name,
            value=value
        )
    elif 'trigger' in action_data:
        duration = action_data.get('duration', 30)
        return TriggerAction(
            capability_name=capability_name,
            value=duration
        )
    else:
        raise ValueError(f"Unknown action type in data: {action_data}")

def action_to_dict(action: Action) -> Dict[str, Any]:
    if isinstance(action, ToggleAction):
        return {'toggle': action.value}
    elif isinstance(action, AbsoluteValueAction):
        return {'absolute_value': action.value}
    elif isinstance(action, DiscreteValueAction):
        return {'discrete_value': {'key': action.value}}
    elif isinstance(action, TriggerAction):
        return {'trigger': True, 'duration': action.value}
    else:
        raise ValueError(f"Unknown action type: {type(action)}")

@dataclass
class ActionableDevice:
    device_id: str
    device_type: str
    location: str
    name: str
    status: DeviceStatus
    capabilities: List[DeviceCapability]
    last_updated: datetime


class ActionableDeviceModel:
    def __init__(self):
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.database = os.getenv("POSTGRES_DB", "smart_home")
        self.user = os.getenv("POSTGRES_USER", "smart_home_user")
        self.password = os.getenv("POSTGRES_PASSWORD", "smart_home_pass")
        self.port = os.getenv("POSTGRES_PORT", "5432")
        self._init_database()

    def _get_connection(self):
        return psycopg2.connect(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password,
            port=self.port
        )

    def _init_database(self):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        DO $$ BEGIN
                            CREATE TYPE device_status_enum AS ENUM ('online', 'offline', 'error', 'triggered');
                        EXCEPTION
                            WHEN duplicate_object THEN null;
                        END $$;
                    """)
                    
                    cursor.execute("""
                        DO $$ BEGIN
                            CREATE TYPE capability_type_enum AS ENUM ('toggle', 'absolute_value', 'discrete_values', 'trigger');
                        EXCEPTION
                            WHEN duplicate_object THEN null;
                        END $$;
                    """)
                    
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS actionable_devices (
                            device_id VARCHAR(100) PRIMARY KEY,
                            device_type VARCHAR(100) NOT NULL,
                            location VARCHAR(100) NOT NULL,
                            name VARCHAR(200) NOT NULL,
                            status device_status_enum NOT NULL,
                            last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS device_capabilities (
                            id SERIAL PRIMARY KEY,
                            device_id VARCHAR(100) REFERENCES actionable_devices(device_id) ON DELETE CASCADE,
                            name VARCHAR(100) NOT NULL,
                            capability_type capability_type_enum NOT NULL,
                            config JSONB,
                            current_value JSONB,
                            UNIQUE(device_id, name)
                        )
                    ''')
                    
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS device_rules (
                            rule_id SERIAL PRIMARY KEY,
                            device_id VARCHAR(100) REFERENCES actionable_devices(device_id) ON DELETE CASCADE,
                            rule_name VARCHAR(200) NOT NULL,
                            conditions JSONB NOT NULL,
                            actions JSONB NOT NULL,
                            enabled BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    
                    conn.commit()
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    def add_device(self, device: ActionableDevice) -> bool:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        INSERT INTO actionable_devices (device_id, device_type, location, name, status, last_updated)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (device_id) DO UPDATE SET
                            device_type = EXCLUDED.device_type,
                            location = EXCLUDED.location,
                            name = EXCLUDED.name,
                            status = EXCLUDED.status,
                            last_updated = EXCLUDED.last_updated
                    ''', (
                        device.device_id,
                        device.device_type,
                        device.location,
                        device.name,
                        device.status.value,
                        device.last_updated
                    ))
                    
                    cursor.execute('DELETE FROM device_capabilities WHERE device_id = %s', (device.device_id,))
                    
                    for cap in device.capabilities:
                        cursor.execute('''
                            INSERT INTO device_capabilities (device_id, name, capability_type, config, current_value)
                            VALUES (%s, %s, %s, %s, %s)
                        ''', (
                            device.device_id,
                            cap.name,
                            cap.capability_type.value,
                            json.dumps(cap.config),
                            json.dumps(cap.current_value)
                        ))
                    
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Error adding device {device.device_id}: {e}")
            return False

    def get_all_devices(self) -> List[ActionableDevice]:
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute('''
                        SELECT d.*, c.name as cap_name, c.capability_type, c.config, c.current_value
                        FROM actionable_devices d
                        LEFT JOIN device_capabilities c ON d.device_id = c.device_id
                        ORDER BY d.device_id, c.name
                    ''')
                    rows = cursor.fetchall()
                    
                    devices_dict = {}
                    for row in rows:
                        device_id = row['device_id']
                        if device_id not in devices_dict:
                            devices_dict[device_id] = {
                                'device_id': row['device_id'],
                                'device_type': row['device_type'],
                                'location': row['location'],
                                'name': row['name'],
                                'status': DeviceStatus(row['status']),
                                'last_updated': row['last_updated'],
                                'capabilities': []
                            }
                        
                        if row['cap_name']:
                            capability = DeviceCapability(
                                name=row['cap_name'],
                                capability_type=CapabilityType(row['capability_type']),
                                config=row['config'],
                                current_value=row['current_value']
                            )
                            devices_dict[device_id]['capabilities'].append(capability)
                    
                    devices = []
                    for device_data in devices_dict.values():
                        devices.append(ActionableDevice(**device_data))
                    
                    return devices
        except Exception as e:
            logger.error(f"Error getting devices: {e}")
            return []

    def add_rule(self, device_id: str, rule_name: str, conditions: Dict[str, Any], actions: Dict[str, Any]) -> bool:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        INSERT INTO device_rules (device_id, rule_name, conditions, actions)
                        VALUES (%s, %s, %s, %s)
                    ''', (device_id, rule_name, json.dumps(conditions), json.dumps(actions)))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Error adding rule for device {device_id}: {e}")
            return False

    def get_rules_for_device(self, device_id: str) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute('SELECT * FROM device_rules WHERE device_id = %s ORDER BY created_at DESC', (device_id,))
                    rows = cursor.fetchall()
                    
                    rules = []
                    for row in rows:
                        rules.append({
                            'rule_id': row['rule_id'],
                            'device_id': row['device_id'],
                            'rule_name': row['rule_name'],
                            'conditions': row['conditions'],
                            'actions': row['actions'],
                            'enabled': row['enabled'],
                            'created_at': row['created_at']
                        })
                    return rules
        except Exception as e:
            logger.error(f"Error getting rules for device {device_id}: {e}")
            return []

    def toggle_rule_enabled(self, rule_id: str) -> bool:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('SELECT enabled FROM device_rules WHERE rule_id = %s', (rule_id,))
                    result = cursor.fetchone()
                    if not result:
                        return False
                    
                    new_enabled = not result[0]
                    cursor.execute('''
                        UPDATE device_rules 
                        SET enabled = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE rule_id = %s
                    ''', (new_enabled, rule_id))
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error toggling rule {rule_id}: {e}")
            return False

    def update_rule(self, rule_id: str, rule_name: str, conditions: Dict[str, Any], actions: Dict[str, Any]) -> bool:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE device_rules 
                        SET rule_name = %s, conditions = %s, actions = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE rule_id = %s
                    ''', (rule_name, json.dumps(conditions), json.dumps(actions), rule_id))
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating rule {rule_id}: {e}")
            return False

    def delete_rule(self, rule_id: str) -> bool:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('DELETE FROM device_rules WHERE rule_id = %s', (rule_id,))
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting rule {rule_id}: {e}")
            return False

    def update_device_capability(self, device_id: str, capability_name: str, new_value: Any) -> bool:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE device_capabilities 
                        SET current_value = %s
                        WHERE device_id = %s AND name = %s
                    ''', (json.dumps(new_value), device_id, capability_name))
                    
                    cursor.execute('''
                        UPDATE actionable_devices 
                        SET last_updated = CURRENT_TIMESTAMP
                        WHERE device_id = %s
                    ''', (device_id,))
                    
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating device capability {device_id}.{capability_name}: {e}")
            return False