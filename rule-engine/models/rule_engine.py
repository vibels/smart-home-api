from typing import Dict, Any
from datetime import datetime, timedelta
from durable.lang import *
from .actionable_models import ActionableDeviceModel
import logging

logger = logging.getLogger(__name__)


class SmartHomeRuleEngine:
    def __init__(self):
        self.actionable_model = ActionableDeviceModel()
        self.active_rulesets = {}

    def create_rule_from_config(self, rule_id: str, device_id: str, rule_config: Dict[str, Any]):
        try:
            condition_tree = rule_config.get('condition_tree')
            actions = rule_config.get('actions', {})
            
            if not condition_tree:
                logger.error(f"No condition_tree provided for rule {rule_id}")
                return False
            
            ruleset_name = f"rule_{rule_id}_{device_id}"
            
            with ruleset(ruleset_name):
                predicate = self._build_predicate_from_tree(condition_tree)
                
                @when_all(predicate)
                def execute_action(c):
                    try:
                        logger.info(f"Rule {rule_id} triggered for device {device_id}")
                        self._execute_action(device_id, actions)
                    except Exception as e:
                        logger.error(f"Error executing action for rule {rule_id}: {e}")
            
            self.active_rulesets[rule_id] = {
                'ruleset_name': ruleset_name,
                'device_id': device_id,
                'config': rule_config
            }
            
            logger.info(f"Created rule {rule_id} for device {device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating rule {rule_id}: {e}")
            return False

    def _build_predicate_from_tree(self, node: Dict[str, Any]):
        node_type = node.get('type')
        
        if node_type == 'condition':
            return self._create_leaf_condition(node)
        elif node_type == 'and':
            left = self._build_predicate_from_tree(node['left'])
            right = self._build_predicate_from_tree(node['right'])
            return left & right
        elif node_type == 'or':
            left = self._build_predicate_from_tree(node['left'])
            right = self._build_predicate_from_tree(node['right'])
            return left | right
        elif node_type == 'not':
            child = self._build_predicate_from_tree(node['child'])
            return ~child
        else:
            raise ValueError(f"Unknown node type: {node_type}")

    def _create_leaf_condition(self, condition: Dict[str, Any]):
        sensor_device = condition['sensor_device']
        operator = condition['operator']
        value = condition['value']
        time_filter_config = condition.get('time_filter')
        
        device_filter = m.sensor_device == sensor_device
        
        if operator == 'gte':
            value_filter = m.value >= value
        elif operator == 'lte':
            value_filter = m.value <= value
        elif operator == 'gt':
            value_filter = m.value > value
        elif operator == 'lt':
            value_filter = m.value < value
        elif operator == 'eq':
            value_filter = m.value == value
        elif operator == 'neq':
            value_filter = m.value != value
        else:
            raise ValueError(f"Unknown operator: {operator}")
        
        time_filter = self._create_time_filter(time_filter_config)
        return device_filter & value_filter & time_filter

    def _create_time_filter(self, time_filter_config: Dict[str, Any]):
        if not time_filter_config:
            return True
        
        filter_type = time_filter_config.get('type')
        
        if filter_type == 'recent':
            if 'minutes' in time_filter_config:
                minutes = time_filter_config['minutes']
                return m.timestamp > (datetime.now() - timedelta(minutes=minutes)).isoformat()
            elif 'hours' in time_filter_config:
                hours = time_filter_config['hours']
                return m.timestamp > (datetime.now() - timedelta(hours=hours)).isoformat()
        
        elif filter_type == 'time_of_day':
            now = datetime.now()
            start_time = time_filter_config.get('start', '00:00')
            end_time = time_filter_config.get('end', '23:59')
            
            start_dt = datetime.strptime(f"{now.date()} {start_time}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{now.date()} {end_time}", "%Y-%m-%d %H:%M")
            
            return (m.timestamp >= start_dt.isoformat()) & (m.timestamp <= end_dt.isoformat())
        
        elif filter_type == 'days_of_week':
            current_day = datetime.now().strftime('%A').lower()
            days = [day.lower() for day in time_filter_config.get('days', [])]
            if current_day in days:
                return m.timestamp > (datetime.now() - timedelta(minutes=5)).isoformat()
            else:
                return False
        
        elif filter_type == 'duration_since':
            duration_type = time_filter_config.get('duration_type', 'minutes')
            amount = time_filter_config.get('amount', 5)
            
            if duration_type == 'minutes':
                return m.timestamp > (datetime.now() - timedelta(minutes=amount)).isoformat()
            elif duration_type == 'hours':
                return m.timestamp > (datetime.now() - timedelta(hours=amount)).isoformat()
            elif duration_type == 'days':
                return m.timestamp > (datetime.now() - timedelta(days=amount)).isoformat()
        
        return m.timestamp > (datetime.now() - timedelta(minutes=5)).isoformat()

    def _execute_action(self, device_id: str, actions: Dict[str, Any]):
        try:
            for capability, action_config in actions.items():
                if isinstance(action_config, dict):
                    if 'toggle' in action_config:
                        state = action_config['toggle']
                        if state == 'on':
                            self.actionable_model.update_device_capability(device_id, capability, True)
                        elif state == 'off':
                            self.actionable_model.update_device_capability(device_id, capability, False)
                        else:
                            current_devices = self.actionable_model.get_all_devices()
                            device = next((d for d in current_devices if d.device_id == device_id), None)
                            if device:
                                cap = next((c for c in device.capabilities if c.name == capability), None)
                                if cap:
                                    new_value = not cap.current_value
                                    self.actionable_model.update_device_capability(device_id, capability, new_value)
                    
                    elif 'trigger' in action_config:
                        trigger_time = datetime.now().isoformat()
                        if 'duration' in action_config:
                            trigger_time = f"{trigger_time}:duration:{action_config['duration']}"
                        self.actionable_model.update_device_capability(device_id, capability, trigger_time)
                    
                    elif 'absolute_value' in action_config:
                        value = action_config['absolute_value']
                        self.actionable_model.update_device_capability(device_id, capability, value)
                    
                    elif 'discrete_value' in action_config:
                        discrete_config = action_config['discrete_value']
                        for key, value in discrete_config.items():
                            self.actionable_model.update_device_capability(device_id, capability, value)
                            break
                
        except Exception as e:
            logger.error(f"Error executing action: {e}")

    def process_sensor_data(self, sensor_device: str, sensor_type: str, value: float, timestamp: datetime):
        try:
            fact = {
                'sensor_device': sensor_device,
                'sensor_type': sensor_type,
                'value': value,
                'timestamp': timestamp.isoformat()
            }
            
            for rule_id, rule_info in self.active_rulesets.items():
                ruleset_name = rule_info['ruleset_name']
                try:
                    assert_fact(ruleset_name, fact)
                except Exception as e:
                    logger.error(f"Error asserting fact to {ruleset_name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing sensor data: {e}")

    @staticmethod
    def create_simple_condition_tree(sensor_device: str, operator: str, value: float, time_minutes: int = 5):
        return {
            'type': 'condition',
            'sensor_device': sensor_device,
            'operator': operator,
            'value': value,
            'time_minutes': time_minutes
        }

    @staticmethod
    def create_and_tree(left_tree: Dict, right_tree: Dict):
        return {
            'type': 'and',
            'left': left_tree,
            'right': right_tree
        }

    @staticmethod 
    def create_or_tree(left_tree: Dict, right_tree: Dict):
        return {
            'type': 'or',
            'left': left_tree,
            'right': right_tree
        }

    @staticmethod
    def create_not_tree(child_tree: Dict):
        return {
            'type': 'not',
            'child': child_tree
        }

    def load_rules_from_database(self):
        try:
            devices = self.actionable_model.get_all_devices()
            rule_count = 0
            
            for device in devices:
                rules = self.actionable_model.get_rules_for_device(device.device_id)
                for rule in rules:
                    success = self.create_rule_from_config(
                        str(rule['rule_id']),
                        device.device_id,
                        {
                            'condition_tree': rule['conditions'],
                            'actions': rule['actions']
                        }
                    )
                    if success:
                        rule_count += 1
            
            logger.info(f"Loaded {rule_count} rules from database")
            return rule_count
            
        except Exception as e:
            logger.error(f"Error loading rules from database: {e}")
            return 0