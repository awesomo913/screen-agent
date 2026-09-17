"""toolkit_75_code_snippet_manager.py
Manage a local library of code snippets — save, search, tag, retrieve.
"""
import json
import os
import re
import hashlib
import datetime
from pathlib import Path

_DEFAULT_DB = os.path.join(os.path.expanduser('~'), '.screen_agent', 'snippets.json')

def _load_db(db_path: str = '') -> dict:
    path = db_path or _DEFAULT_DB
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {'snippets': {}}

def _save_db(db: dict, db_path: str = '') -> None:
    path = db_path or _DEFAULT_DB
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2)

def _snippet_id(title: str) -> str:
    return hashlib.md5(title.encode()).hexdigest()[:8]

def save_snippet(title: str, code: str, language: str = '', tags: list = [], description: str = '', db_path: str = '') -> dict:
    """Save a code snippet to the local library."""
    try:
        db = _load_db(db_path)
        sid = _snippet_id(title)
        db['snippets'][sid] = {'id': sid, 'title': title, 'code': code, 'language': language, 'tags': tags, 'description': description, 'created': datetime.datetime.now().isoformat(), 'updated': datetime.datetime.now().isoformat()}
        _save_db(db, db_path)
        return {'success': True, 'data': {'id': sid, 'title': title}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_snippet(snippet_id: str, db_path: str = '') -> dict:
    """Get a snippet by ID."""
    try:
        db = _load_db(db_path)
        snip = db['snippets'].get(snippet_id)
        if snip:
            return {'success': True, 'data': snip, 'error': None}
        return {'success': False, 'data': None, 'error': 'Snippet not found: ' + snippet_id}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_snippet_by_title(title: str, db_path: str = '') -> dict:
    """Get a snippet by exact title."""
    try:
        db = _load_db(db_path)
        for snip in db['snippets'].values():
            if snip['title'].lower() == title.lower():
                return {'success': True, 'data': snip, 'error': None}
        return {'success': False, 'data': None, 'error': 'Snippet not found: ' + title}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_snippets(language: str = '', db_path: str = '') -> dict:
    """List all snippets, optionally filtered by language."""
    try:
        db = _load_db(db_path)
        snippets = list(db['snippets'].values())
        if language:
            snippets = [s for s in snippets if s.get('language','').lower() == language.lower()]
        return {'success': True, 'data': [{'id': s['id'], 'title': s['title'], 'language': s.get('language',''), 'tags': s.get('tags',[])} for s in snippets], 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_snippets(query: str, db_path: str = '') -> dict:
    """Search snippets by title, description, tags, or code content."""
    try:
        db = _load_db(db_path)
        q = query.lower()
        results = []
        for snip in db['snippets'].values():
            score = 0
            if q in snip['title'].lower():
                score += 3
            if q in snip.get('description','').lower():
                score += 2
            if any(q in t.lower() for t in snip.get('tags',[])):
                score += 2
            if q in snip['code'].lower():
                score += 1
            if score > 0:
                results.append({'id': snip['id'], 'title': snip['title'], 'language': snip.get('language',''), 'score': score})
        results.sort(key=lambda x: x['score'], reverse=True)
        return {'success': True, 'data': results, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_by_tag(tag: str, db_path: str = '') -> dict:
    """Find all snippets with a given tag."""
    try:
        db = _load_db(db_path)
        results = [s for s in db['snippets'].values() if tag.lower() in [t.lower() for t in s.get('tags',[])]]
        return {'success': True, 'data': [{'id': s['id'], 'title': s['title'], 'language': s.get('language','')} for s in results], 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def update_snippet(snippet_id: str, title: str = '', code: str = '', language: str = '', tags: list = [], description: str = '', db_path: str = '') -> dict:
    """Update fields of an existing snippet."""
    try:
        db = _load_db(db_path)
        if snippet_id not in db['snippets']:
            return {'success': False, 'data': None, 'error': 'Snippet not found'}
        snip = db['snippets'][snippet_id]
        if title:
            snip['title'] = title
        if code:
            snip['code'] = code
        if language:
            snip['language'] = language
        if tags:
            snip['tags'] = tags
        if description:
            snip['description'] = description
        snip['updated'] = datetime.datetime.now().isoformat()
        _save_db(db, db_path)
        return {'success': True, 'data': snip, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def delete_snippet(snippet_id: str, db_path: str = '') -> dict:
    """Delete a snippet by ID."""
    try:
        db = _load_db(db_path)
        if snippet_id not in db['snippets']:
            return {'success': False, 'data': None, 'error': 'Snippet not found'}
        title = db['snippets'][snippet_id]['title']
        del db['snippets'][snippet_id]
        _save_db(db, db_path)
        return {'success': True, 'data': {'deleted': title}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def export_snippets(output_path: str, db_path: str = '') -> dict:
    """Export all snippets to a JSON file."""
    try:
        db = _load_db(db_path)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2)
        return {'success': True, 'data': {'exported': len(db['snippets']), 'path': output_path}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def import_snippets(input_path: str, db_path: str = '') -> dict:
    """Import snippets from a JSON file."""
    try:
        db = _load_db(db_path)
        with open(input_path, encoding='utf-8') as f:
            imported = json.load(f)
        count = 0
        for sid, snip in imported.get('snippets', {}).items():
            db['snippets'][sid] = snip
            count += 1
        _save_db(db, db_path)
        return {'success': True, 'data': {'imported': count}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def export_snippet_as_file(snippet_id: str, output_dir: str = '.', db_path: str = '') -> dict:
    """Export a single snippet to its own source file."""
    try:
        db = _load_db(db_path)
        snip = db['snippets'].get(snippet_id)
        if not snip:
            return {'success': False, 'data': None, 'error': 'Snippet not found'}
        ext_map = {'python': '.py', 'javascript': '.js', 'java': '.java', 'cpp': '.cpp', 'c': '.c', 'ruby': '.rb', 'go': '.go', 'rust': '.rs', 'php': '.php', 'bash': '.sh', 'typescript': '.ts', 'html': '.html', 'css': '.css'}
        ext = ext_map.get(snip.get('language','').lower(), '.txt')
        filename = re.sub(r'[^\w\s-]', '', snip['title']).strip().replace(' ', '_') + ext
        path = os.path.join(output_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(snip['code'])
        return {'success': True, 'data': {'path': path}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_db_stats(db_path: str = '') -> dict:
    """Get statistics about the snippet library."""
    try:
        db = _load_db(db_path)
        snippets = list(db['snippets'].values())
        from collections import Counter
        langs = Counter(s.get('language','unknown') for s in snippets)
        tags = Counter(t for s in snippets for t in s.get('tags',[]))
        return {'success': True, 'data': {'total': len(snippets), 'languages': dict(langs.most_common(10)), 'top_tags': dict(tags.most_common(10)), 'db_path': db_path or _DEFAULT_DB}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def add_tag_to_snippet(snippet_id: str, tag: str, db_path: str = '') -> dict:
    """Add a tag to an existing snippet."""
    try:
        db = _load_db(db_path)
        if snippet_id not in db['snippets']:
            return {'success': False, 'data': None, 'error': 'Snippet not found'}
        tags = db['snippets'][snippet_id].get('tags', [])
        if tag not in tags:
            tags.append(tag)
        db['snippets'][snippet_id]['tags'] = tags
        _save_db(db, db_path)
        return {'success': True, 'data': {'tags': tags}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_recent_snippets(limit: int = 10, db_path: str = '') -> dict:
    """Get most recently updated snippets."""
    try:
        db = _load_db(db_path)
        snippets = sorted(db['snippets'].values(), key=lambda s: s.get('updated',''), reverse=True)[:limit]
        return {'success': True, 'data': [{'id': s['id'], 'title': s['title'], 'language': s.get('language',''), 'updated': s.get('updated','')} for s in snippets], 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
