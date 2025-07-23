import dash
from dash import html, dcc, Input, Output, State, callback
import requests
import os
import json
from datetime import datetime
from src.config.logger import get_logger
from src.models.sensor import TemperatureModel, HumidityModel, MotionModel, GasModel
from ..utils.condition_tree import (
    render_condition_tree, apply_not_to_node, delete_node_from_tree, 
    add_group_to_node, validate_condition_tree_completeness
)

logger = get_logger(__name__)

RULE_ENGINE_URL = os.getenv('RULE_ENGINE_URL', 'http://localhost:5001')

temp_model = TemperatureModel()
humidity_model = HumidityModel()
motion_model = MotionModel()
gas_model = GasModel()
sensor_models = [temp_model, humidity_model, motion_model, gas_model]

def extract_value_from_container(container, target_id):
    if not container:
        return None
        
    if isinstance(container, dict):
        if container.get('type') == target_id or container.get('id') == target_id:
            return container.get('value')
        for key, value in container.items():
            if isinstance(value, (dict, list)):
                result = extract_value_from_container(value, target_id)
                if result is not None:
                    return result

    elif isinstance(container, list):
        for item in container:
            result = extract_value_from_container(item, target_id)
            if result is not None:
                return result
    
    elif hasattr(container, 'id') and container.id == target_id:
        return getattr(container, 'value', None)
    elif hasattr(container, 'children'):
        return extract_value_from_container(container.children, target_id)
    
    return None

@callback(
    [Output('rule-modal', 'style'),
     Output('rule-device-id', 'data'),
     Output('condition-tree-store', 'data', allow_duplicate=True),
     Output('edit-rule-id', 'data', allow_duplicate=True)],
    Input({'type': 'rule-button', 'index': dash.dependencies.ALL}, 'n_clicks'),
    [State('edit-rule-id', 'data')],
    prevent_initial_call=True
)
def handle_rule_button_click(n_clicks, current_edit_rule_id):
    ctx = dash.callback_context
    if not ctx.triggered or not any(n_clicks or []):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    if current_edit_rule_id is not None:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    try:
        button_dict = json.loads(button_id)
        device_id = button_dict['index']
        return {'display': 'block'}, device_id, {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}, None
    except Exception as e:
        logger.error(f"Error in handle_rule_button_click: {e}")
        return {'display': 'none'}, dash.no_update, dash.no_update, dash.no_update

@callback(
    Output('rule-form-container', 'children'),
    [Input('rule-device-id', 'data'),
     Input('edit-rule-id', 'data')],
    [State('condition-tree-store', 'data')],
    prevent_initial_call=True
)
def create_rule_form(device_id, edit_rule_id, condition_tree_data):
    if not device_id:
        return html.Div("No device selected")
    
    is_editing = edit_rule_id is not None
    form_title = f"Edit Rule for {device_id}" if is_editing else f"Create Rule for {device_id}"
    
    # Pre-populate condition tree display with current data
    tree_data = condition_tree_data if condition_tree_data else {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
    initial_tree_display = render_condition_tree(tree_data)
    
    return html.Div([
        html.H3(form_title),
        html.Div([
            html.Label("Rule Name:"),
            dcc.Input(id='rule-name-input', type='text', placeholder='Enter rule name', style={'width': '100%'})
        ], className='form-group'),
        
        html.Div([
            html.H4("Condition Tree"),
            html.Div([
                html.Div(id='condition-tree-display', children=initial_tree_display),
                html.Div([
                    html.Button('Add AND Group', id='add-and-btn', className='tree-button'),
                    html.Button('Add OR Group', id='add-or-btn', className='tree-button'),
                    html.Button('Add NOT Group', id='add-not-btn', className='tree-button'),
                    html.Button('Reset Tree', id='reset-tree-btn', className='tree-button reset-btn')
                ], className='tree-buttons')
            ], className='condition-tree-builder')
        ], className='form-group'),
        
        html.Div([
            html.H4("Actions"),
            html.Div(id='actions-container', children=[
                html.Div([
                    html.Label("Capability:"),
                    dcc.Dropdown(id='action-capability-dropdown', placeholder='Select capability', options=[])
                ], className='form-row'),
                html.Div([
                    html.Label("Action Type:"),
                    dcc.Dropdown(
                        id='action-type-dropdown',
                        placeholder='Select action type'
                    )
                ], className='form-row'),
                html.Div(id='action-value-container')
            ])
        ], className='form-group'),
        
        html.Div([
            html.Button('Save Rule', id='save-rule-button', className='save-button'),
            html.Button('Cancel', id='cancel-rule-button', className='cancel-button')
        ], className='form-buttons'),
        
        html.Div(id='rule-save-feedback')
    ], className='rule-form')

@callback(
    Output('rule-name-input', 'value'),
    Input('edit-rule-data', 'data'),
    prevent_initial_call=False
)
def populate_rule_name_for_editing(edit_rule_data):
    if not edit_rule_data:
        logger.info("Rule name callback: no edit_rule_data available")
        return dash.no_update
    
    rule_name = edit_rule_data.get('rule_name', '')
    logger.info(f"Populating rule name from store: {rule_name}")
    return rule_name

@callback(
    [Output('action-capability-dropdown', 'value'),
     Output('action-type-dropdown', 'value')],
    [Input('edit-rule-data', 'data'),
     Input('action-capability-dropdown', 'options')],
    prevent_initial_call=True
)
def populate_actions_for_editing(edit_rule_data, capability_options):
    logger.info(f"Action callback triggered with edit_rule_data: {edit_rule_data}, options: {capability_options}")
    
    if not edit_rule_data or not capability_options:
        logger.info("Action callback: no edit_rule_data or options available")
        return dash.no_update, dash.no_update
    
    capability_name = edit_rule_data.get('capability_name')
    action_type = edit_rule_data.get('action_type')
    
    logger.info(f"Populating actions from store: capability={capability_name}, type={action_type}")
    return capability_name, action_type

@callback(
    Output('action-toggle-state', 'value'),
    Input('edit-rule-data', 'data'),
    prevent_initial_call=True
)
def populate_toggle_action_for_editing(edit_rule_data):
    if not edit_rule_data:
        return dash.no_update
    
    actions = edit_rule_data.get('actions', {})
    action_type = edit_rule_data.get('action_type')
    capability_name = edit_rule_data.get('capability_name')
    
    if (action_type == 'toggle' and capability_name and 
        capability_name in actions and 'toggle' in actions[capability_name]):
        toggle_value = actions[capability_name]['toggle']
        logger.info(f"Populating toggle value from store: {toggle_value}")
        return toggle_value
    
    return dash.no_update

@callback(
    Output('action-absolute-value', 'value'),
    Input('edit-rule-data', 'data'),
    prevent_initial_call=True
)
def populate_absolute_action_for_editing(edit_rule_data):
    if not edit_rule_data:
        return dash.no_update
    
    actions = edit_rule_data.get('actions', {})
    action_type = edit_rule_data.get('action_type')
    capability_name = edit_rule_data.get('capability_name')
    
    if (action_type == 'absolute_value' and capability_name and 
        capability_name in actions and 'absolute_value' in actions[capability_name]):
        absolute_value = actions[capability_name]['absolute_value']
        logger.info(f"Populating absolute value from store: {absolute_value}")
        return absolute_value
    
    return dash.no_update

@callback(
    Output('action-trigger-duration', 'value'),
    Input('edit-rule-data', 'data'),
    prevent_initial_call=True
)
def populate_trigger_action_for_editing(edit_rule_data):
    if not edit_rule_data:
        return dash.no_update
    
    actions = edit_rule_data.get('actions', {})
    action_type = edit_rule_data.get('action_type')
    capability_name = edit_rule_data.get('capability_name')
    
    if (action_type == 'trigger' and capability_name and 
        capability_name in actions and 'duration' in actions[capability_name]):
        duration = actions[capability_name]['duration']
        logger.info(f"Populating trigger duration from store: {duration}")
        return duration
    
    return dash.no_update

@callback(
    Output('action-discrete-value', 'value'),
    Input('edit-rule-data', 'data'),
    prevent_initial_call=True
)
def populate_discrete_action_for_editing(edit_rule_data):
    if not edit_rule_data:
        return dash.no_update
    
    actions = edit_rule_data.get('actions', {})
    action_type = edit_rule_data.get('action_type')
    capability_name = edit_rule_data.get('capability_name')
    
    if (action_type == 'discrete_values' and capability_name and 
        capability_name in actions and 'discrete_value' in actions[capability_name]):
        discrete_value = actions[capability_name]['discrete_value']
        logger.info(f"Populating discrete value from store: {discrete_value}")
        return discrete_value
    
    return dash.no_update

@callback(
    Output('condition-tree-display', 'children'),
    Input('condition-tree-store', 'data'),
    prevent_initial_call=False
)
def update_condition_tree_display(tree_data):
    if tree_data is None:
        tree_data = {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
    return render_condition_tree(tree_data)

@callback(
    Output('condition-tree-store', 'data'),
    [Input('add-and-btn', 'n_clicks'), 
     Input('add-or-btn', 'n_clicks'),
     Input('add-not-btn', 'n_clicks'),
     Input('reset-tree-btn', 'n_clicks'),
     Input({'type': 'delete-node', 'node_id': dash.dependencies.ALL}, 'n_clicks'),
     Input({'type': 'apply-not-to-node', 'node_id': dash.dependencies.ALL}, 'n_clicks'),
     Input({'type': 'add-and-to-node', 'node_id': dash.dependencies.ALL}, 'n_clicks'),
     Input({'type': 'add-or-to-node', 'node_id': dash.dependencies.ALL}, 'n_clicks')],
    [State('condition-tree-store', 'data')],
    prevent_initial_call=True
)
def update_condition_tree_data(add_and, add_or, add_not, reset_tree, delete_clicks, apply_not_clicks, add_and_to_node_clicks, add_or_to_node_clicks, current_tree):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    
    trigger = ctx.triggered[0]['prop_id']
    
    if 'reset-tree-btn' in trigger and reset_tree:
        return {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
    
    elif 'add-and-btn' in trigger and add_and:
        new_condition = {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
        return {'type': 'and', 'left': current_tree, 'right': new_condition}
    
    elif 'add-or-btn' in trigger and add_or:
        new_condition = {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
        return {'type': 'or', 'left': current_tree, 'right': new_condition}
    
    elif 'add-not-btn' in trigger and add_not:
        return apply_not_to_node(current_tree, 'root')
    
    elif 'apply-not-to-node' in trigger and any(apply_not_clicks or []):
        try:
            button_info = json.loads(trigger.split('.')[0])
            node_id = button_info.get('node_id', '')
            
            modified_tree = apply_not_to_node(current_tree, node_id)
            return modified_tree
        except Exception as e:
            logger.error(f"Error applying NOT to node: {e}")
            return current_tree
    
    elif 'delete-node' in trigger and any(delete_clicks or []):
        try:
            button_info = json.loads(trigger.split('.')[0])
            node_id = button_info.get('node_id', '')
            
            if node_id == 'root':
                return {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
            else:
                modified_tree = delete_node_from_tree(current_tree, node_id)
                return modified_tree if modified_tree else {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
        except Exception as e:
            logger.error(f"Error deleting node: {e}")
            return {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
    
    elif 'add-and-to-node' in trigger and any(add_and_to_node_clicks or []):
        try:
            button_info = json.loads(trigger.split('.')[0])
            node_id = button_info.get('node_id', '')
            
            modified_tree = add_group_to_node(current_tree, node_id, 'and')
            return modified_tree
        except Exception as e:
            logger.error(f"Error adding AND group to node: {e}")
            return current_tree
    
    elif 'add-or-to-node' in trigger and any(add_or_to_node_clicks or []):
        try:
            button_info = json.loads(trigger.split('.')[0])
            node_id = button_info.get('node_id', '')
            
            modified_tree = add_group_to_node(current_tree, node_id, 'or')
            return modified_tree
        except Exception as e:
            logger.error(f"Error adding OR group to node: {e}")
            return current_tree
    
    return dash.no_update

@callback(
    Output('device-capabilities-store', 'data'),
    Input('rule-device-id', 'data'),
    prevent_initial_call=True
)
def populate_capability_store(device_id):
    if not device_id:
        return dash.no_update
    
    try:
        response = requests.get(f'{RULE_ENGINE_URL}/devices/{device_id}/capabilities', timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result['success']:
                capabilities = result['capabilities']
                return capabilities
        return []
    except Exception as e:
        logger.error(f"Error getting capability options: {e}")
        return []

@callback(
    Output('action-capability-dropdown', 'options'),
    Input('device-capabilities-store', 'data'),
    prevent_initial_call=True
)
def update_action_capability_options(capabilities_data):
    if not capabilities_data:
        logger.info("Action capability options: no capabilities data")
        return []
    
    options = [{'label': cap['label'], 'value': cap['name']} for cap in capabilities_data]
    logger.info(f"Action capability options populated: {options}")
    return options

@callback(
    Output('action-type-dropdown', 'options'),
    [Input('action-capability-dropdown', 'value')],
    [State('device-capabilities-store', 'data')]
)
def update_action_type_options(selected_capability, capabilities_data):
    logger.info(f"Action type options callback: capability={selected_capability}, capabilities_data={capabilities_data}")
    
    if not selected_capability or not capabilities_data:
        logger.info("Action type options: missing capability or data")
        return []
    
    selected_cap = next((cap for cap in capabilities_data if cap['name'] == selected_capability), None)
    if not selected_cap:
        logger.info(f"Action type options: capability {selected_capability} not found")
        return []
    
    capability_type = selected_cap['type']
    
    type_mapping = {
        'toggle': [{'label': 'Toggle On/Off', 'value': 'toggle'}],
        'absolute_value': [{'label': 'Set Value', 'value': 'absolute_value'}],
        'trigger': [{'label': 'Trigger', 'value': 'trigger'}],
        'discrete_values': [{'label': 'Set Mode', 'value': 'discrete_values'}]
    }
    
    options = type_mapping.get(capability_type, [])
    logger.info(f"Action type options populated: {options}")
    return options

@callback(
    Output('action-value-container', 'children'),
    [Input('action-type-dropdown', 'value'),
     Input('action-capability-dropdown', 'value')],
    [State('device-capabilities-store', 'data')]
)
def update_action_value_options(action_type, selected_capability, capabilities_data):
    if action_type == 'toggle':
        return html.Div([
            html.Label("Toggle State:"),
            dcc.Dropdown(
                id='action-toggle-state',
                options=[
                    {'label': 'Turn On', 'value': 'on'},
                    {'label': 'Turn Off', 'value': 'off'},
                    {'label': 'Toggle', 'value': 'toggle'}
                ],
                value='on'
            )
        ], className='form-row')
    elif action_type == 'absolute_value':
        return html.Div([
            html.Label("Value:"),
            dcc.Input(id='action-absolute-value', type='number', placeholder='Enter numeric value')
        ], className='form-row')
    elif action_type == 'trigger':
        return html.Div([
            html.Label("Duration (seconds):"),
            dcc.Input(id='action-trigger-duration', type='number', placeholder='Duration in seconds', value=30)
        ], className='form-row')
    elif action_type == 'discrete_values':
        if selected_capability and capabilities_data:
            selected_cap = next((cap for cap in capabilities_data if cap['name'] == selected_capability), None)
            if selected_cap and 'values' in selected_cap.get('config', {}):
                available_values = selected_cap['config']['values']
                options = [{'label': value.replace('_', ' ').title(), 'value': value} for value in available_values]
                return html.Div([
                    html.Label("Value:"),
                    dcc.Dropdown(
                        id='action-discrete-value',
                        options=options,
                        placeholder='Select value'
                    )
                ], className='form-row')
        
        return html.Div([
            html.Label("Value:"),
            dcc.Input(id='action-discrete-value', type='text', placeholder='Enter mode/state value')
        ], className='form-row')
    return html.Div()

@callback(
    [Output('rule-save-feedback', 'children'),
     Output('rule-modal', 'style', allow_duplicate=True),
     Output('condition-tree-modal', 'style', allow_duplicate=True),
     Output('view-rules-modal', 'style', allow_duplicate=True)],
    Input('save-rule-button', 'n_clicks'),
    [State('rule-device-id', 'data'),
     State('edit-rule-id', 'data'),
     State('rule-name-input', 'value'),
     State('condition-tree-store', 'data'),
     State('action-capability-dropdown', 'value'),
     State('action-type-dropdown', 'value'),
     State('action-value-container', 'children')],
    prevent_initial_call=True
)
def save_rule(n_clicks, device_id, edit_rule_id, rule_name, condition_tree, capability, action_type, action_container):
    logger.info(f"Save rule callback triggered: n_clicks={n_clicks}, device_id={device_id}, rule_name={rule_name}")
    if not n_clicks:
        logger.info("Save rule callback returning early - no button click")
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    if not device_id or not rule_name:
        logger.info("Save rule callback returning early - missing parameters")
        return dash.no_update, {'display': 'none'}, {'display': 'none'}, {'display': 'none'}
    
    try:
        if not validate_condition_tree_completeness(condition_tree):
            return html.Div("Please ensure all conditions have sensor device, operator, and value set.", 
                          className="error-message"), {'display': 'none'}, {'display': 'none'}, {'display': 'none'}
        
        actions = {}
        if capability and action_type:
            logger.info(f"Processing action: capability={capability}, type={action_type}, is_editing={edit_rule_id is not None}")
            logger.info(f"Action container type: {type(action_container)}, content: {action_container}")
            
            # Extract the action value based on action type
            target_id = f'action-{action_type.replace("_", "-")}'
            if action_type == 'discrete_values':
                target_id = 'action-discrete-value'
            elif action_type == 'trigger':
                target_id = 'action-trigger-duration'
            elif action_type == 'absolute_value':
                target_id = 'action-absolute-value'
            elif action_type == 'toggle':
                target_id = 'action-toggle-state'
                
            logger.info(f"Looking for target_id: {target_id}")
            action_value = extract_value_from_container(action_container, target_id)
            logger.info(f"Extracted value for {target_id}: {action_value}")
            
            if action_type == 'toggle':
                actions[capability] = {'toggle': action_value or 'on'}
            elif action_type == 'absolute_value':
                actions[capability] = {'absolute_value': action_value if action_value is not None else 0}
            elif action_type == 'trigger':
                actions[capability] = {'trigger': True, 'duration': action_value or 30}
            elif action_type == 'discrete_values':
                actions[capability] = {'discrete_value': {'key': action_value or 'default'}}
        
        logger.info(f"Final actions payload: {actions}")
        
        payload = {
            'device_id': device_id,
            'rule_name': rule_name,
            'condition_tree': condition_tree,
            'actions': actions
        }
        
        # Determine if this is an update or create operation
        is_editing = edit_rule_id is not None
        
        if is_editing:
            # Update existing rule
            response = requests.put(f'{RULE_ENGINE_URL}/rules/{edit_rule_id}', json=payload, timeout=10)
            success_msg = "Rule updated successfully!"
        else:
            # Create new rule
            response = requests.post(f'{RULE_ENGINE_URL}/rules', json=payload, timeout=10)
            success_msg = "Rule created successfully!"
        
        if response.status_code in [200, 201]:
            return html.Div(success_msg, className="success-message"), {'display': 'none'}, {'display': 'none'}, {'display': 'none'}
        else:
            error_msg = response.json().get('message', f'Failed to {"update" if is_editing else "create"} rule')
            return html.Div(error_msg, className="error-message"), {'display': 'none'}, {'display': 'none'}, {'display': 'none'}
            
    except Exception as e:
        logger.error(f"Error saving rule: {e}")
        return html.Div(f"Error: {str(e)}", className="error-message"), {'display': 'none'}, {'display': 'none'}, {'display': 'none'}

@callback(
    Output('rule-modal', 'style', allow_duplicate=True),
    Input('cancel-rule-button', 'n_clicks'),
    prevent_initial_call=True
)
def cancel_rule_creation(n_clicks):
    if n_clicks:
        return {'display': 'none'}
    return dash.no_update