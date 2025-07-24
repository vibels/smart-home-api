import dash
from dash import html, Input, Output, callback
import pandas as pd
import json
from src.config.logger import get_logger
from . import sensor_models

logger = get_logger(__name__)

@callback(
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

@callback(
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