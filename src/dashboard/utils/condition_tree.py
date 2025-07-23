from dash import html
import json

def apply_not_to_node(tree, target_node_id, current_id="root"):
    if current_id == target_node_id:
        if tree.get('type') == 'not':
            return tree.get('child', {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0})
        else:
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
        if parent_tree.get('type') in ['and', 'or']:
            sibling_key = 'right' if parent_key == 'left' else 'left'
            return parent_tree.get(sibling_key, {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0})
        elif parent_tree.get('type') == 'not':
            return parent_tree.get('child', {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0})
        else:
            return {'type': 'condition', 'sensor_device': '', 'operator': 'gte', 'value': 0}
    
    if not tree or tree.get('type') == 'condition':
        return tree
    
    node_type = tree.get('type')
    if node_type in ['and', 'or']:
        left_id = f"{current_id}_left"
        right_id = f"{current_id}_right"
        
        new_left = delete_node_from_tree(tree.get('left', {}), target_node_id, left_id, tree, 'left')
        new_right = delete_node_from_tree(tree.get('right', {}), target_node_id, right_id, tree, 'right')
        
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
        
        if child_id == target_node_id:
            return new_child
        
        return {
            'type': 'not',
            'child': new_child
        }
    
    return tree

def add_group_to_node(tree, target_node_id, group_type, current_id="root"):
    if current_id == target_node_id:
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

def render_condition_tree(tree, prefix=''):
    if not tree:
        return html.Div("Empty condition tree", className="tree-empty")
    
    return html.Div([
        render_tree_node(tree, node_id="root", parent_id=None, prefix=prefix)
    ], className="tree-display")

def render_tree_node(node, node_id, parent_id=None, prefix=''):
    if not node:
        return html.Div()
    
    node_type = node.get('type', 'unknown')
    
    if node_type == 'condition':
        return render_condition_node(node, node_id, parent_id, prefix)
    elif node_type in ['and', 'or']:
        return render_binary_node(node, node_id, parent_id, prefix)
    elif node_type == 'not':
        return render_unary_node(node, node_id, parent_id, prefix)
    else:
        return html.Div(f"Unknown node type: {node_type}", className="tree-error")

def render_condition_node(node, node_id, parent_id=None, prefix=''):
    sensor = node.get('sensor_device', '')
    operator = node.get('operator', '')
    value = node.get('value', '')
    time_filter = node.get('time_filter')
    
    operator_labels = {
        'eq': '=', 'neq': '≠', 'gt': '>', 'gte': '≥', 'lt': '<', 'lte': '≤'
    }
    
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
            html.Button("Add AND", id={'type': f'{prefix}add-and-to-node', 'node_id': node_id}, className="node-button"),
            html.Button("Add OR", id={'type': f'{prefix}add-or-to-node', 'node_id': node_id}, className="node-button"),
            html.Button("Edit", id={'type': f'{prefix}edit-node', 'node_id': node_id}, className="node-button edit-btn"),
            html.Button("Delete", id={'type': f'{prefix}delete-node', 'node_id': node_id}, className="node-button delete-btn") if parent_id else None
        ], className="condition-header")
    ], className="tree-node condition-node", id=f"node-{node_id}")

def render_binary_node(node, node_id, parent_id=None, prefix=''):
    operator = node['type'].upper()
    left = node.get('left', {})
    right = node.get('right', {})
    
    return html.Div([
        html.Div([
            html.Button(operator, id={'type': f'{prefix}apply-not-to-node', 'node_id': node_id}, className="operator-button"),
            html.Button("Add AND", id={'type': f'{prefix}add-and-to-node', 'node_id': node_id}, className="node-button"),
            html.Button("Add OR", id={'type': f'{prefix}add-or-to-node', 'node_id': node_id}, className="node-button"),
            html.Button("Delete", id={'type': f'{prefix}delete-node', 'node_id': node_id}, className="node-button delete-btn") if parent_id else None
        ], className="operator-header"),
        html.Div([
            render_tree_node(left, f"{node_id}_left", node_id, prefix),
            render_tree_node(right, f"{node_id}_right", node_id, prefix)
        ], className="binary-children")
    ], className="tree-node binary-node", id=f"node-{node_id}")

def render_unary_node(node, node_id, parent_id=None, prefix=''):
    child = node.get('child', {})
    
    return html.Div([
        html.Div([
            html.Button("NOT", id={'type': f'{prefix}apply-not-to-node', 'node_id': node_id}, className="operator-button not-operator"),
            html.Button("Delete", id={'type': f'{prefix}delete-node', 'node_id': node_id}, className="node-button delete-btn") if parent_id else None
        ], className="operator-header"),
        html.Div([
            render_tree_node(child, f"{node_id}_child", node_id, prefix)
        ], className="unary-children")
    ], className="tree-node unary-node", id=f"node-{node_id}")

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