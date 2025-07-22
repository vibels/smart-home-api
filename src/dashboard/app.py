import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import plotly.express as px
from datetime import datetime
import pandas as pd

from src.models.sensor import TemperatureModel, HumidityModel, MotionModel, GasModel
from src.config.logger import get_logger
import requests
import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any
import json
import warnings
from influxdb_client.client.warnings import MissingPivotFunction

warnings.simplefilter("ignore", MissingPivotFunction)
logger = get_logger(__name__)

app = dash.Dash(__name__, suppress_callback_exceptions=True)

temp_model = TemperatureModel()
humidity_model = HumidityModel()
motion_model = MotionModel()
gas_model = GasModel()
sensor_models = [temp_model, humidity_model, motion_model, gas_model]

RULE_ENGINE_URL = os.getenv('RULE_ENGINE_URL', 'http://localhost:5001')

@dataclass
class DeviceCapabilityDTO:
    name: str
    capability_type: str
    config: Dict[str, Any]
    current_value: Any

@dataclass  
class ActionableDeviceDTO:
    device_id: str
    device_type: str
    location: str
    name: str
    status: str
    capabilities: List[DeviceCapabilityDTO]
    last_updated: str

app.layout = html.Div([
    dcc.Store(id='selected-device', data=[]),
    dcc.Store(id='available-options', data=[]),
    dcc.Store(id='edit-modal-devices-store', data=[]),
    dcc.Store(id='condition-tree-store', data={'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}),
    
    html.H1("Smart Home Dashboard", className="main-header"),

    html.Div([
        html.Button("Sensor Devices", id="nav-sensors", className="nav-button active", n_clicks=0),
        html.Button("Charts", id="nav-charts", className="nav-button", n_clicks=0),
        html.Button("Actionable Devices", id="nav-actionable", className="nav-button", n_clicks=0),
    ], className="navigation"),
    
    dcc.Store(id='active-tab', data='sensors'),
    
    html.Div(id='tab-content'),
    
    dcc.Store(id='rule-device-id', data=None),
    
    html.Div(id='rule-modal', children=[
        html.Div(id='rule-form-container', className='modal-content')
    ], className='modal', style={'display': 'none'}),

    html.Div(id='edit-condition-modal', children=[
        html.Div(id='edit-condition-form', className='modal-content')
    ], className='modal', style={'display': 'none'}),
    
    dcc.Store(id='edit-node-id', data=None),
    
    dcc.Interval(
        id='interval-component',
        interval=30*1000,
        n_intervals=0
    )
], className="dashboard")

@app.callback(
    [Output('active-tab', 'data'),
     Output('nav-sensors', 'className'),
     Output('nav-charts', 'className'),
     Output('nav-actionable', 'className')],
    [Input('nav-sensors', 'n_clicks'),
     Input('nav-charts', 'n_clicks'),
     Input('nav-actionable', 'n_clicks')],
    prevent_initial_call=True
)
def update_active_tab(sensors_clicks, charts_clicks, actionable_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return 'sensors', 'nav-button active', 'nav-button', 'nav-button'
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'nav-sensors':
        return 'sensors', 'nav-button active', 'nav-button', 'nav-button'
    elif button_id == 'nav-charts':
        return 'charts', 'nav-button', 'nav-button active', 'nav-button'
    elif button_id == 'nav-actionable':
        return 'actionable', 'nav-button', 'nav-button', 'nav-button active'
    
    return 'sensors', 'nav-button active', 'nav-button', 'nav-button'


@app.callback(
    Output('tab-content', 'children'),
    Input('active-tab', 'data'),
    [State('selected-device', 'data'), State('available-options', 'data')]
)
def render_tab_content(active_tab, selected_devices, available_options):

    if active_tab == 'sensors':
        return html.Div(id='sensor-devices-container')
    elif active_tab == 'charts':
        return html.Div([
            html.Div([
                html.Div([
                    html.Label("Select Devices:"),
                    dcc.Dropdown(
                        id='device-dropdown',
                        options=available_options or [],
                        value=selected_devices or [],
                        multi=True,
                        placeholder="Select devices (empty = all devices)",
                        clearable=True,
                        searchable=True
                    )
                ], className="dropdown-container"),
                html.Div([
                    html.Label("Select Time Range:"),
                    dcc.Dropdown(
                        id='time-range-dropdown',
                        options=[
                            {'label': 'Last Hour', 'value': '-1h'},
                            {'label': 'Last 6 Hours', 'value': '-6h'},
                            {'label': 'Last 12 Hours', 'value': '-12h'},
                            {'label': 'Last 24 Hours', 'value': '-24h'},
                            {'label': 'Last Week', 'value': '-7d'}
                        ],
                        value='-1h'
                    )
                ], className="dropdown-container")
            ], className="controls"),
            html.Div([
                dcc.Graph(id='temperature-line-chart')
            ], className="chart-container", id='temperature-line-chart-container', style={'display': 'none'}),
            html.Div([
                dcc.Graph(id='temperature-histogram')
            ], className="chart-container", id='temperature-histogram-container', style={'display': 'none'})
        ], id='charts-content')
    elif active_tab == 'actionable':
        return html.Div([
            html.Div(id='actionable-devices-container')
        ])

@app.callback(
    Output('sensor-devices-container', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_sensor_devices(n):
    try:
        all_data = []
        for model in sensor_models:
            data = model.get_latest_device_data()
            if not data.empty:
                all_data.append(data)
        
        if not all_data:
            return html.Div("No sensor devices found", className="no-data")
            
        latest_data = pd.concat(all_data, ignore_index=True)
        
        device_cards = []
        for _, row in latest_data.iterrows():
            device_id = row['device_id']
            value = row['value']
            timestamp = row['_time']
            location = row['location'] if row['location'] else 'Unknown'
            sensor_type = row.get('type', 'Unknown')
            
            units = {'temperature': '°C', 'humidity': '%', 'motion': '', 'gas': 'ppm'}
            unit = units.get(sensor_type, '')
            
            time_str = timestamp.strftime('%H:%M:%S') if timestamp else 'Unknown'
            date_str = timestamp.strftime('%Y-%m-%d') if timestamp else 'Unknown'
            
            card = html.Div([
                html.H3(device_id, className="device-title"),
                html.Div([
                    html.Div([
                        html.Span("Type: ", className="label"),
                        html.Span(sensor_type.capitalize(), className="value")
                    ]),
                    html.Div([
                        html.Span("Location: ", className="label"),
                        html.Span(location, className="value")
                    ]),
                    html.Div([
                        html.Span("Value: ", className="label"),
                        html.Span(f"{value}{unit}", className="sensor-value")
                    ]),
                    html.Div([
                        html.Span("Last Update: ", className="label"),
                        html.Span(f"{date_str} {time_str}", className="timestamp")
                    ])
                ], className="device-info"),
                html.Button("Details", id={'type': 'details-button', 'index': device_id}, 
                          className="details-button")
            ], className="device-card")
            
            device_cards.append(card)
        
        return html.Div(device_cards, className="device-grid")
        
    except Exception as e:
        logger.error(f"Error updating sensor devices: {e}")
        return html.Div(f"Error loading sensor devices: {str(e)}", className="error")

@app.callback(
    Output('actionable-devices-container', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_actionable_devices(n):
    try:
        logger.info(f"update_actionable_devices called with n={n}")
        
        response = requests.get(f'{RULE_ENGINE_URL}/devices', timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Failed to get devices from rule engine: {response.status_code}")
            return html.Div("Failed to load actionable devices", className="error")
        
        result = response.json()
        if not result.get('success', False):
            logger.error(f"Rule engine returned error: {result.get('message', 'Unknown error')}")
            return html.Div("Failed to load actionable devices", className="error")
        
        devices = result.get('devices', [])
        logger.info(f"Found {len(devices)} devices from API")
        
        if not devices:
            logger.info("No devices found, returning no-data message")
            return html.Div("No actionable devices found", className="no-data")
        
        device_cards = []
        for device_data in devices:
            device = ActionableDeviceDTO(
                device_id=device_data['device_id'],
                device_type=device_data['device_type'],
                location=device_data['location'],
                name=device_data['name'],
                status=device_data['status'],
                capabilities=[
                    DeviceCapabilityDTO(
                        name=cap['name'],
                        capability_type=cap['capability_type'],
                        config=cap['config'],
                        current_value=cap['current_value']
                    ) for cap in device_data['capabilities']
                ],
                last_updated=device_data['last_updated']
            )
            
            last_updated = datetime.fromisoformat(device.last_updated.replace('Z', '+00:00') if device.last_updated.endswith('Z') else device.last_updated)
            time_str = last_updated.strftime('%H:%M:%S')
            date_str = last_updated.strftime('%Y-%m-%d')
            
            capabilities_info = []
            for cap in device.capabilities:
                if cap.capability_type == 'toggle':
                    current_label = cap.config.get('labels', ['Off', 'On'])[1 if cap.current_value else 0]
                    capabilities_info.append(html.Div([
                        html.Span(f"{cap.name.replace('_', ' ').title()}: ", className="label"),
                        html.Span(current_label, className="value")
                    ]))
                elif cap.capability_type == 'absolute_value':
                    unit = cap.config.get('unit', '')
                    capabilities_info.append(html.Div([
                        html.Span(f"{cap.name.replace('_', ' ').title()}: ", className="label"),
                        html.Span(f"{cap.current_value}{unit}", className="value")
                    ]))
                elif cap.capability_type == 'discrete_values':
                    capabilities_info.append(html.Div([
                        html.Span(f"{cap.name.replace('_', ' ').title()}: ", className="label"),
                        html.Span(str(cap.current_value), className="value")
                    ]))
                elif cap.capability_type == 'trigger':
                    action = cap.config.get('action', 'trigger')
                    capabilities_info.append(html.Div([
                        html.Span(f"{cap.name.replace('_', ' ').title()}: ", className="label"),
                        html.Span(action.replace('_', ' ').title(), className="value")
                    ]))
            
            card = html.Div([
                html.H3(device.name, className="device-title"),
                html.Div([
                    html.Div([
                        html.Span("Type: ", className="label"),
                        html.Span(device.device_type.replace('_', ' ').title(), className="value")
                    ]),
                    html.Div([
                        html.Span("Location: ", className="label"),
                        html.Span(device.location.replace('_', ' ').title(), className="value")
                    ]),
                    html.Div([
                        html.Span("Status: ", className="label"),
                        html.Span(device.status.title(), className=f"status-{device.status}")
                    ]),
                    html.Hr(),
                    *capabilities_info,
                    html.Hr(),
                    html.Div([
                        html.Span("Last Update: ", className="label"),
                        html.Span(f"{date_str} {time_str}", className="timestamp")
                    ])
                ], className="device-info"),
                html.Button("Create Rule", id={'type': 'rule-button', 'index': device.device_id}, 
                          className="rule-button")
            ], className="actionable-device-card")
            
            device_cards.append(card)
        
        return html.Div(device_cards, className="device-grid")
        
    except Exception as e:
        logger.error(f"Error updating actionable devices: {e}")
        return html.Div(f"Error loading actionable devices: {str(e)}", className="error")

@app.callback(
    [Output('active-tab', 'data', allow_duplicate=True),
     Output('selected-device', 'data')],
    Input({'type': 'details-button', 'index': dash.dependencies.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def handle_details_button_click(n_clicks):
    ctx = dash.callback_context
    if not ctx.triggered or not any(n_clicks or []):
        return dash.no_update, dash.no_update
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    try:
        button_dict = json.loads(button_id)
        device_id = button_dict['index']
        return 'charts', [device_id]
    except:
        return dash.no_update, dash.no_update

@app.callback(
    [Output('rule-modal', 'style'),
     Output('rule-device-id', 'data'),
     Output('condition-tree-store', 'data', allow_duplicate=True)],
    Input({'type': 'rule-button', 'index': dash.dependencies.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def handle_rule_button_click(n_clicks):
    ctx = dash.callback_context
    if not ctx.triggered or not any(n_clicks or []):
        return dash.no_update, dash.no_update, dash.no_update
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    try:
        button_dict = json.loads(button_id)
        device_id = button_dict['index']
        return {'display': 'block'}, device_id, {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
    except Exception as e:
        logger.error(f"Error in handle_rule_button_click: {e}")
        return dash.no_update, dash.no_update, dash.no_update

@app.callback(
    Output('rule-form-container', 'children'),
    [Input('rule-device-id', 'data')],
    prevent_initial_call=True
)
def create_rule_form(device_id):
    if not device_id:
        return html.Div("No device selected")
    
    return html.Div([
        html.H3(f"Create Rule for {device_id}"),
        html.Div([
            html.Label("Rule Name:"),
            dcc.Input(id='rule-name-input', type='text', placeholder='Enter rule name', style={'width': '100%'})
        ], className='form-group'),
        
        html.Div([
            html.H4("Condition Tree"),
            html.Div([
                html.Div(id='condition-tree-display', children=render_condition_tree({'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0})),
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
                    dcc.Dropdown(id='action-capability-dropdown', placeholder='Select capability')
                ], className='form-row'),
                html.Div([
                    html.Label("Action Type:"),
                    dcc.Dropdown(
                        id='action-type-dropdown',
                        options=[
                            {'label': 'Toggle On/Off', 'value': 'toggle'},
                            {'label': 'Set Value', 'value': 'absolute_value'},
                            {'label': 'Trigger', 'value': 'trigger'},
                            {'label': 'Set Mode', 'value': 'discrete_value'}
                        ],
                        value='toggle'
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

# Helper functions for condition tree
def apply_not_to_node(tree, target_node_id, current_id="root"):
    if current_id == target_node_id:
        # If this node is already a NOT, remove it (unwrap)
        if tree.get('type') == 'not':
            return tree.get('child', {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0})
        else:
            # Wrap this node with NOT
            return {'type': 'not', 'child': tree}
    
    if not tree or tree.get('type') == 'condition':
        return tree
    
    node_type = tree.get('type')
    if node_type in ['and', 'or']:
        left_id = f"{current_id}_left"
        right_id = f"{current_id}_right"
        
        new_left = apply_not_to_node(tree.get('left', {}), target_node_id, left_id)
        new_right = apply_not_to_node(tree.get('right', {}), target_node_id, right_id)
        
        return {
            'type': node_type,
            'left': new_left,
            'right': new_right
        }
    elif node_type == 'not':
        child_id = f"{current_id}_child"
        
        # Special case: if we're trying to apply NOT to the child of a NOT node,
        # and the child has the target_node_id, then remove this NOT wrapper
        if child_id == target_node_id:
            return tree.get('child', {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0})
        
        new_child = apply_not_to_node(tree.get('child', {}), target_node_id, child_id)
        return {
            'type': 'not',
            'child': new_child
        }
    
    return tree

def delete_node_from_tree(tree, target_node_id, current_id="root", parent_tree=None, parent_key=None):
    if current_id == target_node_id and parent_tree and parent_key:
        # This is the node to delete
        if parent_tree.get('type') in ['and', 'or']:
            # For binary nodes, replace parent with the sibling
            sibling_key = 'right' if parent_key == 'left' else 'left'
            return parent_tree.get(sibling_key, {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0})
        elif parent_tree.get('type') == 'not':
            # For NOT nodes, return the child of the NOT (unwrap)
            return parent_tree.get('child', {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0})
        else:
            # Reset to default condition
            return {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
    
    if not tree or tree.get('type') == 'condition':
        return tree
    
    node_type = tree.get('type')
    if node_type in ['and', 'or']:
        left_id = f"{current_id}_left"
        right_id = f"{current_id}_right"
        
        # Check if we need to delete left or right subtree
        new_left = delete_node_from_tree(tree.get('left', {}), target_node_id, left_id, tree, 'left')
        new_right = delete_node_from_tree(tree.get('right', {}), target_node_id, right_id, tree, 'right')
        
        # If the deletion affected the current tree structure, return the result
        if left_id == target_node_id:
            return new_right
        elif right_id == target_node_id:
            return new_left
        
        return {
            'type': node_type,
            'left': new_left,
            'right': new_right
        }
    elif node_type == 'not':
        child_id = f"{current_id}_child"
        new_child = delete_node_from_tree(tree.get('child', {}), target_node_id, child_id, tree, 'child')
        
        # If the child was deleted, return the unwrapped child
        if child_id == target_node_id:
            return new_child
        
        return {
            'type': 'not',
            'child': new_child
        }
    
    return tree

def add_group_to_node(tree, target_node_id, group_type, current_id="root"):
    if current_id == target_node_id:
        # This is the node to wrap with the new group
        new_condition = {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
        return {
            'type': group_type,
            'left': tree,
            'right': new_condition
        }
    
    if not tree or tree.get('type') == 'condition':
        return tree
    
    node_type = tree.get('type')
    if node_type in ['and', 'or']:
        left_id = f"{current_id}_left"
        right_id = f"{current_id}_right"
        
        new_left = add_group_to_node(tree.get('left', {}), target_node_id, group_type, left_id)
        new_right = add_group_to_node(tree.get('right', {}), target_node_id, group_type, right_id)
        
        return {
            'type': node_type,
            'left': new_left,
            'right': new_right
        }
    elif node_type == 'not':
        child_id = f"{current_id}_child"
        new_child = add_group_to_node(tree.get('child', {}), target_node_id, group_type, child_id)
        return {
            'type': 'not',
            'child': new_child
        }
    
    return tree

def render_condition_tree(tree):
    if not tree:
        return html.Div("Empty condition tree", className="tree-empty")
    
    return html.Div([
        render_tree_node(tree, node_id="root")
    ], className="tree-display")

def render_tree_node(node, node_id, parent_id=None):
    if not node:
        return html.Div()
    
    node_type = node.get('type', 'unknown')
    
    if node_type == 'condition':
        return render_condition_node(node, node_id, parent_id)
    elif node_type in ['and', 'or']:
        return render_binary_node(node, node_id, parent_id)
    elif node_type == 'not':
        return render_unary_node(node, node_id, parent_id)
    else:
        return html.Div(f"Unknown node type: {node_type}", className="tree-error")

def render_condition_node(node, node_id, parent_id=None):
    sensor = node.get('sensor_device', '')
    operator = node.get('operator', '')
    value = node.get('value', '')
    time_filter = node.get('time_filter')
    
    operator_labels = {
        'eq': '=', 'neq': '≠', 'gt': '>', 'gte': '≥', 'lt': '<', 'lte': '≤'
    }
    
    # Ensure condition text is always visible by adding placeholder for empty sensor
    sensor_display = sensor or "[Select Sensor]"
    condition_text = f"{sensor_display} {operator_labels.get(operator, operator)} {value}"
    if time_filter and time_filter.get('type') != 'none':
        filter_type = time_filter.get('type', '')
        if filter_type == 'recent':
            if 'minutes' in time_filter:
                condition_text += f" (last {time_filter['minutes']} min)"
            elif 'hours' in time_filter:
                condition_text += f" (last {time_filter['hours']} hr)"
        elif filter_type == 'time_of_day':
            condition_text += f" ({time_filter.get('start', '')}-{time_filter.get('end', '')})"
        elif filter_type == 'days_of_week':
            days = time_filter.get('days', [])
            condition_text += f" ({', '.join(days[:2])}{'...' if len(days) > 2 else ''})"
    
    return html.Div([
        html.Div([
            html.Span(condition_text, className="condition-text"),
            html.Button("Add AND", id={'type': 'add-and-to-node', 'node_id': node_id}, className="node-button"),
            html.Button("Add OR", id={'type': 'add-or-to-node', 'node_id': node_id}, className="node-button"),
            html.Button("Edit", id={'type': 'edit-node', 'node_id': node_id}, className="node-button edit-btn"),
            html.Button("Delete", id={'type': 'delete-node', 'node_id': node_id}, className="node-button delete-btn") if parent_id else None
        ], className="condition-header")
    ], className="tree-node condition-node", id=f"node-{node_id}")

def render_binary_node(node, node_id, parent_id=None):
    operator = node['type'].upper()
    left = node.get('left', {})
    right = node.get('right', {})
    
    return html.Div([
        html.Div([
            html.Button(operator, id={'type': 'apply-not-to-node', 'node_id': node_id}, className="operator-button"),
            html.Button("Add AND", id={'type': 'add-and-to-node', 'node_id': node_id}, className="node-button"),
            html.Button("Add OR", id={'type': 'add-or-to-node', 'node_id': node_id}, className="node-button"),
            html.Button("Delete", id={'type': 'delete-node', 'node_id': node_id}, className="node-button delete-btn") if parent_id else None
        ], className="operator-header"),
        html.Div([
            render_tree_node(left, f"{node_id}_left", node_id),
            render_tree_node(right, f"{node_id}_right", node_id)
        ], className="binary-children")
    ], className="tree-node binary-node", id=f"node-{node_id}")

def render_unary_node(node, node_id, parent_id=None):
    child = node.get('child', {})
    
    return html.Div([
        html.Div([
            html.Button("NOT", id={'type': 'apply-not-to-node', 'node_id': node_id}, className="operator-button not-operator"),
            html.Button("Delete", id={'type': 'delete-node', 'node_id': node_id}, className="node-button delete-btn") if parent_id else None
        ], className="operator-header"),
        html.Div([
            render_tree_node(child, f"{node_id}_child", node_id)
        ], className="unary-children")
    ], className="tree-node unary-node", id=f"node-{node_id}")

@app.callback(
    Output('condition-tree-display', 'children'),
    Input('condition-tree-store', 'data'),
)
def update_condition_tree_display(tree_data):
    if tree_data is None:
        tree_data = {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
    return render_condition_tree(tree_data)

@app.callback(
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
    
    # Handle reset
    if 'reset-tree-btn' in trigger and reset_tree:
        return {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
    
    # Handle adding new nodes
    elif 'add-and-btn' in trigger and add_and:
        new_condition = {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
        return {'type': 'and', 'left': current_tree, 'right': new_condition}
    
    elif 'add-or-btn' in trigger and add_or:
        new_condition = {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
        return {'type': 'or', 'left': current_tree, 'right': new_condition}
    
    elif 'add-not-btn' in trigger and add_not:
        # Apply NOT to root node (same behavior as clicking NOT on individual nodes)
        return apply_not_to_node(current_tree, 'root')
    
    # Handle apply NOT to node
    elif 'apply-not-to-node' in trigger and any(apply_not_clicks or []):
        try:
            button_info = json.loads(trigger.split('.')[0])
            node_id = button_info.get('node_id', '')
            
            # Apply NOT to the specified node in the tree
            modified_tree = apply_not_to_node(current_tree, node_id)
            return modified_tree
        except Exception as e:
            logger.error(f"Error applying NOT to node: {e}")
            return current_tree
    
    # Handle delete node
    elif 'delete-node' in trigger and any(delete_clicks or []):
        try:
            button_info = json.loads(trigger.split('.')[0])
            node_id = button_info.get('node_id', '')
            
            if node_id == 'root':
                # Reset root to empty condition
                return {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
            else:
                # Try to delete the specific node from the tree
                modified_tree = delete_node_from_tree(current_tree, node_id)
                return modified_tree if modified_tree else {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
        except Exception as e:
            logger.error(f"Error deleting node: {e}")
            # Fallback: reset to simple condition
            return {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
    
    # Handle add AND group to specific node
    elif 'add-and-to-node' in trigger and any(add_and_to_node_clicks or []):
        try:
            button_info = json.loads(trigger.split('.')[0])
            node_id = button_info.get('node_id', '')
            
            # Add AND group to the specified node in the tree
            modified_tree = add_group_to_node(current_tree, node_id, 'and')
            return modified_tree
        except Exception as e:
            logger.error(f"Error adding AND group to node: {e}")
            return current_tree
    
    # Handle add OR group to specific node
    elif 'add-or-to-node' in trigger and any(add_or_to_node_clicks or []):
        try:
            button_info = json.loads(trigger.split('.')[0])
            node_id = button_info.get('node_id', '')
            
            # Add OR group to the specified node in the tree
            modified_tree = add_group_to_node(current_tree, node_id, 'or')
            return modified_tree
        except Exception as e:
            logger.error(f"Error adding OR group to node: {e}")
            return current_tree
    
    return dash.no_update

@app.callback(
    Output('action-capability-dropdown', 'options'),
    Input('rule-device-id', 'data')
)
def populate_capability_options(device_id):
    try:
        response = requests.get(f'{RULE_ENGINE_URL}/devices/{device_id}/capabilities', timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result['success']:
                options = [{'label': cap['label'], 'value': cap['name']} 
                          for cap in result['capabilities']]
                return options
        return []
    except Exception as e:
        logger.error(f"Error getting capability options: {e}")
        return []

@app.callback(
    Output('time-filter-options', 'children'),
    Input('time-filter-type-dropdown', 'value')
)
def update_time_filter_options(filter_type):
    if filter_type == 'recent':
        return html.Div([
            html.Div([
                html.Label("Minutes:"),
                dcc.Input(id='time-filter-minutes', type='number', placeholder='Minutes', style={'width': '100px'})
            ], className='form-row'),
            html.Div([
                html.Label("Hours:"),
                dcc.Input(id='time-filter-hours', type='number', placeholder='Hours', style={'width': '100px'})
            ], className='form-row')
        ])
    elif filter_type == 'time_of_day':
        return html.Div([
            html.Div([
                html.Label("Start Time:"),
                dcc.Input(id='time-filter-start', type='text', placeholder='HH:MM', value='09:00')
            ], className='form-row'),
            html.Div([
                html.Label("End Time:"),
                dcc.Input(id='time-filter-end', type='text', placeholder='HH:MM', value='17:00')
            ], className='form-row')
        ])
    elif filter_type == 'days_of_week':
        return html.Div([
            dcc.Checklist(
                id='time-filter-days',
                options=[
                    {'label': 'Monday', 'value': 'monday'},
                    {'label': 'Tuesday', 'value': 'tuesday'},
                    {'label': 'Wednesday', 'value': 'wednesday'},
                    {'label': 'Thursday', 'value': 'thursday'},
                    {'label': 'Friday', 'value': 'friday'},
                    {'label': 'Saturday', 'value': 'saturday'},
                    {'label': 'Sunday', 'value': 'sunday'}
                ],
                value=['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
            )
        ])
    return html.Div()

@app.callback(
    Output('action-value-container', 'children'),
    Input('action-type-dropdown', 'value')
)
def update_action_value_options(action_type):
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
            html.Label("Duration (seconds, optional):"),
            dcc.Input(id='action-trigger-duration', type='number', placeholder='Duration in seconds')
        ], className='form-row')
    elif action_type == 'discrete_value':
        return html.Div([
            html.Label("Value:"),
            dcc.Input(id='action-discrete-value', type='text', placeholder='Enter mode/state value')
        ], className='form-row')
    return html.Div()

@app.callback(
    [Output('rule-save-feedback', 'children'),
     Output('rule-modal', 'style', allow_duplicate=True)],
    Input('save-rule-button', 'n_clicks'),
    [State('rule-device-id', 'data'),
     State('rule-name-input', 'value'),
     State('condition-tree-store', 'data'),
     State('action-capability-dropdown', 'value'),
     State('action-type-dropdown', 'value'),
     State('action-value-container', 'children')],
    prevent_initial_call=True
)
def save_rule(n_clicks, device_id, rule_name, condition_tree, capability, action_type, action_container):
    if not n_clicks or not device_id or not rule_name:
        return dash.no_update, dash.no_update
    
    try:
        if not validate_condition_tree_completeness(condition_tree):
            return html.Div("Please ensure all conditions have sensor device, operator, and value set.", 
                          className="error-message"), dash.no_update
        
        actions = {}
        if capability and action_type:
            # Extract values from the action container
            action_value = None
            if action_container and isinstance(action_container, list) and len(action_container) > 0:
                # The action container contains the rendered form elements
                container_div = action_container[0]
                if hasattr(container_div, 'children') and container_div.children:
                    # Look for the input/dropdown in the form
                    for child in container_div.children:
                        if hasattr(child, 'id'):
                            if action_type == 'toggle' and child.id == 'action-toggle-state':
                                action_value = getattr(child, 'value', 'on')
                            elif action_type == 'absolute_value' and child.id == 'action-absolute-value':
                                action_value = getattr(child, 'value', 0)
                            elif action_type == 'trigger' and child.id == 'action-trigger-duration':
                                action_value = getattr(child, 'value', None)
                            elif action_type == 'discrete_value' and child.id == 'action-discrete-value':
                                action_value = getattr(child, 'value', 'default')
            
            # Build the action config
            if action_type == 'toggle':
                actions[capability] = {'toggle': action_value or 'on'}
            elif action_type == 'absolute_value':
                actions[capability] = {'absolute_value': action_value if action_value is not None else 0}
            elif action_type == 'trigger':
                action_config = {'trigger': True}
                if action_value:
                    action_config['duration'] = action_value
                actions[capability] = action_config
            elif action_type == 'discrete_value':
                actions[capability] = {'discrete_value': {'key': action_value or 'default'}}
        
        payload = {
            'device_id': device_id,
            'rule_name': rule_name,
            'condition_tree': condition_tree,
            'actions': actions
        }
        
        response = requests.post(f'{RULE_ENGINE_URL}/rules', json=payload, timeout=10)
        
        if response.status_code == 201:
            return html.Div("Rule saved successfully!", className="success-message"), {'display': 'none'}
        else:
            error_msg = response.json().get('message', 'Failed to save rule')
            return html.Div(error_msg, className="error-message"), dash.no_update
            
    except Exception as e:
        logger.error(f"Error saving rule: {e}")
        return html.Div(f"Error: {str(e)}", className="error-message"), dash.no_update

def validate_condition_tree_completeness(tree):
    if not tree:
        return False
    
    node_type = tree.get('type')
    if node_type == 'condition':
        return (tree.get('sensor_device') and 
                tree.get('operator') and 
                tree.get('value') is not None)
    elif node_type in ['and', 'or']:
        return (validate_condition_tree_completeness(tree.get('left')) and 
                validate_condition_tree_completeness(tree.get('right')))
    elif node_type == 'not':
        return validate_condition_tree_completeness(tree.get('child'))
    
    return False

@app.callback(
    Output('rule-modal', 'style', allow_duplicate=True),
    Input('cancel-rule-button', 'n_clicks'),
    prevent_initial_call=True
)
def cancel_rule_creation(n_clicks):
    if n_clicks:
        return {'display': 'none'}
    return dash.no_update

@app.callback(
    [Output('edit-condition-modal', 'style'),
     Output('edit-node-id', 'data')],
    Input({'type': 'edit-node', 'node_id': dash.dependencies.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def open_edit_modal(n_clicks_list):
    if not any(n_clicks_list):
        return dash.no_update, dash.no_update
    
    # Find which button was clicked
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    node_id = eval(button_id)['node_id']
    
    return {'display': 'block'}, node_id

@app.callback(
    Output('edit-condition-form', 'children'),
    [Input('edit-node-id', 'data'),
     Input('condition-tree-store', 'data')],
    prevent_initial_call=True
)
def create_edit_form(node_id, tree_data):
    if not node_id or not tree_data:
        return html.Div()
    
    # Find the node to edit
    def find_node_by_id(node, target_id, current_id="root"):
        if current_id == target_id:
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
    
    node_to_edit = find_node_by_id(tree_data, node_id)
    
    if not node_to_edit or node_to_edit.get('type') != 'condition':
        return html.Div("Cannot edit this node type")
    
    return html.Div([
        html.H3("Edit Condition"),
        html.Div([
            html.Label("Sensor Device:"),
            dcc.Dropdown(
                id='edit-sensor-device',
                options=[],  # Will be populated by callback
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

@app.callback(
    [Output('condition-tree-store', 'data', allow_duplicate=True),
     Output('edit-condition-modal', 'style', allow_duplicate=True)],
    Input('save-edit-button', 'n_clicks'),
    [State('edit-node-id', 'data'),
     State('condition-tree-store', 'data'),
     State('edit-sensor-device', 'value'),
     State('edit-operator', 'value'),
     State('edit-value', 'value')],
    prevent_initial_call=True
)
def save_edited_condition(n_clicks, node_id, tree_data, sensor_device, operator, value):
    if not n_clicks or not node_id or not tree_data:
        return dash.no_update, dash.no_update
    
    # Update the node in the tree
    def update_node_by_id(node, target_id, new_data, current_id="root"):
        if current_id == target_id:
            if node.get('type') == 'condition':
                node.update({
                    'sensor_device': sensor_device or '',
                    'operator': operator or 'gte',
                    'value': value if value is not None else 0
                })
            return True
        
        if node.get('type') in ['and', 'or']:
            if update_node_by_id(node.get('left', {}), target_id, new_data, f"{current_id}_left"):
                return True
            if update_node_by_id(node.get('right', {}), target_id, new_data, f"{current_id}_right"):
                return True
        elif node.get('type') == 'not':
            if update_node_by_id(node.get('child', {}), target_id, new_data, f"{current_id}_child"):
                return True
        
        return False
    
    updated_tree = tree_data.copy()
    update_node_by_id(updated_tree, node_id, {})
    
    return updated_tree, {'display': 'none'}


@app.callback(
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

@app.callback(
    Output('edit-sensor-device', 'options'),
    Input('edit-modal-devices-store', 'data'),
    prevent_initial_call=False
)
def populate_edit_sensor_dropdown(devices_list):
    if devices_list:
        return [{'label': device, 'value': device} for device in devices_list]
    return []


@app.callback(
    Output('edit-condition-modal', 'style', allow_duplicate=True),
    Input('cancel-edit-button', 'n_clicks'),
    prevent_initial_call=True
)
def cancel_edit(n_clicks):
    if n_clicks:
        return {'display': 'none'}
    return dash.no_update

@app.callback(
    [Output('device-dropdown', 'options'),
     Output('device-dropdown', 'value')],
    [Input('interval-component', 'n_intervals'), Input('active-tab', 'data')],
    [State('selected-device', 'data'), State('available-options', 'data')]
)
def update_device_options(n, active_tab, selected_devices, available_options):
    if active_tab == 'charts':
        try:
            all_devices = []
            for model in sensor_models:
                devices = model.get_devices()
                all_devices.extend(devices)

            unique_devices = list(dict.fromkeys(all_devices))
            options = [{'label': device, 'value': device} for device in unique_devices]

            if selected_devices:
                for device in selected_devices:
                    options.append({'label': device, 'value': device})

            return options, selected_devices or []
        except Exception as e:
            logger.error(f"Error updating device options: {e}")
            return available_options or [], selected_devices or [], available_options or []
    return dash.no_update, dash.no_update


@app.callback(
    Output('selected-device', 'data', allow_duplicate=True),
    Input('device-dropdown', 'value'),
    prevent_initial_call=True
)
def update_store_from_dropdown(selected_devices):
    return selected_devices

@app.callback(
    Output('available-options', 'data', allow_duplicate=True),
    Input('device-dropdown', 'options'),
    State('available-options', 'data'),
    prevent_initial_call=True
)
def update_store_from_dropdown_options(available_options, current_store):
    new_value = available_options if isinstance(available_options, list) else [
        available_options] if available_options else []

    if not new_value and current_store:
        return current_store

    if new_value != current_store:
        return new_value

    return dash.no_update


@app.callback(
    [Output('temperature-line-chart', 'figure'),
     Output('temperature-histogram', 'figure'),
     Output('temperature-line-chart-container', 'style'),
     Output('temperature-histogram-container', 'style')],
    [Input('time-range-dropdown', 'value'),
     Input('interval-component', 'n_intervals'),
     Input('selected-device', 'data'),
     Input('active-tab', 'data'),
     ],
    prevent_initial_call=True
)
def update_charts(time_range, n, current_store, active_tab,):
    if active_tab != 'charts':
        return go.Figure(), go.Figure(), {'display': 'none'}, {'display': 'none'}
    try:
        all_data = []
        for model in sensor_models:
            data = model.get_sensor_data(time_range, current_store)
            if not data.empty:
                all_data.append(data)

        if not all_data and current_store:
            empty_fig = go.Figure()
            empty_fig.add_annotation(
                text="No data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16)
            )
            return empty_fig, empty_fig, {'display': 'none'}, {'display': 'none'}
        
        df = pd.concat(all_data, ignore_index=True)
        
        # Line chart
        line_fig = go.Figure()

        for device in df['device_id'].unique():
            device_data = df[df['device_id'] == device]
            line_fig.add_trace(go.Scatter(
                x=device_data['_time'],
                y=device_data['value'],
                mode='lines+markers',
                name=device,
                line=dict(width=2)
            ))
        
        line_fig.update_layout(
            title='Sensor Values Over Time',
            xaxis_title='Time',
            yaxis_title='Value',
            hovermode='x unified',
            template='plotly_white',
            height=400
        )
        
        # Histogram
        hist_fig = px.histogram(
            df,
            x='value',
            color='device_id',
            nbins=20,
            title='Value Distribution by Device',
            labels={'value': 'Value', 'count': 'Frequency'}
        )

        hist_fig.update_layout(
            template='plotly_white',
            height=400
        )
        
        return line_fig, hist_fig, {'display': 'block'}, {'display': 'block'}
        
    except Exception as e:
        logger.error(f"Error updating charts: {e}")
        empty_fig = go.Figure()
        empty_fig.add_annotation(
            text=f"Error loading data: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        return empty_fig, empty_fig, {'display': 'none'}, {'display': 'none'}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)