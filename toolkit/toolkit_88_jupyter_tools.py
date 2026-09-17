"""toolkit_88_jupyter_tools.py
Work with Jupyter notebooks — parse, run cells, export, create notebooks.
"""
import json
import os
import subprocess
import sys
import re
import tempfile
from pathlib import Path

def read_notebook(path: str) -> dict:
    """Read a Jupyter notebook and extract cells."""
    try:
        with open(path, encoding='utf-8') as f:
            nb = json.load(f)
        cells = []
        for cell in nb.get('cells', []):
            cell_type = cell.get('cell_type', 'unknown')
            source = ''.join(cell.get('source', []))
            outputs = []
            for out in cell.get('outputs', []):
                if 'text' in out:
                    outputs.append({'type': 'stream', 'text': ''.join(out['text'])})
                elif 'data' in out:
                    text = ''.join(out['data'].get('text/plain', []))
                    outputs.append({'type': 'display', 'text': text})
            cells.append({'type': cell_type, 'source': source, 'outputs': outputs})
        return {'success': True, 'data': {'cells': cells, 'total': len(cells), 'kernel': nb.get('metadata', {}).get('kernelspec', {}).get('name', 'unknown')}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_code_cells(path: str) -> dict:
    """Extract only code cells from a notebook."""
    try:
        result = read_notebook(path)
        if not result['success']:
            return result
        code_cells = [c for c in result['data']['cells'] if c['type'] == 'code']
        return {'success': True, 'data': {'code_cells': code_cells, 'count': len(code_cells)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def notebook_to_script(path: str, output_path: str = '') -> dict:
    """Convert notebook code cells to a Python script."""
    try:
        result = extract_code_cells(path)
        if not result['success']:
            return result
        cells = result['data']['code_cells']
        lines = ['# Exported from: ' + os.path.basename(path), '']
        for i, cell in enumerate(cells):
            lines.append('# Cell ' + str(i+1))
            lines.append(cell['source'])
            lines.append('')
        script = '\n'.join(lines)
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(script)
        return {'success': True, 'data': {'script': script, 'cell_count': len(cells), 'output_path': output_path}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_notebook(cells: list, output_path: str = '', kernel: str = 'python3') -> dict:
    """Create a new Jupyter notebook from a list of cell dicts."""
    try:
        nb_cells = []
        for cell in cells:
            ctype = cell.get('type', 'code')
            source = cell.get('source', '')
            nb_cell = {'cell_type': ctype, 'metadata': {}, 'source': source.splitlines(keepends=True)}
            if ctype == 'code':
                nb_cell['outputs'] = []
                nb_cell['execution_count'] = None
            nb_cells.append(nb_cell)
        nb = {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': kernel}, 'language_info': {'name': 'python', 'version': '3.11.0'}}, 'cells': nb_cells}
        if not output_path:
            output_path = os.path.join(tempfile.gettempdir(), 'new_notebook.ipynb')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(nb, f, indent=1)
        return {'success': True, 'data': {'path': output_path, 'cells': len(nb_cells)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_notebook(path: str, timeout: int = 60, output_path: str = '') -> dict:
    """Execute a Jupyter notebook using nbconvert."""
    try:
        out = output_path or path.replace('.ipynb', '_executed.ipynb')
        result = subprocess.run([sys.executable, '-m', 'nbconvert', '--to', 'notebook', '--execute', '--output', out, path], capture_output=True, text=True, timeout=timeout)
        success = result.returncode == 0
        return {'success': success, 'data': {'output_path': out, 'stdout': result.stdout, 'stderr': result.stderr[:1000]}, 'error': None if success else result.stderr[:500]}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def notebook_to_html(path: str, output_path: str = '') -> dict:
    """Convert notebook to HTML using nbconvert."""
    try:
        out = output_path or path.replace('.ipynb', '.html')
        result = subprocess.run([sys.executable, '-m', 'nbconvert', '--to', 'html', '--output', out, path], capture_output=True, text=True, timeout=30)
        success = result.returncode == 0
        return {'success': success, 'data': {'output_path': out}, 'error': None if success else result.stderr[:500]}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def notebook_to_pdf(path: str, output_path: str = '') -> dict:
    """Convert notebook to PDF using nbconvert."""
    try:
        out = output_path or path.replace('.ipynb', '.pdf')
        result = subprocess.run([sys.executable, '-m', 'nbconvert', '--to', 'pdf', '--output', out, path], capture_output=True, text=True, timeout=60)
        success = result.returncode == 0
        return {'success': success, 'data': {'output_path': out}, 'error': None if success else result.stderr[:500]}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_notebooks(directory: str = '.') -> dict:
    """List all Jupyter notebooks in a directory."""
    try:
        path = Path(directory)
        notebooks = list(path.rglob('*.ipynb'))
        result = [{'path': str(nb), 'name': nb.name, 'size': nb.stat().st_size} for nb in notebooks]
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_notebook_outputs(path: str) -> dict:
    """Get all cell outputs from an executed notebook."""
    try:
        with open(path, encoding='utf-8') as f:
            nb = json.load(f)
        outputs = []
        for i, cell in enumerate(nb.get('cells', [])):
            if cell.get('cell_type') == 'code':
                for out in cell.get('outputs', []):
                    if 'text' in out:
                        outputs.append({'cell': i+1, 'type': 'stream', 'text': ''.join(out['text'])})
                    elif 'traceback' in out:
                        outputs.append({'cell': i+1, 'type': 'error', 'text': '\n'.join(out.get('traceback', []))})
        return {'success': True, 'data': outputs, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def add_cell_to_notebook(path: str, source: str, cell_type: str = 'code', position: int = -1) -> dict:
    """Add a cell to an existing notebook file."""
    try:
        with open(path, encoding='utf-8') as f:
            nb = json.load(f)
        new_cell = {'cell_type': cell_type, 'metadata': {}, 'source': source.splitlines(keepends=True)}
        if cell_type == 'code':
            new_cell['outputs'] = []
            new_cell['execution_count'] = None
        if position == -1:
            nb['cells'].append(new_cell)
        else:
            nb['cells'].insert(position, new_cell)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(nb, f, indent=1)
        return {'success': True, 'data': {'path': path, 'total_cells': len(nb['cells'])}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def clear_notebook_outputs(path: str, output_path: str = '') -> dict:
    """Remove all outputs from a notebook."""
    try:
        with open(path, encoding='utf-8') as f:
            nb = json.load(f)
        for cell in nb.get('cells', []):
            if cell.get('cell_type') == 'code':
                cell['outputs'] = []
                cell['execution_count'] = None
        out = output_path or path
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(nb, f, indent=1)
        return {'success': True, 'data': {'path': out}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def start_jupyter_server(port: int = 8888, directory: str = '.') -> dict:
    """Start a Jupyter notebook server in background."""
    try:
        proc = subprocess.Popen([sys.executable, '-m', 'jupyter', 'notebook', '--no-browser', '--port=' + str(port), '--notebook-dir=' + directory], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        import time; time.sleep(2)
        if proc.poll() is None:
            return {'success': True, 'data': {'pid': proc.pid, 'port': port, 'url': 'http://localhost:' + str(port)}, 'error': None}
        return {'success': False, 'data': None, 'error': 'Server failed to start'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
