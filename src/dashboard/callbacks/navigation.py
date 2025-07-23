import dash
from dash import html, Input, Output, State, callback
from ..components.layout import create_charts_tab_content, create_actionable_tab_content

@callback(
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

@callback(
    Output('tab-content', 'children'),
    Input('active-tab', 'data'),
    [State('selected-device', 'data'), State('available-options', 'data')]
)
def render_tab_content(active_tab, selected_devices, available_options):
    from src.config.logger import get_logger
    logger = get_logger(__name__)
    logger.info(f"render_tab_content called with active_tab={active_tab}")
    
    if active_tab == 'sensors':
        return html.Div(id='sensor-devices-container')
    elif active_tab == 'charts':
        return create_charts_tab_content(available_options, selected_devices)
    elif active_tab == 'actionable':
        return create_actionable_tab_content()