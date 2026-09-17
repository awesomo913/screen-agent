"""toolkit_89_html_generator.py
Generate HTML pages, components, and forms programmatically.
"""
import re
import json
import os

def _attrs(attrs: dict) -> str:
    if not attrs:
        return ''
    return ' ' + ' '.join(k + '="' + str(v) + '"' for k, v in attrs.items())

def tag(name: str, content: str = '', attrs: dict = {}, self_closing: bool = False) -> dict:
    """Create an HTML tag."""
    try:
        a = _attrs(attrs)
        if self_closing:
            html = '<' + name + a + '>'
        else:
            html = '<' + name + a + '>' + content + '</' + name + '>'
        return {'success': True, 'data': html, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_page(title: str, body_content: str, css: str = '', js: str = '', charset: str = 'UTF-8') -> dict:
    """Create a complete HTML5 page."""
    try:
        style = '<style>' + css + '</style>' if css else ''
        script = '<script>' + js + '</script>' if js else ''
        html = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="' + charset + '">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n  <title>' + title + '</title>\n  ' + style + '\n</head>\n<body>\n' + body_content + '\n' + script + '\n</body>\n</html>')
        return {'success': True, 'data': html, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_table(headers: list, rows: list, table_attrs: dict = {}) -> dict:
    """Create an HTML table from headers and rows."""
    try:
        th = ''.join('<th>' + str(h) + '</th>' for h in headers)
        thead = '<thead><tr>' + th + '</tr></thead>'
        tbody_rows = []
        for row in rows:
            tds = ''.join('<td>' + str(c) + '</td>' for c in row)
            tbody_rows.append('<tr>' + tds + '</tr>')
        tbody = '<tbody>' + ''.join(tbody_rows) + '</tbody>'
        a = _attrs(table_attrs)
        html = '<table' + a + '>' + thead + tbody + '</table>'
        return {'success': True, 'data': html, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_form(fields: list, action: str = '#', method: str = 'POST', submit_label: str = 'Submit') -> dict:
    """Create an HTML form. fields: [{name, type, label, required, placeholder}]."""
    try:
        html_fields = []
        for f in fields:
            fname = f.get('name', 'field')
            ftype = f.get('type', 'text')
            label = f.get('label', fname)
            required = 'required' if f.get('required') else ''
            placeholder = f.get('placeholder', '')
            options = f.get('options', [])
            if ftype == 'textarea':
                inp = '<textarea name="' + fname + '" id="' + fname + '" ' + required + '></textarea>'
            elif ftype == 'select':
                opts = ''.join('<option value="' + str(o) + '">' + str(o) + '</option>' for o in options)
                inp = '<select name="' + fname + '" id="' + fname + '" ' + required + '>' + opts + '</select>'
            elif ftype == 'checkbox':
                inp = '<input type="checkbox" name="' + fname + '" id="' + fname + '" ' + required + '>'
            else:
                inp = '<input type="' + ftype + '" name="' + fname + '" id="' + fname + '" placeholder="' + placeholder + '" ' + required + '>'
            html_fields.append('<div class="form-group"><label for="' + fname + '">' + label + '</label>' + inp + '</div>')
        form = '<form action="' + action + '" method="' + method + '">' + '\n'.join(html_fields) + '<button type="submit">' + submit_label + '</button></form>'
        return {'success': True, 'data': form, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_navbar(brand: str, links: list, brand_url: str = '/') -> dict:
    """Create a simple HTML navbar. links: [{text, href}]."""
    try:
        link_items = ''.join('<a href="' + l.get('href','#') + '">' + l.get('text','') + '</a>' for l in links)
        html = '<nav class="navbar"><a class="brand" href="' + brand_url + '">' + brand + '</a><div class="nav-links">' + link_items + '</div></nav>'
        return {'success': True, 'data': html, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_card(title: str, content: str, footer: str = '', image_url: str = '') -> dict:
    """Create a Bootstrap-style card."""
    try:
        img = '<img src="' + image_url + '" class="card-img-top" alt="' + title + '">' if image_url else ''
        footer_html = '<div class="card-footer">' + footer + '</div>' if footer else ''
        html = '<div class="card">' + img + '<div class="card-body"><h5 class="card-title">' + title + '</h5><p class="card-text">' + content + '</p></div>' + footer_html + '</div>'
        return {'success': True, 'data': html, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_alert(message: str, alert_type: str = 'info') -> dict:
    """Create a Bootstrap-style alert. types: success, warning, danger, info."""
    try:
        html = '<div class="alert alert-' + alert_type + '" role="alert">' + message + '</div>'
        return {'success': True, 'data': html, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_list(items: list, ordered: bool = False) -> dict:
    """Create an HTML ordered or unordered list."""
    try:
        lis = ''.join('<li>' + str(i) + '</li>' for i in items)
        tag_name = 'ol' if ordered else 'ul'
        html = '<' + tag_name + '>' + lis + '</' + tag_name + '>'
        return {'success': True, 'data': html, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_grid(columns: list, gap: str = '1rem') -> dict:
    """Create a CSS Grid layout wrapper."""
    try:
        cols_html = ''.join('<div class="grid-col">' + str(c) + '</div>' for c in columns)
        style = 'display:grid;grid-template-columns:repeat(' + str(len(columns)) + ',1fr);gap:' + gap
        html = '<div class="grid" style="' + style + '">' + cols_html + '</div>'
        return {'success': True, 'data': html, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_dashboard_page(title: str, widgets: list) -> dict:
    """Create a simple dashboard HTML page with metric cards."""
    try:
        css = 'body{font-family:sans-serif;background:#f5f5f5;margin:0;padding:20px}.dashboard{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem}.card{background:white;border-radius:8px;padding:20px;box-shadow:0 2px 4px rgba(0,0,0,.1)}.card h3{margin:0;font-size:2rem;color:#333}.card p{margin:0;color:#666}'
        cards = ''
        for w in widgets:
            cards += '<div class="card"><p>' + w.get('label','') + '</p><h3>' + str(w.get('value','')) + '</h3></div>'
        body = '<h1>' + title + '</h1><div class="dashboard">' + cards + '</div>'
        return create_page(title, body, css)
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def save_html(html: str, path: str) -> dict:
    """Save HTML string to a file."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        return {'success': True, 'data': {'path': path, 'size': len(html)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def json_to_html_table(json_str: str, table_attrs: dict = {}) -> dict:
    """Convert a JSON array to an HTML table."""
    try:
        data = json.loads(json_str)
        if not isinstance(data, list) or not data:
            return {'success': False, 'data': None, 'error': 'JSON must be a non-empty array'}
        headers = list(data[0].keys())
        rows = [[str(row.get(h,'')) for h in headers] for row in data]
        return create_table(headers, rows, table_attrs)
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_code_block(code: str, language: str = '') -> dict:
    """Create an HTML code block with syntax highlighting placeholder."""
    try:
        escaped = code.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        html = '<pre><code class="language-' + language + '">' + escaped + '</code></pre>'
        return {'success': True, 'data': html, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
