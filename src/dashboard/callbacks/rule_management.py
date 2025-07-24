import dash
from dash import html, dcc, Input, Output, State, callback
import requests
import os
import json
from datetime import datetime
from src.config.logger import get_logger
from . import sensor_models
from ..utils.condition_tree import render_condition_tree, validate_condition_tree_completeness

logger = get_logger(__name__)

RULE_ENGINE_URL = os.getenv('RULE_ENGINE_URL', 'http://localhost:5001')


@callback(
    [Output('view-rules-modal', 'style'),
     Output('view-rules-device-id', 'data')],
    Input({'type': 'view-rules-button', 'index': dash.dependencies.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def handle_view_rules_button_click(n_clicks):
    ctx = dash.callback_context
    if not ctx.triggered or not any(n_clicks or []):
        return dash.no_update, dash.no_update
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    try:
        button_dict = json.loads(button_id)
        device_id = button_dict['index']
        logger.info(f"Opening view rules modal for device: {device_id}")
        return {'display': 'block'}, device_id
    except Exception as e:
        logger.error(f"Error in handle_view_rules_button_click: {e}")
        return {'display': 'none'}, dash.no_update

@callback(
    Output('rules-list-container', 'children'),
    [Input('view-rules-device-id', 'data'),
     Input('rules-search-store', 'data')],
    prevent_initial_call=True
)
def populate_rules_list(device_id, search_term):
    if not device_id:
        return html.Div("No device selected")
    
    try:
        response = requests.get(f'{RULE_ENGINE_URL}/rules/{device_id}', timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Failed to get rules from rule engine: {response.status_code}")
            return html.Div([
                html.H3(f"Rules for {device_id}"),
                html.Div([
                    html.Label("Search rules:", className="form-label"),
                    dcc.Input(id='rules-search-input', type='text', placeholder='Search by rule name...', className='search-input')
                ], className="search-container"),
                html.Div("Failed to load rules", className="error")
            ])
        
        result = response.json()
        if not result.get('success', False):
            logger.error(f"Rule engine returned error: {result.get('message', 'Unknown error')}")
            return html.Div([
                html.H3(f"Rules for {device_id}"),
                html.Div([
                    html.Label("Search rules:", className="form-label"),
                    dcc.Input(id='rules-search-input', type='text', placeholder='Search by rule name...', className='search-input')
                ], className="search-container"),
                html.Div("Failed to load rules", className="error")
            ])
        
        rules = result.get('rules', [])
        
        if search_term:
            rules = [rule for rule in rules if search_term.lower() in rule['rule_name'].lower()]
        
        if not rules:
            no_results_msg = "No rules found matching your search" if search_term else "No rules found for this device"
            return html.Div([
                html.H3(f"Rules for {device_id}"),
                html.Div([
                    html.Label("Search rules:", className="form-label"),
                    dcc.Input(id='rules-search-input', type='text', placeholder='Search by rule name...', className='search-input', value=search_term or '')
                ], className="search-container"),
                html.Div(no_results_msg, className="no-data")
            ])
        
        rule_cards = []
        for rule in rules:
            rule_id = rule['rule_id']
            rule_name = rule['rule_name']
            enabled = rule['enabled']
            created_at = rule.get('created_at', 'Unknown')
            
            try:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00') if created_at.endswith('Z') else created_at)
                created_str = created_dt.strftime('%Y-%m-%d %H:%M')
            except:
                created_str = str(created_at)
            
            actions = rule.get('actions', {})
            action_summary = []
            for capability, action_config in actions.items():
                if 'toggle' in action_config:
                    action_summary.append(f"{capability}: {action_config['toggle']}")
                elif 'absolute_value' in action_config:
                    action_summary.append(f"{capability}: {action_config['absolute_value']}")
                elif 'discrete_value' in action_config:
                    action_summary.append(f"{capability}: {action_config['discrete_value']}")
                elif 'trigger' in action_config:
                    duration = action_config.get('duration', 30)
                    action_summary.append(f"{capability}: trigger ({duration}s)")
            
            status_class = "rule-enabled" if enabled else "rule-disabled"
            status_text = "Enabled" if enabled else "Disabled"
            
            rule_card = html.Div([
                html.H4(rule_name, className="rule-title"),
                html.Div([
                    html.Div([
                        html.Span("Status: ", className="label"),
                        html.Span(status_text, className=f"status {status_class}")
                    ]),
                    html.Div([
                        html.Span("Created: ", className="label"),
                        html.Span(created_str, className="timestamp")
                    ]),
                    html.Div([
                        html.Span("Actions: ", className="label"),
                        html.Span(", ".join(action_summary) if action_summary else "No actions", className="actions-summary")
                    ])
                ], className="rule-info"),
                html.Div([
                    html.Button(
                        "View Condition", 
                        id={'type': 'view-condition', 'rule_id': rule_id}, 
                        className="view-condition-button"
                    ),
                    html.Button(
                        "Disable" if enabled else "Enable", 
                        id={'type': 'toggle-rule', 'rule_id': rule_id}, 
                        className="toggle-rule-button"
                    ),
                    html.Button(
                        "Delete", 
                        id={'type': 'delete-rule', 'rule_id': rule_id}, 
                        className="delete-rule-button"
                    )
                ], className="rule-buttons")
            ], className=f"rule-card {status_class}")
            
            rule_cards.append(rule_card)
        
        return html.Div([
            html.H3(f"Rules for {device_id}"),
            html.Div([
                html.Label("Search rules:", className="form-label"),
                dcc.Input(id='rules-search-input', type='text', placeholder='Search by rule name...', className='search-input', value=search_term or '')
            ], className="search-container"),
            html.Div(rule_cards, className="rules-grid"),
            html.Div(id='rule-action-feedback')
        ])
        
    except Exception as e:
        logger.error(f"Error loading rules for device {device_id}: {e}")
        return html.Div([
            html.H3(f"Rules for {device_id}"),
            html.Div([
                html.Label("Search rules:", className="form-label"),
                dcc.Input(id='rules-search-input', type='text', placeholder='Search by rule name...', className='search-input')
            ], className="search-container"),
            html.Div(f"Error loading rules: {str(e)}", className="error")
        ])


@callback(
    Output('view-rules-modal', 'style', allow_duplicate=True),
    Input('close-rules-modal', 'n_clicks'),
    prevent_initial_call=True
)
def close_rules_modal(n_clicks):
    if n_clicks:
        return {'display': 'none'}
    return dash.no_update

@callback(
    [Output('rule-action-feedback', 'children'),
     Output('view-rules-device-id', 'data', allow_duplicate=True)],
    [Input({'type': 'toggle-rule', 'rule_id': dash.dependencies.ALL}, 'n_clicks'),
     Input({'type': 'delete-rule', 'rule_id': dash.dependencies.ALL}, 'n_clicks')],
    [State('view-rules-device-id', 'data')],
    prevent_initial_call=True
)
def handle_rule_actions(toggle_clicks, delete_clicks, device_id):
    ctx = dash.callback_context
    if not ctx.triggered or not device_id:
        return dash.no_update, dash.no_update
    
    # Check if any button was actually clicked (n_clicks > 0)
    if not any(toggle_clicks or []) and not any(delete_clicks or []):
        return dash.no_update, dash.no_update
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    try:
        button_dict = json.loads(button_id)
        rule_id = button_dict['rule_id']
        action_type = button_dict['type']
        
        if action_type == 'toggle-rule':
            response = requests.post(f'{RULE_ENGINE_URL}/rules/{rule_id}/toggle', timeout=10)
            if response.status_code == 200:
                feedback = html.Div("Rule status toggled successfully!", className="success-message")
            else:
                error_msg = response.json().get('message', 'Failed to toggle rule')
                feedback = html.Div(error_msg, className="error-message")
        
        elif action_type == 'delete-rule':
            response = requests.delete(f'{RULE_ENGINE_URL}/rules/{rule_id}', timeout=10)
            if response.status_code == 200:
                feedback = html.Div("Rule deleted successfully!", className="success-message")
            else:
                error_msg = response.json().get('message', 'Failed to delete rule')
                feedback = html.Div(error_msg, className="error-message")
        else:
            return dash.no_update, dash.no_update
        
        # Trigger refresh by setting the device_id again - this will cause populate_rules_list to re-run
        return feedback, device_id
    
    except Exception as e:
        logger.error(f"Error handling rule action: {e}")
        return html.Div(f"Error: {str(e)}", className="error-message"), dash.no_update

@callback(
    [Output('condition-tree-modal', 'style'),
     Output('view-condition-rule-id', 'data')],
    Input({'type': 'view-condition', 'rule_id': dash.dependencies.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def handle_view_condition_button_click(n_clicks):
    ctx = dash.callback_context
    if not ctx.triggered or not any(n_clicks or []):
        return dash.no_update, dash.no_update
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    try:
        button_dict = json.loads(button_id)
        rule_id = button_dict['rule_id']
        return {'display': 'block'}, rule_id
    except Exception as e:
        logger.error(f"Error in handle_view_condition_button_click: {e}")
        return {'display': 'none'}, dash.no_update

@callback(
    Output('condition-tree-container', 'children'),
    Input('view-condition-rule-id', 'data'),
    [State('view-rules-device-id', 'data')],
    prevent_initial_call=True
)
def populate_condition_tree_view(rule_id, device_id):
    if not rule_id or not device_id:
        return html.Div("No rule selected")
    
    try:
        response = requests.get(f'{RULE_ENGINE_URL}/rules/{device_id}', timeout=10)
        
        if response.status_code != 200:
            return html.Div([
                html.H3("Condition Tree"),
                html.Div("Failed to load rule", className="error"),
                html.Button('Close', id='close-condition-tree-modal', className='cancel-button')
            ])
        
        result = response.json()
        if not result.get('success', False):
            return html.Div([
                html.H3("Condition Tree"),
                html.Div("Failed to load rule", className="error"),
                html.Button('Close', id='close-condition-tree-modal', className='cancel-button')
            ])
        
        rules = result.get('rules', [])
        rule = next((r for r in rules if str(r['rule_id']) == str(rule_id)), None)
        
        if not rule:
            return html.Div([
                html.H3("Condition Tree"),
                html.Div("Rule not found", className="error"),
                html.Button('Close', id='close-condition-tree-modal', className='cancel-button')
            ])
        
        rule_name = rule['rule_name']
        conditions = rule.get('conditions', {})
        
        return html.Div([
            html.H3(f"Condition Tree: {rule_name}"),
            html.Div([
                html.H4("Condition Tree Structure"),
                html.Div(
                    json.dumps(conditions, indent=2),
                    className="condition-json"
                )
            ], className="condition-display"),
            html.Div([
                html.Button('Edit Condition Tree', id='edit-condition-tree-button', className='edit-condition-button', n_clicks=0),
                html.Button('Close', id='close-condition-tree-modal', className='cancel-button')
            ], className='modal-buttons')
        ])
        
    except Exception as e:
        logger.error(f"Error loading condition tree for rule {rule_id}: {e}")
        return html.Div([
            html.H3("Condition Tree"),
            html.Div(f"Error loading condition tree: {str(e)}", className="error"),
            html.Button('Close', id='close-condition-tree-modal', className='cancel-button')
        ])

@callback(
    Output('condition-tree-modal', 'style', allow_duplicate=True),
    Input('close-condition-tree-modal', 'n_clicks'),
    prevent_initial_call=True
)
def close_condition_tree_modal(n_clicks):
    if n_clicks:
        return {'display': 'none'}
    return dash.no_update

@callback(
    [Output('rule-modal', 'style', allow_duplicate=True),
     Output('rule-device-id', 'data', allow_duplicate=True),
     Output('condition-tree-store', 'data', allow_duplicate=True),
     Output('condition-tree-modal', 'style', allow_duplicate=True),
     Output('edit-rule-id', 'data'),
     Output('view-rules-device-id', 'data', allow_duplicate=True),
     Output('edit-rule-data', 'data', allow_duplicate=True)],
    Input('edit-condition-tree-button', 'n_clicks'),
    [State('view-condition-rule-id', 'data'),
     State('view-rules-device-id', 'data')],
    prevent_initial_call=True
)
def handle_edit_condition_tree_button(n_clicks, rule_id, device_id):
    logger.info(f"Edit condition tree callback triggered with n_clicks={n_clicks}, rule_id={rule_id}, device_id={device_id}")
    
    if not n_clicks or not rule_id or not device_id:
        logger.info("Callback returning no_update due to missing parameters")
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    try:
        logger.info(f"Edit condition tree button clicked for rule {rule_id} on device {device_id}")
        
        # Get the rule's condition tree data
        response = requests.get(f'{RULE_ENGINE_URL}/rules/{device_id}', timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Failed to get rule data for editing: {response.status_code}")
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        
        result = response.json()
        if not result.get('success', False):
            logger.error(f"Rule engine returned error: {result.get('message', 'Unknown error')}")
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        
        rules = result.get('rules', [])
        rule = next((r for r in rules if str(r['rule_id']) == str(rule_id)), None)
        
        if not rule:
            logger.error(f"Rule {rule_id} not found")
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        
        conditions = rule.get('conditions', {})
        rule_name = rule.get('rule_name', '')
        actions = rule.get('actions', {})
        
        # Extract action data for pre-filling
        capability_name = None
        action_type = None
        if actions:
            # Get the first action (assuming single action for now)
            for cap_name, action_config in actions.items():
                capability_name = cap_name
                if 'toggle' in action_config:
                    action_type = 'toggle'
                elif 'absolute_value' in action_config:
                    action_type = 'absolute_value'
                elif 'trigger' in action_config:
                    action_type = 'trigger'
                elif 'discrete_value' in action_config:
                    action_type = 'discrete_values'
                break
        
        logger.info(f"Opening rule editor with conditions: {conditions}")
        logger.info(f"Pre-filling rule name: {rule_name}, capability: {capability_name}, action_type: {action_type}")
        
        # Create rule data store for pre-filling the form
        rule_data = {
            'rule_name': rule_name,
            'capability_name': capability_name,
            'action_type': action_type,
            'actions': actions
        }
        
        # Open the rule editor with existing condition tree (keep condition modal open in background)
        logger.info(f"Returning rule modal display=block, device_id={device_id}, edit_rule_id={rule_id}")
        logger.info(f"About to set condition-tree-store to: {conditions}")
        return {'display': 'block'}, device_id, conditions, dash.no_update, rule_id, device_id, rule_data
        
    except Exception as e:
        logger.error(f"Error handling edit condition tree button: {e}")
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

@callback(
    Output('rules-search-store', 'data'),
    Input('rules-search-input', 'value'),
    prevent_initial_call=True
)
def update_search_store(search_value):
    return search_value or ''