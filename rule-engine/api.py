from typing import Dict, Any
from models.actionable_models import ActionableDeviceModel
import logging

logger = logging.getLogger(__name__)


class RuleEngineAPI:
    def __init__(self):
        self.actionable_model = ActionableDeviceModel()
    
    def create_rule(self, device_id: str, rule_name: str, condition_tree: Dict[str, Any], actions: Dict[str, Any]) -> Dict[str, Any]:
        try:
            success = self.actionable_model.add_rule(device_id, rule_name, condition_tree, actions)
            
            if success:
                return {'success': True, 'message': 'Rule created successfully'}
            else:
                return {'success': False, 'message': 'Failed to create rule'}
                
        except Exception as e:
            logger.error(f"Error creating rule: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def get_rules_for_device(self, device_id: str) -> Dict[str, Any]:
        try:
            rules = self.actionable_model.get_rules_for_device(device_id)
            return {'success': True, 'rules': rules}
        except Exception as e:
            logger.error(f"Error getting rules for device {device_id}: {e}")
            return {'success': False, 'message': f'Error: {str(e)}', 'rules': []}
    
    def update_rule(self, rule_id: str, device_id: str, rule_name: str, condition_tree: Dict[str, Any], actions: Dict[str, Any]) -> Dict[str, Any]:
        try:
            success = self.actionable_model.update_rule(rule_id, rule_name, condition_tree, actions)
            
            if success:
                return {'success': True, 'message': 'Rule updated successfully'}
            else:
                return {'success': False, 'message': 'Failed to update rule'}
                
        except Exception as e:
            logger.error(f"Error updating rule {rule_id}: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def delete_rule(self, rule_id: str) -> Dict[str, Any]:
        try:
            success = self.actionable_model.delete_rule(rule_id)
            
            if success:
                return {'success': True, 'message': 'Rule deleted successfully'}
            else:
                return {'success': False, 'message': 'Rule not found'}
                
        except Exception as e:
            logger.error(f"Error deleting rule {rule_id}: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def get_all_devices(self) -> Dict[str, Any]:
        try:
            devices = self.actionable_model.get_all_devices()
            device_list = [
                {
                    'device_id': device.device_id,
                    'device_type': device.device_type,
                    'location': device.location,
                    'name': device.name,
                    'status': device.status.value,
                    'capabilities': [
                        {
                            'name': cap.name,
                            'capability_type': cap.capability_type.value,
                            'config': cap.config,
                            'current_value': cap.current_value
                        }
                        for cap in device.capabilities
                    ],
                    'last_updated': device.last_updated.isoformat()
                }
                for device in devices
            ]
            return {'success': True, 'devices': device_list}
        except Exception as e:
            logger.error(f"Error getting all devices: {e}")
            return {'success': False, 'message': f'Error: {str(e)}', 'devices': []}

    def get_device_capabilities(self, device_id: str) -> Dict[str, Any]:
        try:
            devices = self.actionable_model.get_all_devices()
            device = next((d for d in devices if d.device_id == device_id), None)
            
            if device:
                capabilities = [
                    {
                        'name': cap.name,
                        'label': cap.name.replace('_', ' ').title(),
                        'type': cap.capability_type.value,
                        'config': cap.config,
                        'current_value': cap.current_value
                    }
                    for cap in device.capabilities
                ]
                return {'success': True, 'capabilities': capabilities}
            else:
                return {'success': False, 'message': 'Device not found', 'capabilities': []}
        except Exception as e:
            logger.error(f"Error getting device capabilities: {e}")
            return {'success': False, 'message': f'Error: {str(e)}', 'capabilities': []}