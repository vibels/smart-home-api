from typing import Dict, Any, List, Union


class ConditionTreeBuilder:
    @staticmethod
    def condition(sensor_device: str, operator: str, value: Any, time_filter: Dict[str, Any] = None) -> Dict[str, Any]:
        condition = {
            'type': 'condition',
            'sensor_device': sensor_device,
            'operator': operator,
            'value': value
        }
        
        if time_filter:
            condition['time_filter'] = time_filter
        
        return condition
    
    @staticmethod
    def and_op(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'type': 'and',
            'left': left,
            'right': right
        }
    
    @staticmethod
    def or_op(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'type': 'or',
            'left': left,
            'right': right
        }
    
    @staticmethod
    def not_op(child: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'type': 'not',
            'child': child
        }
    
    @staticmethod
    def validate_tree(tree: Dict[str, Any]) -> bool:
        try:
            node_type = tree.get('type')
            
            if node_type == 'condition':
                return all(field in tree for field in ['sensor_device', 'operator', 'value'])
            elif node_type in ['and', 'or']:
                return ('left' in tree and 'right' in tree and
                        ConditionTreeBuilder.validate_tree(tree['left']) and
                        ConditionTreeBuilder.validate_tree(tree['right']))
            elif node_type == 'not':
                return ('child' in tree and
                        ConditionTreeBuilder.validate_tree(tree['child']))
            else:
                return False
        except Exception:
            return False


class TimeFilterBuilder:
    @staticmethod
    def recent_minutes(minutes: int) -> Dict[str, Any]:
        return {
            'type': 'recent',
            'minutes': minutes
        }
    
    @staticmethod
    def recent_hours(hours: int) -> Dict[str, Any]:
        return {
            'type': 'recent',
            'hours': hours
        }
    
    @staticmethod
    def time_of_day(start_time: str, end_time: str) -> Dict[str, Any]:
        return {
            'type': 'time_of_day',
            'start': start_time,
            'end': end_time
        }
    
    @staticmethod
    def days_of_week(days: List[str]) -> Dict[str, Any]:
        return {
            'type': 'days_of_week',
            'days': days
        }
    
    @staticmethod
    def date_range(start_date: str, end_date: str) -> Dict[str, Any]:
        return {
            'type': 'date_range',
            'start_date': start_date,
            'end_date': end_date
        }
    
    @staticmethod
    def duration_since(duration_type: str, amount: int) -> Dict[str, Any]:
        return {
            'type': 'duration_since',
            'duration_type': duration_type,
            'amount': amount
        }


class ActionBuilder:
    @staticmethod
    def toggle_action(capability: str, state: str) -> Dict[str, Any]:
        return {capability: {"toggle": state}}
    
    @staticmethod
    def trigger_action(capability: str, duration: int = None) -> Dict[str, Any]:
        action = {"trigger": True}
        if duration is not None:
            action["duration"] = duration
        return {capability: action}
    
    @staticmethod
    def absolute_value_action(capability: str, value: float) -> Dict[str, Any]:
        return {capability: {"absolute_value": value}}
    
    @staticmethod
    def discrete_value_action(capability: str, key: str, value: str) -> Dict[str, Any]:
        return {capability: {"discrete_value": {key: value}}}


class RuleBuilder:
    @staticmethod
    def create_rule(device_id: str, rule_name: str, condition_tree: Dict[str, Any], actions: Dict[str, Any]) -> Dict[str, Any]:
        if not ConditionTreeBuilder.validate_tree(condition_tree):
            raise ValueError("Invalid condition tree structure")
        
        return {
            'device_id': device_id,
            'rule_name': rule_name,
            'condition_tree': condition_tree,
            'actions': actions
        }