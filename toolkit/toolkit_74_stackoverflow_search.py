"""toolkit_74_stackoverflow_search.py
Search Stack Overflow and retrieve Q&A content via the Stack Exchange API.
"""
import urllib.request
import urllib.parse
import json
import re

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

_API = 'https://api.stackexchange.com/2.3'

def _get(path, params=None):
    try:
        base_params = {'site':'stackoverflow'}
        if params:
            base_params.update(params)
        query = urllib.parse.urlencode(base_params)
        url = _API + path + '?' + query
        if HAS_REQUESTS:
            r = requests.get(url, timeout=15)
            return r.status_code, r.json()
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as e:
        return 0, {'error': str(e)}

def _strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text or '')

def search_questions(query: str, tagged: str = '', max_results: int = 5) -> dict:
    """Search Stack Overflow questions."""
    try:
        params = {'intitle': query, 'order': 'desc', 'sort': 'relevance', 'pagesize': max_results}
        if tagged:
            params['tagged'] = tagged
        status, data = _get('/search/advanced', params)
        if status == 200:
            items = [{'id': q['question_id'], 'title': _strip_html(q['title']), 'answered': q.get('is_answered', False), 'votes': q.get('score', 0), 'answers': q.get('answer_count', 0), 'tags': q.get('tags', []), 'url': q.get('link', '')} for q in data.get('items', [])]
            return {'success': True, 'data': items, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_question(question_id: int) -> dict:
    """Get a Stack Overflow question with body."""
    try:
        status, data = _get('/questions/' + str(question_id), {'filter': 'withbody'})
        if status == 200 and data.get('items'):
            q = data['items'][0]
            return {'success': True, 'data': {'id': q['question_id'], 'title': _strip_html(q['title']), 'body': _strip_html(q.get('body', ''))[:2000], 'votes': q.get('score', 0), 'answered': q.get('is_answered', False), 'tags': q.get('tags', []), 'url': q.get('link', '')}, 'error': None}
        return {'success': False, 'data': None, 'error': 'Question not found'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_answers(question_id: int, max_results: int = 3) -> dict:
    """Get answers for a Stack Overflow question."""
    try:
        status, data = _get('/questions/' + str(question_id) + '/answers', {'filter': 'withbody', 'sort': 'votes', 'pagesize': max_results})
        if status == 200:
            answers = [{'id': a['answer_id'], 'body': _strip_html(a.get('body', ''))[:2000], 'votes': a.get('score', 0), 'accepted': a.get('is_accepted', False)} for a in data.get('items', [])]
            return {'success': True, 'data': answers, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_accepted_answer(question_id: int) -> dict:
    """Get only the accepted answer for a question."""
    try:
        result = get_answers(question_id, max_results=10)
        if result['success']:
            accepted = [a for a in result['data'] if a['accepted']]
            if accepted:
                return {'success': True, 'data': accepted[0], 'error': None}
            return {'success': True, 'data': None, 'error': 'No accepted answer found'}
        return result
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_and_get_top_answer(query: str, tagged: str = '') -> dict:
    """One-shot: search SO and return top question with its best answer."""
    try:
        q_result = search_questions(query, tagged=tagged, max_results=3)
        if not q_result['success'] or not q_result['data']:
            return {'success': False, 'data': None, 'error': 'No questions found'}
        best = max(q_result['data'], key=lambda x: x['votes'])
        a_result = get_answers(best['id'], max_results=1)
        answer_body = a_result['data'][0]['body'] if a_result['success'] and a_result['data'] else 'No answers found'
        return {'success': True, 'data': {'question': best['title'], 'question_url': best['url'], 'answer': answer_body}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_popular_tags(max_results: int = 20) -> dict:
    """Get most popular Stack Overflow tags."""
    try:
        status, data = _get('/tags', {'order': 'desc', 'sort': 'popular', 'pagesize': max_results})
        if status == 200:
            tags = [{'name': t['name'], 'count': t.get('count', 0)} for t in data.get('items', [])]
            return {'success': True, 'data': tags, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_questions_by_tag(tag: str, max_results: int = 10) -> dict:
    """Get recent unanswered questions for a tag."""
    try:
        status, data = _get('/questions', {'tagged': tag, 'sort': 'votes', 'order': 'desc', 'pagesize': max_results})
        if status == 200:
            items = [{'id': q['question_id'], 'title': _strip_html(q['title']), 'votes': q.get('score', 0), 'answers': q.get('answer_count', 0), 'url': q.get('link', '')} for q in data.get('items', [])]
            return {'success': True, 'data': items, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_full_text(query: str, max_results: int = 5) -> dict:
    """Full-text search across questions and answers."""
    try:
        params = {'q': query, 'order': 'desc', 'sort': 'relevance', 'pagesize': max_results}
        status, data = _get('/search/excerpts', params)
        if status == 200:
            items = [{'type': i.get('item_type'), 'title': _strip_html(i.get('title', '')), 'excerpt': _strip_html(i.get('excerpt', ''))[:500], 'votes': i.get('score', 0), 'url': 'https://stackoverflow.com/' + i.get('item_type', 'q') + 's/' + str(i.get('question_id', ''))} for i in data.get('items', [])]
            return {'success': True, 'data': items, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_code_snippets(question_id: int) -> dict:
    """Extract code blocks from a question's top answer."""
    try:
        status, data = _get('/questions/' + str(question_id) + '/answers', {'filter': 'withbody', 'sort': 'votes', 'pagesize': 1})
        if status == 200 and data.get('items'):
            body = data['items'][0].get('body', '')
            snippets = re.findall(r'<code>(.*?)</code>', body, re.DOTALL)
            snippets = [_strip_html(s).strip() for s in snippets]
            return {'success': True, 'data': {'snippets': snippets, 'count': len(snippets)}, 'error': None}
        return {'success': False, 'data': None, 'error': 'No answer found'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_related_questions(question_id: int, max_results: int = 5) -> dict:
    """Get related questions for a given question ID."""
    try:
        status, data = _get('/questions/' + str(question_id) + '/related', {'pagesize': max_results, 'sort': 'votes', 'order': 'desc'})
        if status == 200:
            items = [{'id': q['question_id'], 'title': _strip_html(q['title']), 'votes': q.get('score', 0), 'url': q.get('link', '')} for q in data.get('items', [])]
            return {'success': True, 'data': items, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_api_quota() -> dict:
    """Check Stack Exchange API quota remaining."""
    try:
        status, data = _get('/questions', {'pagesize': 1})
        if status == 200:
            return {'success': True, 'data': {'quota_remaining': data.get('quota_remaining'), 'quota_max': data.get('quota_max')}, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_python_error(error_message: str) -> dict:
    """Search SO specifically for a Python error message."""
    return search_questions(error_message, tagged='python', max_results=5)

def search_javascript_error(error_message: str) -> dict:
    """Search SO specifically for a JavaScript error."""
    return search_questions(error_message, tagged='javascript', max_results=5)
