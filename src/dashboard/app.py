import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import plotly.express as px

from src.models.temperature import TemperatureModel
from src.config.logger import get_logger
import warnings
from influxdb_client.client.warnings import MissingPivotFunction

warnings.simplefilter("ignore", MissingPivotFunction)
logger = get_logger(__name__)

app = dash.Dash(__name__)

temp_model = TemperatureModel()

app.layout = html.Div([
    html.H1("Smart Home Temperature Dashboard", className="header"),
    
    html.Div([
        html.Div([
            html.Label("Select Devices:"),
            dcc.Dropdown(
                id='device-dropdown',
                options=[],
                value=[],
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
    ], className="chart-container"),
    
    dcc.Interval(
        id='interval-component',
        interval=30*1000,  # Update every 30 seconds
        n_intervals=0
    )
], className="dashboard")

@app.callback(
    Output('device-dropdown', 'options'),
    Input('interval-component', 'n_intervals')
)
def update_device_options(n):
    try:
        devices = temp_model.get_devices()
        options = [{'label': device, 'value': device} for device in devices]
        print(f"DEBUG: Available devices: {devices}")
        return options
    except Exception as e:
        logger.error(f"Error updating device options: {e}")
        return []

@app.callback(
    [Output('temperature-line-chart', 'figure'),
     Output('temperature-histogram', 'figure')],
    [Input('device-dropdown', 'value'),
     Input('time-range-dropdown', 'value'),
     Input('interval-component', 'n_intervals')]
)
def update_charts(selected_devices, time_range, n):
    print(f"DEBUG: Selected devices: {selected_devices}, Type: {type(selected_devices)}")
    logger.info(f"Selected devices: {selected_devices}")
    try:
        df = temp_model.get_temperature_data(time_range, selected_devices)
        
        if df.empty:
            empty_fig = go.Figure()
            empty_fig.add_annotation(
                text="No data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16)
            )
            return empty_fig, empty_fig
        
        # Line chart
        line_fig = go.Figure()
        
        if selected_devices:
            for device in selected_devices:
                device_data = df[df['device_id'] == device]
                if not device_data.empty:
                    line_fig.add_trace(go.Scatter(
                        x=device_data['_time'],
                        y=device_data['temperature'],
                        mode='lines+markers',
                        name=device,
                        line=dict(width=2)
                    ))
        else:
            for device in df['device_id'].unique():
                device_data = df[df['device_id'] == device]
                line_fig.add_trace(go.Scatter(
                    x=device_data['_time'],
                    y=device_data['temperature'],
                    mode='lines+markers',
                    name=device,
                    line=dict(width=2)
                ))
        
        line_fig.update_layout(
            title='Temperature Over Time',
            xaxis_title='Time',
            yaxis_title='Temperature (°C)',
            hovermode='x unified',
            template='plotly_white',
            height=400
        )
        
        # Histogram
        if selected_devices and len(selected_devices) == 1:
            hist_fig = px.histogram(
                df, 
                x='temperature',
                nbins=20,
                title=f'Temperature Distribution - {selected_devices[0]}',
                labels={'temperature': 'Temperature (°C)', 'count': 'Frequency'}
            )
        else:
            hist_fig = px.histogram(
                df, 
                x='temperature',
                color='device_id',
                nbins=20,
                title='Temperature Distribution by Device',
                labels={'temperature': 'Temperature (°C)', 'count': 'Frequency'}
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