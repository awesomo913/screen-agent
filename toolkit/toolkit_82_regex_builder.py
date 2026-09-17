"""toolkit_82_regex_builder.py
Build, test, explain and generate regex patterns interactively.
"""
import re
import json

def test_regex(pattern: str, text: str, flags: list = []) -> dict:
    """Test a regex pattern against text and return all matches."""
    try:
        flag_map = {'i': re.IGNORECASE, 'm': re.MULTILINE, 's': re.DOTALL, 'x': re.VERBOSE}
        flag_val = 0
        for f in flags:
            flag_val |= flag_map.get(f.lower(), 0)
        compiled = re.compile(pattern, flag_val)
        matches = list(compiled.finditer(text))
        result = []
        for m in matches:
            result.append({'match': m.group(0), 'start': m.start(), 'end': m.end(), 'groups': list(m.groups()), 'groupdict': m.groupdict()})
        return {'success': True, 'data': {'matches': result, 'count': len(result), 'pattern': pattern}, 'error': None}
    except re.error as e:
        return {'success': False, 'data': None, 'error': 'Regex error: ' + str(e)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def regex_search(pattern: str, text: str, flags: list = []) -> dict:
    """Find first match of pattern in text."""
    try:
        flag_val = 0
        for f in flags:
            flag_val |= {'i': re.IGNORECASE, 'm': re.MULTILINE, 's': re.DOTALL}.get(f.lower(), 0)
        m = re.search(pattern, text, flag_val)
        if m:
            return {'success': True, 'data': {'match': m.group(0), 'start': m.start(), 'end': m.end(), 'groups': list(m.groups())}, 'error': None}
        return {'success': True, 'data': None, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def regex_replace(pattern: str, replacement: str, text: str, flags: list = [], count: int = 0) -> dict:
    """Replace regex matches in text."""
    try:
        flag_val = 0
        for f in flags:
            flag_val |= {'i': re.IGNORECASE, 'm': re.MULTILINE, 's': re.DOTALL}.get(f.lower(), 0)
        result = re.sub(pattern, replacement, text, count=count, flags=flag_val)
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def regex_split(pattern: str, text: str, maxsplit: int = 0) -> dict:
    """Split text on regex pattern."""
    try:
        parts = re.split(pattern, text, maxsplit)
        return {'success': True, 'data': parts, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def validate_regex(pattern: str) -> dict:
    """Check if a regex pattern is valid."""
    try:
        re.compile(pattern)
        return {'success': True, 'data': {'valid': True, 'pattern': pattern}, 'error': None}
    except re.error as e:
        return {'success': True, 'data': {'valid': False, 'error': str(e)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_common_patterns() -> dict:
    """Return library of common regex patterns."""
    try:
        patterns = {
            'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'url': r'https?://[^\s<>"{}|\\^\[\]`]+',
            'ipv4': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            'ipv6': r'(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}',
            'phone_us': r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
            'date_iso': r'\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])',
            'date_us': r'(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])/\d{2,4}',
            'time': r'(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?',
            'zip_us': r'\b\d{5}(?:-\d{4})?\b',
            'credit_card': r'\b(?:\d{4}[- ]?){3}\d{4}\b',
            'hex_color': r'#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b',
            'html_tag': r'<[^>]+>',
            'python_identifier': r'\b[a-zA-Z_][a-zA-Z0-9_]*\b',
            'semver': r'\bv?\d+\.\d+\.\d+(?:-[\w.]+)?(?:\+[\w.]+)?\b',
            'slug': r'^[a-z0-9]+(?:-[a-z0-9]+)*$',
            'uuid': r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            'md5': r'\b[0-9a-fA-F]{32}\b',
            'sha256': r'\b[0-9a-fA-F]{64}\b',
            'python_comment': r'#.*$',
            'python_string': r'(?:""".*?"""|' + "'''.*?'''" + r'|"[^"]*"|' + "'[^']*'" + r')',
        }
        return {'success': True, 'data': patterns, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_emails(text: str) -> dict:
    """Extract all email addresses from text."""
    try:
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(pattern, text)
        return {'success': True, 'data': list(set(emails)), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_urls(text: str) -> dict:
    """Extract all URLs from text."""
    try:
        pattern = r'https?://[^\s<>"{}|\\^\[\]`]+'
        urls = re.findall(pattern, text)
        return {'success': True, 'data': list(dict.fromkeys(urls)), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_ips(text: str) -> dict:
    """Extract all IP addresses from text."""
    try:
        pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        ips = re.findall(pattern, text)
        valid = [ip for ip in ips if all(0 <= int(n) <= 255 for n in ip.split('.'))]
        return {'success': True, 'data': list(set(valid)), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_dates(text: str) -> dict:
    """Extract date patterns from text."""
    try:
        patterns = {'iso': r'\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])', 'us': r'(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])/\d{2,4}', 'written': r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}'}
        results = {}
        for name, pattern in patterns.items():
            results[name] = re.findall(pattern, text)
        return {'success': True, 'data': results, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def build_pattern_from_examples(examples: list) -> dict:
    """Try to infer a regex pattern from example strings."""
    try:
        if not examples:
            return {'success': False, 'data': None, 'error': 'No examples provided'}
        def char_class(c):
            if c.isdigit(): return '\\d'
            if c.isalpha(): return '[a-zA-Z]'
            return re.escape(c)
        min_len = min(len(e) for e in examples)
        max_len = max(len(e) for e in examples)
        if min_len == max_len:
            pattern_parts = []
            for i in range(min_len):
                chars_at_pos = set(e[i] for e in examples)
                if len(chars_at_pos) == 1:
                    pattern_parts.append(re.escape(next(iter(chars_at_pos))))
                elif all(c.isdigit() for c in chars_at_pos):
                    pattern_parts.append('\\d')
                elif all(c.isalpha() for c in chars_at_pos):
                    pattern_parts.append('[a-zA-Z]')
                else:
                    escaped = [re.escape(c) for c in sorted(chars_at_pos)]
                    pattern_parts.append('[' + ''.join(escaped) + ']')
            pattern = '^' + ''.join(pattern_parts) + '$'
        else:
            pattern = '.{' + str(min_len) + ',' + str(max_len) + '}'
        valid_for_all = all(re.fullmatch(pattern, e) for e in examples)
        return {'success': True, 'data': {'pattern': pattern, 'valid_for_examples': valid_for_all, 'examples_tested': len(examples)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def explain_regex_token(token: str) -> dict:
    """Explain what a regex token/character class means."""
    try:
        explanations = {'\\d': 'Any digit 0-9', '\\D': 'Any non-digit', '\\w': 'Any word character (a-z, A-Z, 0-9, _)', '\\W': 'Any non-word character', '\\s': 'Any whitespace (space, tab, newline)', '\\S': 'Any non-whitespace', '\\b': 'Word boundary', '\\B': 'Non-word boundary', '.': 'Any character except newline', '^': 'Start of string/line', '$': 'End of string/line', '*': 'Zero or more of preceding', '+': 'One or more of preceding', '?': 'Zero or one of preceding (optional)', '|': 'Alternation (OR)', '(': 'Start capturing group', ')': 'End capturing group', '[': 'Start character class', ']': 'End character class', '{': 'Start quantifier', '}': 'End quantifier', '\\n': 'Newline', '\\t': 'Tab', '\\r': 'Carriage return', '(?:': 'Non-capturing group', '(?=': 'Positive lookahead', '(?!': 'Negative lookahead', '(?<=': 'Positive lookbehind', '(?<!': 'Negative lookbehind'}
        result = explanations.get(token, 'Unknown or literal character: ' + token)
        return {'success': True, 'data': {'token': token, 'explanation': result}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def highlight_matches(pattern: str, text: str, marker: str = '>>>') -> dict:
    """Return text with matches highlighted using a marker."""
    try:
        result = re.sub('(' + pattern + ')', marker + r'\1' + marker, text)
        count = len(re.findall(pattern, text))
        return {'success': True, 'data': {'highlighted': result, 'count': count}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def named_groups_extract(pattern: str, text: str) -> dict:
    """Extract named groups from all matches."""
    try:
        compiled = re.compile(pattern)
        results = [m.groupdict() for m in compiled.finditer(text)]
        return {'success': True, 'data': {'matches': results, 'count': len(results)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
