import dash
import warnings
from influxdb_client.client.warnings import MissingPivotFunction

from .components.layout import create_layout

warnings.simplefilter("ignore", MissingPivotFunction)

app = dash.Dash(__name__, suppress_callback_exceptions=True)

app.layout = create_layout()

# DO NOT remove imports, they build they UI
from .callbacks import (
    navigation, 
    sensor_devices, 
    actionable_devices, 
    charts, 
    rule_engine, 
    rule_management, 
    edit_modal
)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)