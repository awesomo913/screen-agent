"""toolkit_123_config_manager.py
Manage application configs — load/save YAML, TOML, INI, JSON, env vars.
"""
import os
import json
import re
import configparser
from pathlib import Path

try:
    import yaml; HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    import tomllib; HAS_TOML = True
except ImportError:
    try:
        import tomli as tomllib; HAS_TOML = True
    except ImportError:
        HAS_TOML = False

try:
    import tomli_w; HAS_TOMLI_W = True
except ImportError:
    HAS_TOMLI_W = False

def load_json_config(path: str) -> dict:
    """Load a JSON configuration file."""
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return {'success': True, 'data': data, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def save_json_config(data: dict, path: str, indent: int = 2) -> dict:
    """Save a dict as JSON configuration file."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return {'success': True, 'data': {'path': path}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def load_yaml_config(path: str) -> dict:
    """Load a YAML configuration file."""
    try:
        if not HAS_YAML:
            return {'success': False, 'data': None, 'error': 'PyYAML not installed: pip install pyyaml'}
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return {'success': True, 'data': data, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def save_yaml_config(data: dict, path: str) -> dict:
    """Save a dict as YAML configuration file."""
    try:
        if not HAS_YAML:
            return {'success': False, 'data': None, 'error': 'PyYAML not installed'}
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        return {'success': True, 'data': {'path': path}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def load_toml_config(path: str) -> dict:
    """Load a TOML configuration file."""
    try:
        if not HAS_TOML:
            return {'success': False, 'data': None, 'error': 'tomllib not available (Python 3.11+ or pip install tomli)'}
        with open(path, 'rb') as f:
            data = tomllib.load(f)
        return {'success': True, 'data': data, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def save_toml_config(data: dict, path: str) -> dict:
    """Save a dict as TOML configuration file."""
    try:
        if not HAS_TOMLI_W:
            return save_json_config(data, path.replace('.toml', '.json'))
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'wb') as f:
            tomli_w.dump(data, f)
        return {'success': True, 'data': {'path': path}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def load_ini_config(path: str) -> dict:
    """Load an INI/CFG configuration file."""
    try:
        config = configparser.ConfigParser()
        config.read(path, encoding='utf-8')
        data = {section: dict(config[section]) for section in config.sections()}
        if 'DEFAULT' in config:
            data['DEFAULT'] = dict(config['DEFAULT'])
        return {'success': True, 'data': data, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def save_ini_config(data: dict, path: str) -> dict:
    """Save a nested dict as INI configuration file."""
    try:
        config = configparser.ConfigParser()
        for section, values in data.items():
            if section != 'DEFAULT':
                config[section] = {k: str(v) for k, v in values.items()}
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            config.write(f)
        return {'success': True, 'data': {'path': path}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def load_dotenv(path: str = '.env') -> dict:
    """Load environment variables from a .env file."""
    try:
        if not os.path.exists(path):
            return {'success': False, 'data': None, 'error': '.env file not found: ' + path}
        env_vars = {}
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                m = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$', line, re.IGNORECASE)
                if m:
                    key = m.group(1)
                    val = m.group(2).strip().strip('"').strip("'")
                    env_vars[key] = val
                    os.environ[key] = val
        return {'success': True, 'data': env_vars, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def save_dotenv(env_vars: dict, path: str = '.env') -> dict:
    """Save environment variables to a .env file."""
    try:
        lines = [key + '=' + str(val) for key, val in env_vars.items()]
        with open(path, 'w', encoding='utf-8') as f:
            f.write(chr(10).join(lines) + chr(10))
        return {'success': True, 'data': {'path': path, 'vars': len(env_vars)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_env_var(key: str, default: str = '') -> dict:
    """Get an environment variable."""
    try:
        value = os.environ.get(key, default)
        return {'success': True, 'data': {'key': key, 'value': value, 'set': key in os.environ}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def set_env_var(key: str, value: str) -> dict:
    """Set an environment variable in current process."""
    try:
        os.environ[key] = str(value)
        return {'success': True, 'data': {'key': key, 'value': value}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_env_vars(prefix: str = '') -> dict:
    """List environment variables, optionally filtered by prefix."""
    try:
        env = dict(os.environ)
        if prefix:
            env = {k: v for k, v in env.items() if k.startswith(prefix.upper())}
        return {'success': True, 'data': env, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def merge_configs(base: dict, override: dict) -> dict:
    """Deep-merge two config dicts (override takes priority)."""
    try:
        def _merge(d1, d2):
            result = dict(d1)
            for k, v in d2.items():
                if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                    result[k] = _merge(result[k], v)
                else:
                    result[k] = v
            return result
        return {'success': True, 'data': _merge(base, override), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def convert_config(input_path: str, output_path: str) -> dict:
    """Convert config between JSON, YAML, TOML, INI formats."""
    try:
        ext_in = Path(input_path).suffix.lower()
        ext_out = Path(output_path).suffix.lower()
        loaders = {'.json': load_json_config, '.yaml': load_yaml_config, '.yml': load_yaml_config, '.toml': load_toml_config, '.ini': load_ini_config, '.cfg': load_ini_config}
        savers = {'.json': save_json_config, '.yaml': save_yaml_config, '.yml': save_yaml_config, '.toml': save_toml_config, '.ini': save_ini_config}
        loader = loaders.get(ext_in)
        saver = savers.get(ext_out)
        if not loader:
            return {'success': False, 'data': None, 'error': 'Unsupported input format: ' + ext_in}
        if not saver:
            return {'success': False, 'data': None, 'error': 'Unsupported output format: ' + ext_out}
        result = loader(input_path)
        if not result['success']:
            return result
        return saver(result['data'], output_path)
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_nested_value(config: dict, key_path: str, default=None) -> dict:
    """Get a nested config value using dot notation (e.g. 'database.host')."""
    try:
        keys = key_path.split('.')
        val = config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return {'success': True, 'data': default, 'error': None}
        return {'success': True, 'data': val, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def set_nested_value(config: dict, key_path: str, value) -> dict:
    """Set a nested config value using dot notation."""
    try:
        keys = key_path.split('.')
        d = config
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
        return {'success': True, 'data': config, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
