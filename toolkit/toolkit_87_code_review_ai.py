"""toolkit_87_code_review_ai.py
AI-assisted code review via free APIs (Gemini, OpenAI-compatible, Ollama).
"""
import json
import urllib.request
import urllib.parse
import re

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def _post(url, payload, headers):
    try:
        body = json.dumps(payload).encode()
        if HAS_REQUESTS:
            r = requests.post(url, json=payload, headers=headers, timeout=60)
            return r.status_code, r.json()
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as e:
        return 0, {'error': str(e)}

def review_with_ollama(code: str, language: str = 'python', model: str = 'llava:7b', host: str = 'http://localhost:11434') -> dict:
    """Review code using local Ollama model."""
    try:
        prompt = 'Review this ' + language + ' code for bugs, style issues, and improvements:\n\n```' + language + '\n' + code + '\n```\n\nProvide specific feedback.'
        status, resp = _post(host + '/api/generate', {'model': model, 'prompt': prompt, 'stream': False}, {'Content-Type': 'application/json'})
        if status == 200:
            review = resp.get('response', '')
            return {'success': True, 'data': {'review': review, 'model': model}, 'error': None}
        return {'success': False, 'data': None, 'error': 'Ollama error: ' + str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def review_with_gemini(code: str, language: str = 'python', api_key: str = '') -> dict:
    """Review code using Google Gemini free API."""
    try:
        if not api_key:
            return {'success': False, 'data': None, 'error': 'Gemini API key required'}
        prompt = 'Review this ' + language + ' code. Find bugs, suggest improvements, check style:\n\n```' + language + '\n' + code + '\n```'
        url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=' + api_key
        payload = {'contents': [{'parts': [{'text': prompt}]}]}
        status, resp = _post(url, payload, {'Content-Type': 'application/json'})
        if status == 200:
            text = resp.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            return {'success': True, 'data': {'review': text, 'model': 'gemini-pro'}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def review_with_openai_compatible(code: str, language: str = 'python', api_key: str = '', base_url: str = 'https://api.openai.com/v1', model: str = 'gpt-3.5-turbo') -> dict:
    """Review code using any OpenAI-compatible API."""
    try:
        prompt = 'Review this ' + language + ' code:\n\n```' + language + '\n' + code + '\n```\n\nList: 1) Bugs 2) Improvements 3) Style issues'
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + api_key}
        payload = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 1000}
        status, resp = _post(base_url + '/chat/completions', payload, headers)
        if status == 200:
            text = resp.get('choices', [{}])[0].get('message', {}).get('content', '')
            return {'success': True, 'data': {'review': text, 'model': model}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def ask_ollama(question: str, model: str = 'llava:7b', host: str = 'http://localhost:11434') -> dict:
    """Ask Ollama a general coding question."""
    try:
        status, resp = _post(host + '/api/generate', {'model': model, 'prompt': question, 'stream': False}, {'Content-Type': 'application/json'})
        if status == 200:
            return {'success': True, 'data': resp.get('response', ''), 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def explain_code_with_ollama(code: str, language: str = 'python', model: str = 'llava:7b', host: str = 'http://localhost:11434') -> dict:
    """Get a plain-English explanation of code from Ollama."""
    try:
        prompt = 'Explain what this ' + language + ' code does in plain English:\n\n```' + language + '\n' + code + '\n```'
        status, resp = _post(host + '/api/generate', {'model': model, 'prompt': prompt, 'stream': False}, {'Content-Type': 'application/json'})
        if status == 200:
            return {'success': True, 'data': resp.get('response', ''), 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_code_with_ollama(prompt: str, language: str = 'python', model: str = 'llava:7b', host: str = 'http://localhost:11434') -> dict:
    """Generate code from a natural language prompt using Ollama."""
    try:
        full_prompt = 'Write ' + language + ' code for: ' + prompt + '\n\nReturn only the code, no explanation.'
        status, resp = _post(host + '/api/generate', {'model': model, 'prompt': full_prompt, 'stream': False}, {'Content-Type': 'application/json'})
        if status == 200:
            text = resp.get('response', '')
            code_match = re.search(r'```(?:\w+)?\n(.*?)```', text, re.DOTALL)
            extracted = code_match.group(1).strip() if code_match else text.strip()
            return {'success': True, 'data': {'code': extracted, 'raw': text}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fix_bug_with_ollama(code: str, error_message: str, language: str = 'python', model: str = 'llava:7b', host: str = 'http://localhost:11434') -> dict:
    """Ask Ollama to fix a bug given code and error message."""
    try:
        prompt = 'Fix this ' + language + ' code.\n\nError: ' + error_message + '\n\nCode:\n```' + language + '\n' + code + '\n```\n\nReturn only the fixed code.'
        status, resp = _post(host + '/api/generate', {'model': model, 'prompt': prompt, 'stream': False}, {'Content-Type': 'application/json'})
        if status == 200:
            text = resp.get('response', '')
            code_match = re.search(r'```(?:\w+)?\n(.*?)```', text, re.DOTALL)
            fixed = code_match.group(1).strip() if code_match else text.strip()
            return {'success': True, 'data': {'fixed_code': fixed, 'raw': text}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_ollama_models(host: str = 'http://localhost:11434') -> dict:
    """List models available in local Ollama instance."""
    try:
        if HAS_REQUESTS:
            r = requests.get(host + '/api/tags', timeout=5)
            return {'success': True, 'data': [m['name'] for m in r.json().get('models',[])], 'error': None}
        with urllib.request.urlopen(host + '/api/tags', timeout=5) as resp:
            data = json.loads(resp.read())
        return {'success': True, 'data': [m['name'] for m in data.get('models',[])], 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': 'Ollama not running or unreachable: ' + str(e)}

def check_ollama_status(host: str = 'http://localhost:11434') -> dict:
    """Check if Ollama is running locally."""
    try:
        if HAS_REQUESTS:
            r = requests.get(host, timeout=3)
            return {'success': True, 'data': {'running': True, 'host': host}, 'error': None}
        urllib.request.urlopen(host, timeout=3)
        return {'success': True, 'data': {'running': True, 'host': host}, 'error': None}
    except:
        return {'success': True, 'data': {'running': False, 'host': host}, 'error': None}

def generate_code_with_gemini(prompt: str, language: str = 'python', api_key: str = '') -> dict:
    """Generate code using Gemini free API."""
    try:
        if not api_key:
            return {'success': False, 'data': None, 'error': 'Gemini API key required'}
        full_prompt = 'Write ' + language + ' code for: ' + prompt + '. Return only the code.'
        url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=' + api_key
        payload = {'contents': [{'parts': [{'text': full_prompt}]}]}
        status, resp = _post(url, payload, {'Content-Type': 'application/json'})
        if status == 200:
            text = resp.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            code_match = re.search(r'```(?:\w+)?\n(.*?)```', text, re.DOTALL)
            code = code_match.group(1).strip() if code_match else text.strip()
            return {'success': True, 'data': {'code': code, 'raw': text}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
