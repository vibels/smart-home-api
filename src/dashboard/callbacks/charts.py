import dash
from dash import Input, Output, State, callback
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
from src.config.logger import get_logger
from . import sensor_models

logger = get_logger(__name__)

@callback(
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

@callback(
    Output('selected-device', 'data', allow_duplicate=True),
    Input('device-dropdown', 'value'),
    prevent_initial_call=True
)
def update_store_from_dropdown(selected_devices):
    return selected_devices

@callback(
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

@callback(
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