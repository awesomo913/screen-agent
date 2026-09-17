"""toolkit_102_json_schema_tools.py
Generate, validate, and work with JSON Schema.
"""
import json
import re

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

def generate_schema_from_json(json_str: str) -> dict:
    """Auto-generate a JSON Schema from a JSON example."""
    try:
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        def _infer(val):
            if isinstance(val, bool):
                return {'type': 'boolean'}
            elif isinstance(val, int):
                return {'type': 'integer'}
            elif isinstance(val, float):
                return {'type': 'number'}
            elif isinstance(val, str):
                s = {'type': 'string'}
                if re.match(r'^\d{4}-\d{2}-\d{2}', val):
                    s['format'] = 'date'
                elif re.match(r'^[a-zA-Z0-9._%+-]+@', val):
                    s['format'] = 'email'
                elif val.startswith('http'):
                    s['format'] = 'uri'
                return s
            elif isinstance(val, list):
                if val:
                    return {'type': 'array', 'items': _infer(val[0])}
                return {'type': 'array'}
            elif isinstance(val, dict):
                props = {k: _infer(v) for k, v in val.items()}
                return {'type': 'object', 'properties': props, 'required': list(val.keys())}
            elif val is None:
                return {'type': 'null'}
            return {}
        schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema', **_infer(data)}
        return {'success': True, 'data': schema, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def validate_against_schema(data_str: str, schema_str: str) -> dict:
    """Validate JSON data against a JSON Schema."""
    try:
        data = json.loads(data_str) if isinstance(data_str, str) else data_str
        schema = json.loads(schema_str) if isinstance(schema_str, str) else schema_str
        if HAS_JSONSCHEMA:
            try:
                jsonschema.validate(instance=data, schema=schema)
                return {'success': True, 'data': {'valid': True, 'errors': []}, 'error': None}
            except jsonschema.ValidationError as e:
                return {'success': True, 'data': {'valid': False, 'errors': [str(e.message)]}, 'error': None}
            except jsonschema.SchemaError as e:
                return {'success': False, 'data': None, 'error': 'Invalid schema: ' + str(e.message)}
        return {'success': False, 'data': None, 'error': 'jsonschema not installed: pip install jsonschema'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_fake_data(schema_str: str, count: int = 1) -> dict:
    """Generate fake data from a JSON Schema."""
    try:
        import random, string
        schema = json.loads(schema_str) if isinstance(schema_str, str) else schema_str
        def _generate(s):
            t = s.get('type', 'string')
            if t == 'string':
                fmt = s.get('format','')
                if fmt == 'email':
                    return 'user' + str(random.randint(1,99)) + '@example.com'
                elif fmt == 'date':
                    return '2024-0' + str(random.randint(1,9)) + '-' + str(random.randint(10,28))
                elif fmt == 'uri':
                    return 'https://example.com/' + ''.join(random.choices(string.ascii_lowercase, k=5))
                min_len = s.get('minLength', 5)
                max_len = s.get('maxLength', 15)
                return ''.join(random.choices(string.ascii_lowercase, k=random.randint(min_len, max_len)))
            elif t == 'integer':
                return random.randint(s.get('minimum',0), s.get('maximum',100))
            elif t == 'number':
                return round(random.uniform(s.get('minimum',0.0), s.get('maximum',100.0)), 2)
            elif t == 'boolean':
                return random.choice([True, False])
            elif t == 'array':
                items_schema = s.get('items', {})
                min_items = s.get('minItems', 1)
                max_items = s.get('maxItems', 3)
                return [_generate(items_schema) for _ in range(random.randint(min_items, max_items))]
            elif t == 'object':
                return {k: _generate(v) for k, v in s.get('properties', {}).items()}
            elif t == 'null':
                return None
            return None
        results = [_generate(schema) for _ in range(count)]
        return {'success': True, 'data': results if count > 1 else results[0], 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def merge_schemas(schema1_str: str, schema2_str: str) -> dict:
    """Merge two JSON schemas using allOf."""
    try:
        s1 = json.loads(schema1_str) if isinstance(schema1_str, str) else schema1_str
        s2 = json.loads(schema2_str) if isinstance(schema2_str, str) else schema2_str
        merged = {'allOf': [s1, s2]}
        return {'success': True, 'data': merged, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def schema_to_typescript(schema_str: str, name: str = 'MyType') -> dict:
    """Convert JSON Schema to TypeScript type definition."""
    try:
        schema = json.loads(schema_str) if isinstance(schema_str, str) else schema_str
        type_map = {'string': 'string', 'integer': 'number', 'number': 'number', 'boolean': 'boolean', 'null': 'null', 'array': 'any[]', 'object': 'Record<string, any>'}
        def _convert(s, indent=0):
            t = s.get('type', 'any')
            if t == 'object':
                props = s.get('properties', {})
                required = s.get('required', [])
                lines = ['{']
                for k, v in props.items():
                    opt = '' if k in required else '?'
                    lines.append('  ' * (indent+1) + k + opt + ': ' + _convert(v, indent+1) + ';')
                lines.append('  ' * indent + '}')
                return '\n'.join(lines)
            elif t == 'array':
                items = s.get('items', {})
                return _convert(items, indent) + '[]'
            return type_map.get(t, 'any')
        ts = 'type ' + name + ' = ' + _convert(schema) + ';'
        return {'success': True, 'data': ts, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def prettify_schema(schema_str: str) -> dict:
    """Pretty-print a JSON Schema."""
    try:
        schema = json.loads(schema_str) if isinstance(schema_str, str) else schema_str
        return {'success': True, 'data': json.dumps(schema, indent=2), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_required_fields(schema_str: str) -> dict:
    """Extract all required fields from a JSON Schema."""
    try:
        schema = json.loads(schema_str) if isinstance(schema_str, str) else schema_str
        required = schema.get('required', [])
        all_props = list(schema.get('properties', {}).keys())
        optional = [p for p in all_props if p not in required]
        return {'success': True, 'data': {'required': required, 'optional': optional, 'all': all_props}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def validate_json_online(json_str: str) -> dict:
    """Validate JSON syntax and return parsed object."""
    try:
        data = json.loads(json_str)
        return {'success': True, 'data': {'valid': True, 'type': type(data).__name__, 'keys': list(data.keys()) if isinstance(data, dict) else None, 'length': len(data) if hasattr(data, '__len__') else None}, 'error': None}
    except json.JSONDecodeError as e:
        return {'success': True, 'data': {'valid': False, 'error': str(e), 'line': e.lineno, 'col': e.colno}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
