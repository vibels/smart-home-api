import dash
from dash import html, Input, Output, callback
import requests
import os
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any
import json
from src.config.logger import get_logger

logger = get_logger(__name__)

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

@callback(
    Output('actionable-devices-container', 'children'),
    Input('interval-component', 'n_intervals'),
    prevent_initial_call=False
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
                html.Div([
                    html.Button("Create Rule", id={'type': 'rule-button', 'index': device.device_id}, 
                              className="rule-button"),
                    html.Button("View Rules", id={'type': 'view-rules-button', 'index': device.device_id}, 
                              className="view-rules-button")
                ], className="device-buttons")
            ], className="actionable-device-card", style={"pointerEvents": "none"})
            
            device_cards.append(card)
        
        return html.Div(device_cards, className="device-grid")
        
    except Exception as e:
        logger.error(f"Error updating actionable devices: {e}")
        return html.Div(f"Error loading actionable devices: {str(e)}", className="error")