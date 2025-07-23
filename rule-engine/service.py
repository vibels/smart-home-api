#!/usr/bin/env python3

from flask import Flask, request, jsonify
import os
import sys
import logging

from api import RuleEngineAPI
from models.condition_tree_builder import ConditionTreeBuilder, TimeFilterBuilder, ActionBuilder, RuleBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
rule_api = RuleEngineAPI()

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

@app.route('/rules', methods=['POST'])
def create_rule():
    try:
        data = request.get_json()
        
        required_fields = ['device_id', 'rule_name', 'condition_tree', 'actions']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        result = rule_api.create_rule(
            data['device_id'],
            data['rule_name'], 
            data['condition_tree'],
            data['actions']
        )
        
        status_code = 201 if result['success'] else 400
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Error creating rule: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/rules/<device_id>', methods=['GET'])
def get_rules_for_device(device_id):
    try:
        result = rule_api.get_rules_for_device(device_id)
        status_code = 200 if result['success'] else 404
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Error getting rules for device {device_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/rules/<rule_id>', methods=['PUT'])
def update_rule(rule_id):
    try:
        data = request.get_json()
        
        required_fields = ['device_id', 'rule_name', 'condition_tree', 'actions']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        result = rule_api.update_rule(
            rule_id,
            data['device_id'],
            data['rule_name'],
            data['condition_tree'], 
            data['actions']
        )
        
        status_code = 200 if result['success'] else 404
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Error updating rule {rule_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/rules/<rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    try:
        result = rule_api.delete_rule(rule_id)
        status_code = 200 if result['success'] else 404
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Error deleting rule {rule_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/rules/<rule_id>/toggle', methods=['POST'])
def toggle_rule_enabled(rule_id):
    try:
        result = rule_api.toggle_rule_enabled(rule_id)
        status_code = 200 if result['success'] else 404
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Error toggling rule {rule_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/devices', methods=['GET'])
def get_all_devices():
    try:
        result = rule_api.get_all_devices()
        status_code = 200 if result['success'] else 404
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Error getting all devices: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/devices/<device_id>/capabilities', methods=['GET'])
def get_device_capabilities(device_id):
    try:
        result = rule_api.get_device_capabilities(device_id)
        status_code = 200 if result['success'] else 404
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Error getting capabilities for device {device_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/rules/validate', methods=['POST'])
def validate_condition_tree():
    try:
        data = request.get_json()
        condition_tree = data.get('condition_tree')
        
        if not condition_tree:
            return jsonify({'valid': False, 'error': 'Missing condition_tree'}), 400
        
        is_valid = ConditionTreeBuilder.validate_tree(condition_tree)
        
        return jsonify({'valid': is_valid}), 200
        
    except Exception as e:
        logger.error(f"Error validating condition tree: {e}")
        return jsonify({'valid': False, 'error': str(e)}), 400

@app.route('/rules/builders/operators', methods=['GET'])
def get_supported_operators():
    try:
        operators = {
            'comparison': ['eq', 'neq', 'gt', 'gte', 'lt', 'lte'],
            'logical': ['and', 'or', 'not']
        }
        return jsonify(operators), 200
    except Exception as e:
        logger.error(f"Error getting operators: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/rules/builders/time-filters', methods=['GET'])
def get_time_filter_types():
    try:
        time_filters = {
            'recent': {
                'description': 'Recent time period',
                'fields': ['minutes', 'hours']
            },
            'time_of_day': {
                'description': 'Specific time range during the day',
                'fields': ['start', 'end']
            },
            'days_of_week': {
                'description': 'Specific days of the week',
                'fields': ['days']
            },
            'duration_since': {
                'description': 'Time elapsed since an event',
                'fields': ['duration_type', 'amount']
            }
        }
        return jsonify(time_filters), 200
    except Exception as e:
        logger.error(f"Error getting time filter types: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/rules/builders/actions', methods=['GET'])
def get_action_types():
    try:
        action_types = {
            'toggle': {
                'description': 'Toggle capability on/off or flip state',
                'example': {'on': {'toggle': 'on'}}
            },
            'trigger': {
                'description': 'Trigger an action with optional duration',
                'example': {'open_close': {'trigger': True, 'duration': 15}}
            },
            'absolute_value': {
                'description': 'Set capability to a specific numeric value',
                'example': {'temperature': {'absolute_value': 23.5}}
            },
            'discrete_value': {
                'description': 'Set capability to a specific discrete value',
                'example': {'mode': {'discrete_value': {'key': 'heat'}}}
            }
        }
        return jsonify(action_types), 200
    except Exception as e:
        logger.error(f"Error getting action types: {e}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.getenv('RULE_ENGINE_PORT', 5001))
    app.run(debug=True, host='0.0.0.0', port=port)