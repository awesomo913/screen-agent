"""toolkit_91_api_mock_server.py
Create and run a mock HTTP API server for testing — using http.server stdlib.
"""
import json
import threading
import re
import time
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

_mock_data = {}
_server_instance = [None]
_server_thread = [None]

class _MockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    def _send(self, code, body, content_type='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode() if not isinstance(body, bytes) else body)
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        self.end_headers()
    def _handle(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        key = method + ' ' + path
        if key in _mock_data:
            route = _mock_data[key]
            delay = route.get('delay', 0)
            if delay:
                time.sleep(delay)
            self._send(route.get('status', 200), route.get('body', {}))
        else:
            for pattern, route in _mock_data.items():
                m_method, _, m_path = pattern.partition(' ')
                if m_method == method:
                    regex = re.sub(r'\{[^}]+\}', '([^/]+)', m_path) + '$'
                    if re.match(regex, path):
                        self._send(route.get('status', 200), route.get('body', {}))
                        return
            self._send(404, {'error': 'Not found', 'path': path})
    def do_GET(self): self._handle('GET')
    def do_POST(self): self._handle('POST')
    def do_PUT(self): self._handle('PUT')
    def do_DELETE(self): self._handle('DELETE')

def start_mock_server(port: int = 8765) -> dict:
    """Start a mock HTTP API server on the given port."""
    try:
        if _server_instance[0]:
            return {'success': True, 'data': {'running': True, 'port': port, 'note': 'Already running'}, 'error': None}
        server = HTTPServer(('localhost', port), _MockHandler)
        _server_instance[0] = server
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        _server_thread[0] = t
        return {'success': True, 'data': {'running': True, 'port': port, 'url': 'http://localhost:' + str(port)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def stop_mock_server() -> dict:
    """Stop the running mock server."""
    try:
        if _server_instance[0]:
            _server_instance[0].shutdown()
            _server_instance[0] = None
            return {'success': True, 'data': {'stopped': True}, 'error': None}
        return {'success': True, 'data': {'stopped': False, 'note': 'No server running'}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def add_route(method: str, path: str, body, status: int = 200, delay: float = 0) -> dict:
    """Add a mock route. method: GET/POST/PUT/DELETE. body: dict or list."""
    try:
        key = method.upper() + ' ' + path
        _mock_data[key] = {'body': body, 'status': status, 'delay': delay}
        return {'success': True, 'data': {'route': key, 'status': status}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def remove_route(method: str, path: str) -> dict:
    """Remove a mock route."""
    try:
        key = method.upper() + ' ' + path
        removed = _mock_data.pop(key, None)
        return {'success': True, 'data': {'removed': bool(removed)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_routes() -> dict:
    """List all registered mock routes."""
    try:
        routes = [{'route': k, 'status': v.get('status', 200), 'delay': v.get('delay', 0)} for k, v in _mock_data.items()]
        return {'success': True, 'data': routes, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def clear_routes() -> dict:
    """Clear all registered mock routes."""
    try:
        _mock_data.clear()
        return {'success': True, 'data': {'cleared': True}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def load_routes_from_json(json_path: str) -> dict:
    """Load mock routes from a JSON file."""
    try:
        with open(json_path, encoding='utf-8') as f:
            routes = json.load(f)
        count = 0
        for r in routes:
            key = r.get('method','GET').upper() + ' ' + r.get('path','/')
            _mock_data[key] = {'body': r.get('body', {}), 'status': r.get('status', 200), 'delay': r.get('delay', 0)}
            count += 1
        return {'success': True, 'data': {'loaded': count}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def save_routes_to_json(json_path: str) -> dict:
    """Save current routes to a JSON file."""
    try:
        routes = []
        for key, val in _mock_data.items():
            method, _, path = key.partition(' ')
            routes.append({'method': method, 'path': path, 'body': val.get('body'), 'status': val.get('status', 200), 'delay': val.get('delay', 0)})
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(routes, f, indent=2)
        return {'success': True, 'data': {'saved': len(routes), 'path': json_path}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def test_route(method: str, path: str, port: int = 8765) -> dict:
    """Test a mock route by making a real request."""
    try:
        import urllib.request
        url = 'http://localhost:' + str(port) + path
        req = urllib.request.Request(url, method=method.upper())
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            return {'success': True, 'data': {'status': resp.status, 'body': body}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_server_status() -> dict:
    """Check if the mock server is running."""
    try:
        running = _server_instance[0] is not None
        return {'success': True, 'data': {'running': running, 'routes': len(_mock_data)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def setup_rest_api_mock(resource_name: str, items: list, port: int = 8765) -> dict:
    """Quick setup: create CRUD mock for a resource."""
    try:
        path = '/' + resource_name
        add_route('GET', path, items)
        add_route('GET', path + '/{id}', items[0] if items else {})
        add_route('POST', path, {'created': True, 'id': len(items) + 1})
        add_route('PUT', path + '/{id}', {'updated': True})
        add_route('DELETE', path + '/{id}', {'deleted': True})
        result = start_mock_server(port)
        return {'success': True, 'data': {'routes_created': 5, 'resource': resource_name, 'server': result.get('data')}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
