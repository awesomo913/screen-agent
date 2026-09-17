"""toolkit_94_data_structure_visualizer.py
Visualize data structures as text/ASCII — trees, graphs, stacks, queues.
"""
from collections import deque
import json

def visualize_binary_tree(tree: dict, node_width: int = 3) -> dict:
    """Render a binary tree as ASCII art. tree: {value, left: {...}, right: {...}}."""
    try:
        if not tree:
            return {'success': True, 'data': '(empty)', 'error': None}
        def _height(node):
            if not node:
                return 0
            return 1 + max(_height(node.get('left')), _height(node.get('right')))
        def _build(node, level, lines, prefix, is_left):
            if not node:
                return
            _build(node.get('right'), level+1, lines, prefix + ('    ' if is_left else '|   '), False)
            lines.append(prefix + ('|-- ' if level > 0 else '') + str(node.get('value','?')))
            _build(node.get('left'), level+1, lines, prefix + ('|   ' if not is_left else '    '), True)
        lines = []
        _build(tree, 0, lines, '', True)
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def visualize_stack(items: list) -> dict:
    """Render a stack as ASCII art."""
    try:
        if not items:
            return {'success': True, 'data': 'Stack: (empty)', 'error': None}
        width = max(len(str(i)) for i in items) + 4
        lines = ['+' + '-'*(width-2) + '+']
        for item in reversed(items):
            s = str(item)
            pad = (width - 2 - len(s)) // 2
            lines.append('| ' + ' '*pad + s + ' '*((width-2-len(s)-pad)) + ' |')
            lines.append('+' + '-'*(width-2) + '+')
        lines.append('  TOP ^')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def visualize_queue(items: list) -> dict:
    """Render a queue as ASCII art."""
    try:
        if not items:
            return {'success': True, 'data': 'Queue: (empty)', 'error': None}
        cells = [' ' + str(item) + ' ' for item in items]
        top = '+' + '+'.join('-'*len(c) for c in cells) + '+'
        middle = '|' + '|'.join(cells) + '|'
        lines = [top, middle, top, 'FRONT^' + ' '*max(0, len(top)-12) + '^BACK']
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def visualize_linked_list(items: list) -> dict:
    """Render a linked list as ASCII art."""
    try:
        if not items:
            return {'success': True, 'data': 'LinkedList: NULL', 'error': None}
        nodes = ['[' + str(i) + '|->]' for i in items]
        result = ' '.join(nodes) + ' NULL'
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def visualize_graph(adjacency: dict) -> dict:
    """Render a graph as ASCII adjacency list."""
    try:
        lines = ['Graph Adjacency List:', '=' * 30]
        for node, neighbors in adjacency.items():
            lines.append(str(node) + ' --> ' + ', '.join(str(n) for n in neighbors))
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def visualize_matrix(matrix: list, col_width: int = 4) -> dict:
    """Render a 2D matrix as formatted text."""
    try:
        if not matrix:
            return {'success': True, 'data': '(empty matrix)', 'error': None}
        lines = []
        rows = len(matrix)
        cols = len(matrix[0]) if matrix else 0
        header = '    ' + ''.join(str(j).rjust(col_width) for j in range(cols))
        lines.append(header)
        lines.append('   +' + '-'*cols*col_width + '+')
        for i, row in enumerate(matrix):
            row_str = str(i) + '  |' + ''.join(str(cell).rjust(col_width) for cell in row) + ' |'
            lines.append(row_str)
        lines.append('   +' + '-'*cols*col_width + '+')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def visualize_heap(items: list) -> dict:
    """Render a heap array as a tree diagram."""
    try:
        if not items:
            return {'success': True, 'data': '(empty heap)', 'error': None}
        def _build_tree(idx):
            if idx >= len(items):
                return None
            return {'value': items[idx], 'left': _build_tree(2*idx+1), 'right': _build_tree(2*idx+2)}
        tree = _build_tree(0)
        array_repr = 'Array: [' + ', '.join(str(x) for x in items) + ']'
        tree_result = visualize_binary_tree(tree)
        return {'success': True, 'data': array_repr + '\n\nTree:\n' + tree_result['data'], 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def visualize_sorting_steps(arr: list, algorithm: str = 'bubble') -> dict:
    """Show step-by-step sorting visualization."""
    try:
        steps = []
        a = list(arr)
        def _record(arr, highlight=None):
            line = '[ '
            for i, v in enumerate(arr):
                if highlight and i in highlight:
                    line += '[' + str(v) + '] '
                else:
                    line += str(v) + ' '
            steps.append(line + ']')
        _record(a)
        if algorithm == 'bubble':
            n = len(a)
            for i in range(n):
                for j in range(n-i-1):
                    if a[j] > a[j+1]:
                        a[j], a[j+1] = a[j+1], a[j]
                        _record(a, {j, j+1})
        elif algorithm == 'insertion':
            for i in range(1, len(a)):
                key = a[i]
                j = i - 1
                while j >= 0 and a[j] > key:
                    a[j+1] = a[j]
                    j -= 1
                a[j+1] = key
                _record(a, {j+1})
        elif algorithm == 'selection':
            n = len(a)
            for i in range(n):
                min_idx = i
                for j in range(i+1, n):
                    if a[j] < a[min_idx]:
                        min_idx = j
                a[i], a[min_idx] = a[min_idx], a[i]
                _record(a, {i})
        return {'success': True, 'data': {'steps': steps, 'count': len(steps), 'final': a}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def json_to_tree_text(data, indent: int = 0, prefix: str = '') -> dict:
    """Render a JSON object as an ASCII tree."""
    try:
        lines = []
        def _render(node, depth, pfix):
            if isinstance(node, dict):
                for i, (k, v) in enumerate(node.items()):
                    is_last = i == len(node) - 1
                    connector = '`-- ' if is_last else '|-- '
                    lines.append(pfix + connector + str(k))
                    ext = '    ' if is_last else '|   '
                    _render(v, depth+1, pfix+ext)
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    is_last = i == len(node) - 1
                    connector = '`-- ' if is_last else '|-- '
                    lines.append(pfix + connector + '[' + str(i) + ']')
                    ext = '    ' if is_last else '|   '
                    _render(item, depth+1, pfix+ext)
            else:
                lines[-1] += ': ' + str(node) if lines else pfix + str(node)
        if isinstance(data, str):
            data = json.loads(data)
        lines.append('.')
        _render(data, 0, '')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def visualize_trie(words: list) -> dict:
    """Build and display a trie from a list of words."""
    try:
        root = {}
        for word in words:
            node = root
            for ch in word:
                if ch not in node:
                    node[ch] = {}
                node = node[ch]
            node['$'] = {}
        result = json_to_tree_text(root)
        return {'success': True, 'data': result['data'], 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
