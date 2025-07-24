from dash import dcc, html

def create_layout():
    return html.Div([
        dcc.Store(id='selected-device', data=[]),
        dcc.Store(id='available-options', data=[]),
        dcc.Store(id='edit-modal-devices-store', data=[]),
        dcc.Store(id='condition-tree-store', data={'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}),
        dcc.Store(id='device-capabilities-store', data=[]),
        
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
        ], className='modal rule-creation-modal', style={'display': 'none'}),

        html.Div(id='edit-condition-modal', children=[
            html.Div(id='edit-condition-form', className='modal-content')
        ], className='modal edit-condition-modal', style={'display': 'none'}),
        
        html.Div(id='view-rules-modal', children=[
            html.Div([
                html.Div(id='rules-list-container'),
                html.Div([
                    html.Button('Close', id='close-rules-modal', className='cancel-button')
                ], className='modal-buttons')
            ], className='modal-content')
        ], className='modal view-rules-modal', style={'display': 'none'}),
        
        html.Div(id='condition-tree-modal', children=[
            html.Div(id='condition-tree-container', className='modal-content')
        ], className='modal condition-tree-modal', style={'display': 'none'}),
        
        dcc.Store(id='edit-node-id', data=None),
        dcc.Store(id='view-rules-device-id', data=None),
        dcc.Store(id='view-condition-rule-id', data=None),
        dcc.Store(id='edit-condition-tree-store', data=None),
        dcc.Store(id='edit-rule-data', data=None),
        dcc.Store(id='edit-rule-id', data=None),
        dcc.Store(id='edit-tree-data-store', data={'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}),
        dcc.Store(id='rules-search-store', data=''),
        
        dcc.Interval(
            id='interval-component',
            interval=5*1000,
            n_intervals=0
        )
    ], className="dashboard")

def create_charts_tab_content(available_options, selected_devices):
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

def create_actionable_tab_content():
    return html.Div([
        html.Div(id='actionable-devices-container')
    ])