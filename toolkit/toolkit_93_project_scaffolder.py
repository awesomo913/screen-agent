"""toolkit_93_project_scaffolder.py
Scaffold new coding projects — directories, boilerplate, configs.
"""
import os
import json
import subprocess
import sys
from pathlib import Path
import datetime

def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def create_python_project(name: str, directory: str = '.', author: str = '', description: str = '') -> dict:
    """Scaffold a standard Python project structure."""
    try:
        base = os.path.join(directory, name)
        os.makedirs(base, exist_ok=True)
        pkg = name.replace('-','_')
        structure = {
            os.path.join(base, 'README.md'): '# ' + name + '\n\n' + (description or 'A Python project.') + '\n',
            os.path.join(base, 'setup.py'): 'from setuptools import setup, find_packages\n\nsetup(\n    name="' + name + '",\n    version="0.1.0",\n    author="' + author + '",\n    packages=find_packages(),\n)\n',
            os.path.join(base, 'pyproject.toml'): '[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.backends.legacy:build"\n',
            os.path.join(base, 'requirements.txt'): '# Add dependencies here\n',
            os.path.join(base, '.gitignore'): '__pycache__/\n*.pyc\n*.egg-info/\ndist/\nbuild/\n.env\nvenv/\n',
            os.path.join(base, pkg, '__init__.py'): '"""' + name + ' package."""\n__version__ = "0.1.0"\n',
            os.path.join(base, pkg, 'main.py'): '"""Main module."""\n\n\ndef main():\n    """Entry point."""\n    print("Hello from ' + name + '!")\n',
            os.path.join(base, 'tests', '__init__.py'): '',
            os.path.join(base, 'tests', 'test_main.py'): 'import unittest\nfrom ' + pkg + ' import main\n\nclass TestMain(unittest.TestCase):\n    def test_placeholder(self):\n        self.assertTrue(True)\n',
        }
        for path, content in structure.items():
            _write(path, content)
        return {'success': True, 'data': {'project_path': base, 'files_created': len(structure)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_flask_app(name: str, directory: str = '.') -> dict:
    """Scaffold a Flask web application."""
    try:
        base = os.path.join(directory, name)
        structure = {
            os.path.join(base, 'app.py'): 'from flask import Flask, jsonify, request\n\napp = Flask(__name__)\n\n@app.route("/")\ndef index():\n    return jsonify({"message": "Hello from ' + name + '!"})\n\n@app.route("/api/health")\ndef health():\n    return jsonify({"status": "ok"})\n\nif __name__ == "__main__":\n    app.run(debug=True)\n',
            os.path.join(base, 'requirements.txt'): 'flask>=2.0\n',
            os.path.join(base, 'README.md'): '# ' + name + '\n\nRun: `python app.py`\n',
            os.path.join(base, '.gitignore'): '__pycache__/\n*.pyc\n.env\nvenv/\n',
            os.path.join(base, 'templates', 'index.html'): '<!DOCTYPE html>\n<html>\n<head><title>' + name + '</title></head>\n<body>\n<h1>' + name + '</h1>\n</body>\n</html>\n',
            os.path.join(base, 'static', 'style.css'): 'body { font-family: sans-serif; margin: 20px; }\n',
        }
        for path, content in structure.items():
            _write(path, content)
        return {'success': True, 'data': {'project_path': base, 'files_created': len(structure), 'run': 'cd ' + base + ' && pip install flask && python app.py'}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_fastapi_app(name: str, directory: str = '.') -> dict:
    """Scaffold a FastAPI application."""
    try:
        base = os.path.join(directory, name)
        structure = {
            os.path.join(base, 'main.py'): 'from fastapi import FastAPI\nfrom pydantic import BaseModel\n\napp = FastAPI(title="' + name + '")\n\nclass Item(BaseModel):\n    name: str\n    value: float = 0.0\n\n@app.get("/")\ndef root():\n    return {"message": "Welcome to ' + name + '"}\n\n@app.get("/health")\ndef health():\n    return {"status": "ok"}\n\n@app.post("/items")\ndef create_item(item: Item):\n    return {"created": item.dict()}\n',
            os.path.join(base, 'requirements.txt'): 'fastapi>=0.100\nuvicorn>=0.20\npydantic>=2.0\n',
            os.path.join(base, 'README.md'): '# ' + name + '\n\nRun: `uvicorn main:app --reload`\n',
            os.path.join(base, '.gitignore'): '__pycache__/\n*.pyc\n.env\nvenv/\n',
        }
        for path, content in structure.items():
            _write(path, content)
        return {'success': True, 'data': {'project_path': base, 'files_created': len(structure), 'run': 'cd ' + base + ' && pip install fastapi uvicorn && uvicorn main:app --reload'}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_node_project(name: str, directory: str = '.') -> dict:
    """Scaffold a basic Node.js/Express project."""
    try:
        base = os.path.join(directory, name)
        pkg_json = json.dumps({'name': name, 'version': '1.0.0', 'main': 'index.js', 'scripts': {'start': 'node index.js', 'dev': 'nodemon index.js'}, 'dependencies': {'express': '^4.18.0'}}, indent=2)
        structure = {
            os.path.join(base, 'package.json'): pkg_json,
            os.path.join(base, 'index.js'): 'const express = require(\'express\');\nconst app = express();\nconst PORT = process.env.PORT || 3000;\n\napp.use(express.json());\n\napp.get(\'/\', (req, res) => {\n  res.json({ message: \'Hello from ' + name + '!\' });\n});\n\napp.listen(PORT, () => console.log(`Server running on port ${PORT}`));\n',
            os.path.join(base, 'README.md'): '# ' + name + '\n\nRun: `npm install && npm start`\n',
            os.path.join(base, '.gitignore'): 'node_modules/\n.env\ndist/\n',
            os.path.join(base, '.env.example'): 'PORT=3000\n',
        }
        for path, content in structure.items():
            _write(path, content)
        return {'success': True, 'data': {'project_path': base, 'files_created': len(structure)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_dockerfile(base_image: str = 'python:3.11-slim', workdir: str = '/app', entry_cmd: str = 'python main.py', expose_port: int = 8000) -> dict:
    """Generate a Dockerfile."""
    try:
        content = 'FROM ' + base_image + '\nWORKDIR ' + workdir + '\nCOPY requirements.txt .\nRUN pip install -r requirements.txt\nCOPY . .\nEXPOSE ' + str(expose_port) + '\nCMD ["' + '", "'.join(entry_cmd.split()) + '"]\n'
        return {'success': True, 'data': content, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_github_workflow(project_type: str = 'python') -> dict:
    """Create a GitHub Actions CI workflow YAML."""
    try:
        if project_type == 'python':
            yaml = 'name: CI\non:\n  push:\n    branches: [main]\n  pull_request:\n    branches: [main]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v3\n      - uses: actions/setup-python@v4\n        with:\n          python-version: "3.11"\n      - run: pip install -r requirements.txt\n      - run: python -m pytest\n'
        elif project_type == 'node':
            yaml = 'name: CI\non:\n  push:\n    branches: [main]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v3\n      - uses: actions/setup-node@v3\n        with:\n          node-version: 18\n      - run: npm install\n      - run: npm test\n'
        else:
            yaml = '# Add your CI workflow here\n'
        return {'success': True, 'data': yaml, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def init_git_repo(directory: str = '.', initial_branch: str = 'main') -> dict:
    """Initialize a git repository."""
    try:
        result = subprocess.run(['git', 'init', '-b', initial_branch], capture_output=True, text=True, cwd=directory)
        if result.returncode != 0:
            result = subprocess.run(['git', 'init'], capture_output=True, text=True, cwd=directory)
        return {'success': result.returncode==0, 'data': {'path': directory, 'branch': initial_branch}, 'error': result.stderr if result.returncode!=0 else None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_makefile(targets: dict) -> dict:
    """Create a Makefile from a dict of {target: [commands]}."""
    try:
        lines = []
        for target, commands in targets.items():
            deps = commands.get('deps', '') if isinstance(commands, dict) else ''
            cmds = commands.get('cmds', []) if isinstance(commands, dict) else commands if isinstance(commands, list) else [str(commands)]
            lines.append(target + ': ' + deps)
            for cmd in cmds:
                lines.append('\t' + cmd)
            lines.append('')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_readme(project_name: str, description: str, install_cmd: str = '', usage: str = '', license_name: str = 'MIT') -> dict:
    """Generate a README.md template."""
    try:
        lines = ['# ' + project_name, '', '> ' + description, '', '## Installation', '', '```bash', install_cmd or '# TODO', '```', '', '## Usage', '', '```', usage or '# TODO', '```', '', '## License', '', license_name]
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
