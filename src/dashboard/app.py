import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import plotly.express as px
from datetime import datetime
import pandas as pd

from src.models.sensor import TemperatureModel, HumidityModel, MotionModel, GasModel
from src.config.logger import get_logger
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

app.layout = html.Div([
    dcc.Store(id='current-view', data='main'),
    dcc.Store(id='selected-device', data=None),
    
    html.Div(id='page-content'),
    
    dcc.Interval(
        id='interval-component',
        interval=30*1000,  # Update every 30 seconds
        n_intervals=0
    )
], className="dashboard")

def create_main_dashboard():
    return html.Div([
        html.H1("Smart Home Dashboard", className="header"),
        html.Div([
            html.Button("← Back to Main", id="back-button", className="back-button", style={'display': 'none'})
        ]),
        html.Div(id='device-overview-container', className="device-overview")
    ])

def create_device_dashboard(selected_device=None):
    return html.Div([
        html.Div([
            html.Button("← Back to Main", id="back-button", className="back-button")
        ]),
        html.H1(f"Device Dashboard - {selected_device if selected_device else 'All Devices'}", className="header"),
        
        html.Div([
            html.Div([
                html.Label("Select Devices:"),
                dcc.Dropdown(
                    id='device-dropdown',
                    options=[],
                    value=[selected_device] if selected_device else [],
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
        ], className="chart-container"),
        
        html.Div([
            dcc.Graph(id='temperature-histogram')
        ], className="chart-container")
    ])

@app.callback(
    Output('page-content', 'children'),
    [Input('current-view', 'data'),
     Input('selected-device', 'data')]
)
def display_page(current_view, selected_device):
    if current_view == 'main':
        return create_main_dashboard()
    else:
        return create_device_dashboard(selected_device)

@app.callback(
    Output('device-overview-container', 'children'),
    [Input('interval-component', 'n_intervals'),
     Input('current-view', 'data')]
)
def update_device_overview(n, current_view):
    try:
        all_data = []
        for model in sensor_models:
            data = model.get_latest_device_data()
            if not data.empty:
                all_data.append(data)
        
        if not all_data:
            return html.Div("No devices found", className="no-data")
            
        latest_data = pd.concat(all_data, ignore_index=True)
        
        device_cards = []
        for _, row in latest_data.iterrows():
            device_id = row['device_id']
            value = row['value']
            timestamp = row['_time']
            location = row['location'] if row['location'] else 'Unknown'
            sensor_type = row.get('type', 'Unknown')
            
            # Get appropriate unit based on sensor type
            units = {'temperature': '°C', 'humidity': '%', 'motion': '', 'gas': 'ppm'}
            unit = units.get(sensor_type, '')
            
            # Format timestamp
            time_str = timestamp.strftime('%H:%M:%S') if timestamp else 'Unknown'
            date_str = timestamp.strftime('%Y-%m-%d') if timestamp else 'Unknown'
            
            card = html.Div([
                html.H3(device_id, className="device-title"),
                html.Div([
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
                html.Button("View Details", id={'type': 'device-button', 'index': device_id}, 
                          className="device-button")
            ], className="device-card")
            
            device_cards.append(card)
        
        return html.Div(device_cards, className="device-grid")
        
    except Exception as e:
        logger.error(f"Error updating device overview: {e}")
        return html.Div(f"Error loading devices: {str(e)}", className="error")

@app.callback(
    [Output('current-view', 'data'),
     Output('selected-device', 'data')],
    Input({'type': 'device-button', 'index': dash.dependencies.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def handle_device_click(n_clicks):
    ctx = dash.callback_context
    if not ctx.triggered or not any(n_clicks or []):
        return dash.no_update, dash.no_update
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    try:
        import json
        button_dict = json.loads(button_id)
        device_id = button_dict['index']
        return 'device', device_id
    except:
        return dash.no_update, dash.no_update

@app.callback(
    [Output('current-view', 'data', allow_duplicate=True),
     Output('selected-device', 'data', allow_duplicate=True)],
    Input('back-button', 'n_clicks'),
    prevent_initial_call=True
)
def handle_back_click(n_clicks):
    if n_clicks:
        return 'main', None
    return dash.no_update, dash.no_update

@app.callback(
    [Output('device-dropdown', 'options'),
     Output('device-dropdown', 'value')],
    [Input('interval-component', 'n_intervals'),
     Input('selected-device', 'data')],
    prevent_initial_call=False
)
def update_device_options(n, selected_device):
    try:
        all_devices = []
        for model in sensor_models:
            devices = model.get_devices()
            all_devices.extend(devices)
        
        unique_devices = list(dict.fromkeys(all_devices))
        options = [{'label': device, 'value': device} for device in unique_devices]
        
        if selected_device and selected_device in unique_devices:
            value = [selected_device]
        else:
            value = []
            
        return options, value
    except Exception as e:
        logger.error(f"Error updating device options: {e}")
        return [], []

@app.callback(
    [Output('temperature-line-chart', 'figure'),
     Output('temperature-histogram', 'figure')],
    [Input('device-dropdown', 'value'),
     Input('time-range-dropdown', 'value'),
     Input('interval-component', 'n_intervals'),
     Input('current-view', 'data')],
    prevent_initial_call=True
)
def update_charts(selected_devices, time_range, n, current_view):
    if current_view != 'device':
        empty_fig = go.Figure()
        return empty_fig, empty_fig
        
    try:
        all_data = []
        for model in sensor_models:
            data = model.get_sensor_data(time_range, selected_devices)
            if not data.empty:
                all_data.append(data)
        
        if not all_data:
            empty_fig = go.Figure()
            empty_fig.add_annotation(
                text="No data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16)
            )
            return empty_fig, empty_fig
        
        df = pd.concat(all_data, ignore_index=True)
        
        # Line chart
        line_fig = go.Figure()
        
        if selected_devices:
            for device in selected_devices:
                device_data = df[df['device_id'] == device]
                if not device_data.empty:
                    line_fig.add_trace(go.Scatter(
                        x=device_data['_time'],
                        y=device_data['value'],
                        mode='lines+markers',
                        name=device,
                        line=dict(width=2)
                    ))
        else:
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
        if selected_devices and len(selected_devices) == 1:
            hist_fig = px.histogram(
                df, 
                x='value',
                nbins=20,
                title=f'Value Distribution - {selected_devices[0]}',
                labels={'value': 'Value', 'count': 'Frequency'}
            )
        else:
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
        
        return line_fig, hist_fig
        
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
        return empty_fig, empty_fig

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)