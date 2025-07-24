import dash
from dash import html, dcc, Input, Output, State, callback
import json
import copy
from src.config.logger import get_logger
from . import sensor_models

logger = get_logger(__name__)

@callback(
    [Output('edit-condition-modal', 'style'),
     Output('edit-node-id', 'data'),
     Output('edit-tree-data-store', 'data')],
    Input({'type': 'edit-node', 'node_id': dash.dependencies.ALL}, 'n_clicks'),
    [State('condition-tree-store', 'data')],
    prevent_initial_call=True
)
def open_edit_modal(n_clicks_list, current_tree_data):
    if not any(n_clicks_list or []):
        return dash.no_update, dash.no_update, dash.no_update
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    node_id = eval(button_id)['node_id']
    
    logger.info(f"Opening edit modal for node {node_id} with tree data: {current_tree_data}")
    
    return {'display': 'block'}, node_id, current_tree_data

@callback(
    Output('edit-condition-form', 'children'),
    Input('edit-node-id', 'data'),
    [State('condition-tree-store', 'data'),
     State('edit-tree-data-store', 'data')],
    prevent_initial_call=True
)
def create_edit_form(node_id, tree_data, edit_tree_data):
    if not node_id:
        return html.Div()
    
    active_tree_data = edit_tree_data if edit_tree_data else tree_data
    
    if not active_tree_data:
        return html.Div("No tree data available")
    
    logger.info(f"Edit form called with node_id: {node_id}")
    logger.info(f"Tree data received: {active_tree_data}")
    logger.info(f"Edit tree data: {edit_tree_data}")
    
    def find_node_by_id(node, target_id, current_id="root"):
        logger.info(f"Searching for target_id='{target_id}', current_id='{current_id}', node_type='{node.get('type')}'")
        
        if current_id == target_id:
            logger.info(f"Found target node: {node}")
            return node
        
        if node.get('type') in ['and', 'or']:
            left_result = find_node_by_id(node.get('left', {}), target_id, f"{current_id}_left")
            if left_result:
                return left_result
            right_result = find_node_by_id(node.get('right', {}), target_id, f"{current_id}_right")
            if right_result:
                return right_result
        elif node.get('type') == 'not':
            child_result = find_node_by_id(node.get('child', {}), target_id, f"{current_id}_child")
            if child_result:
                return child_result
        
        return None
    
    node_to_edit = find_node_by_id(active_tree_data, node_id)
    
    if not node_to_edit or node_to_edit.get('type') != 'condition':
        return html.Div("Cannot edit this node type")
    
    try:
        edit_devices = []
        for model in sensor_models:
            devices = model.get_devices()
            edit_devices.extend(devices)
        unique_edit_devices = list(dict.fromkeys(edit_devices))
        sensor_options = [{'label': device, 'value': device} for device in unique_edit_devices]
    except Exception as e:
        logger.error(f"Error getting sensor devices for edit form: {e}")
        sensor_options = []
    
    return html.Div([
        html.H3("Edit Condition"),
        html.Div([
            html.Label("Sensor Device:"),
            dcc.Dropdown(
                id='edit-sensor-device',
                options=sensor_options,
                value=node_to_edit.get('sensor_device', ''),
                placeholder='Select sensor device',
                style={'width': '100%'}
            )
        ], className='form-group'),
        
        html.Div([
            html.Label("Operator:"),
            dcc.Dropdown(
                id='edit-operator',
                options=[
                    {'label': 'Greater than or equal (≥)', 'value': 'gte'},
                    {'label': 'Less than or equal (≤)', 'value': 'lte'},
                    {'label': 'Greater than (>)', 'value': 'gt'},
                    {'label': 'Less than (<)', 'value': 'lt'},
                    {'label': 'Equal to (=)', 'value': 'eq'},
                    {'label': 'Not equal to (≠)', 'value': 'ne'}
                ],
                value=node_to_edit.get('operator', 'gte'),
                style={'width': '100%'}
            )
        ], className='form-group'),
        
        html.Div([
            html.Label("Value:"),
            dcc.Input(
                id='edit-value',
                type='number',
                value=node_to_edit.get('value', 0),
                style={'width': '100%'}
            )
        ], className='form-group'),
        
        html.Div([
            html.Button('Save Changes', id='save-edit-button', className='btn btn-primary'),
            html.Button('Cancel', id='cancel-edit-button', className='btn btn-secondary')
        ], className='modal-buttons')
    ])

@callback(
    [Output('condition-tree-store', 'data', allow_duplicate=True),
     Output('edit-tree-data-store', 'data', allow_duplicate=True),
     Output('edit-condition-modal', 'style', allow_duplicate=True)],
    Input('save-edit-button', 'n_clicks'),
    [State('edit-node-id', 'data'),
     State('condition-tree-store', 'data'),
     State('edit-tree-data-store', 'data'),
     State('edit-sensor-device', 'value'),
     State('edit-operator', 'value'),
     State('edit-value', 'value')],
    prevent_initial_call=True
)
def save_edited_condition(n_clicks, node_id, tree_data, edit_tree_data, sensor_device, operator, value):
    if not n_clicks or not node_id:
        return dash.no_update, dash.no_update, dash.no_update
    
    logger.info(f"Saving condition node {node_id} with sensor_device={sensor_device}, operator={operator}, value={value}")
    
    active_tree_data = edit_tree_data if edit_tree_data else tree_data
    if not active_tree_data:
        return dash.no_update, dash.no_update, {'display': 'none'}
    
    logger.info(f"Original tree data: {active_tree_data}")
    
    def update_node_by_id(node, target_id, current_id="root"):
        if current_id == target_id:
            if node.get('type') == 'condition':
                logger.info(f"Updating node at {current_id} from {node} to sensor_device={sensor_device}, operator={operator}, value={value}")
                node.update({
                    'sensor_device': sensor_device or '',
                    'operator': operator or 'gte',
                    'value': value if value is not None else 0
                })
                logger.info(f"Node after update: {node}")
            return True
        
        if node.get('type') in ['and', 'or']:
            if update_node_by_id(node.get('left', {}), target_id, f"{current_id}_left"):
                return True
            if update_node_by_id(node.get('right', {}), target_id, f"{current_id}_right"):
                return True
        elif node.get('type') == 'not':
            if update_node_by_id(node.get('child', {}), target_id, f"{current_id}_child"):
                return True
        
        return False
    
    # Use deep copy to avoid modifying the original tree
    updated_tree = copy.deepcopy(active_tree_data)
    success = update_node_by_id(updated_tree, node_id)
    
    logger.info(f"Update success: {success}")
    logger.info(f"Updated tree data: {updated_tree}")
    
    # Always update the main condition-tree-store so the display refreshes
    return updated_tree, dash.no_update, {'display': 'none'}

@callback(
    Output('edit-modal-devices-store', 'data'),
    Input('edit-condition-modal', 'style'),
    prevent_initial_call=False
)
def populate_edit_modal_devices_store(modal_style):
    if modal_style and modal_style.get('display') == 'block':
        try:
            edit_devices = []
            for model in sensor_models:
                devices = model.get_devices()
                edit_devices.extend(devices)
            
            unique_edit_devices = list(dict.fromkeys(edit_devices))
            return unique_edit_devices
        except Exception as e:
            logger.error(f"Error populating edit modal devices store: {e}")
            return []
    return []

@callback(
    Output('edit-sensor-device', 'options'),
    Input('edit-modal-devices-store', 'data'),
    prevent_initial_call=False
)
def populate_edit_sensor_dropdown(devices_list):
    if devices_list:
        return [{'label': device, 'value': device} for device in devices_list]
    return []

@callback(
    Output('edit-condition-modal', 'style', allow_duplicate=True),
    Input('cancel-edit-button', 'n_clicks'),
    prevent_initial_call=True
)
def cancel_edit(n_clicks):
    if n_clicks:
        return {'display': 'none'}
    return dash.no_update