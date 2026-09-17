"""toolkit_86_leetcode_helper.py
Helpers for solving and submitting LeetCode-style problems.
"""
import json
import urllib.request
import urllib.parse
import re
import sys
import tempfile
import os
import subprocess
import time

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def _get(url, headers=None):
    try:
        h = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        if headers:
            h.update(headers)
        if HAS_REQUESTS:
            r = requests.get(url, headers=h, timeout=15)
            return r.status_code, r.json() if 'json' in r.headers.get('Content-Type','') else r.text
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=15) as resp:
            ct = resp.headers.get('Content-Type','')
            body = resp.read().decode('utf-8', errors='replace')
            return resp.status, json.loads(body) if 'json' in ct else body
    except Exception as e:
        return 0, str(e)

def search_problems_on_leetcode(query: str, difficulty: str = '') -> dict:
    """Search LeetCode problems via unofficial API."""
    try:
        url = 'https://leetcode.com/api/problems/all/'
        status, data = _get(url)
        if status == 200 and isinstance(data, dict):
            problems = data.get('stat_status_pairs', [])
            results = []
            for p in problems:
                stat = p.get('stat', {})
                title = stat.get('question__title', '')
                slug = stat.get('question__title_slug', '')
                diff_num = p.get('difficulty', {}).get('level', 0)
                diff_map = {1: 'Easy', 2: 'Medium', 3: 'Hard'}
                diff = diff_map.get(diff_num, '')
                if query.lower() in title.lower():
                    if not difficulty or diff.lower() == difficulty.lower():
                        results.append({'title': title, 'slug': slug, 'difficulty': diff, 'url': 'https://leetcode.com/problems/' + slug + '/'})
            return {'success': True, 'data': results[:20], 'error': None}
        return {'success': False, 'data': None, 'error': 'Could not fetch problem list'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_problem_description(slug: str) -> dict:
    """Get LeetCode problem title and stats."""
    try:
        url = 'https://leetcode.com/api/problems/all/'
        status, data = _get(url)
        if status == 200 and isinstance(data, dict):
            for p in data.get('stat_status_pairs', []):
                stat = p.get('stat', {})
                if stat.get('question__title_slug', '') == slug:
                    diff_map = {1: 'Easy', 2: 'Medium', 3: 'Hard'}
                    return {'success': True, 'data': {'title': stat.get('question__title'), 'slug': slug, 'difficulty': diff_map.get(p.get('difficulty',{}).get('level',0),''), 'total_acs': stat.get('total_acs',0), 'total_submitted': stat.get('total_submitted',0), 'url': 'https://leetcode.com/problems/' + slug + '/'}, 'error': None}
        return {'success': False, 'data': None, 'error': 'Problem not found'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_solution_tests(solution_code: str, test_cases: list, entry_func: str = 'solution') -> dict:
    """Run a solution function against test cases locally."""
    try:
        results = []
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False, encoding='utf-8') as f:
            f.write(solution_code)
            f.write('\n\nimport json, sys\n')
            f.write('test_cases = ' + repr(test_cases) + '\n')
            f.write('results = []\n')
            f.write('for tc in test_cases:\n')
            f.write('    try:\n')
            f.write('        if isinstance(tc.get("input"), list):\n')
            f.write('            out = ' + entry_func + '(*tc["input"])\n')
            f.write('        else:\n')
            f.write('            out = ' + entry_func + '(tc["input"])\n')
            f.write('        passed = out == tc.get("expected")\n')
            f.write('        results.append({"input": tc["input"], "expected": tc.get("expected"), "got": out, "passed": passed})\n')
            f.write('    except Exception as e:\n')
            f.write('        results.append({"input": tc.get("input"), "error": str(e), "passed": False})\n')
            f.write('print(json.dumps(results))\n')
            fname = f.name
        result = subprocess.run([sys.executable, fname], capture_output=True, text=True, timeout=15)
        os.unlink(fname)
        if result.returncode == 0:
            test_results = json.loads(result.stdout.strip())
            passed = sum(1 for r in test_results if r.get('passed'))
            return {'success': True, 'data': {'results': test_results, 'passed': passed, 'total': len(test_results)}, 'error': None}
        return {'success': False, 'data': None, 'error': result.stderr}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_solution_template(problem_type: str = 'array') -> dict:
    """Generate a starter solution template for common problem types."""
    try:
        templates = {
            'array': 'def solution(nums: list) -> int:\n    """TODO: solve the array problem."""\n    result = 0\n    for i, num in enumerate(nums):\n        pass  # TODO\n    return result\n',
            'string': 'def solution(s: str) -> str:\n    """TODO: solve the string problem."""\n    result = []\n    for char in s:\n        pass  # TODO\n    return \'\'.join(result)\n',
            'tree': 'class TreeNode:\n    def __init__(self, val=0, left=None, right=None):\n        self.val = val\n        self.left = left\n        self.right = right\n\ndef solution(root) -> int:\n    """TODO: solve the tree problem."""\n    if not root:\n        return 0\n    # TODO: traverse tree\n    return solution(root.left) + solution(root.right)\n',
            'graph': 'from collections import defaultdict, deque\n\ndef solution(n: int, edges: list) -> int:\n    """TODO: solve the graph problem."""\n    graph = defaultdict(list)\n    for u, v in edges:\n        graph[u].append(v)\n        graph[v].append(u)\n    visited = set()\n    def bfs(start):\n        queue = deque([start])\n        visited.add(start)\n        while queue:\n            node = queue.popleft()\n            for neighbor in graph[node]:\n                if neighbor not in visited:\n                    visited.add(neighbor)\n                    queue.append(neighbor)\n    for i in range(n):\n        if i not in visited:\n            bfs(i)\n    return 0\n',
            'dp': 'def solution(nums: list) -> int:\n    """TODO: dynamic programming solution."""\n    n = len(nums)\n    dp = [0] * (n + 1)\n    dp[0] = 0  # base case\n    for i in range(1, n + 1):\n        dp[i] = dp[i-1]  # TODO: fill transition\n    return dp[n]\n',
            'two_pointers': 'def solution(nums: list) -> int:\n    """TODO: two pointers approach."""\n    left, right = 0, len(nums) - 1\n    result = 0\n    while left < right:\n        # TODO: move pointers\n        left += 1\n        right -= 1\n    return result\n',
            'sliding_window': 'def solution(s: str, k: int) -> int:\n    """TODO: sliding window solution."""\n    window = {}\n    left = 0\n    result = 0\n    for right, char in enumerate(s):\n        window[char] = window.get(char, 0) + 1\n        while len(window) > k:\n            left_char = s[left]\n            window[left_char] -= 1\n            if window[left_char] == 0:\n                del window[left_char]\n            left += 1\n        result = max(result, right - left + 1)\n    return result\n'
        }
        template = templates.get(problem_type, templates['array'])
        return {'success': True, 'data': template, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def time_solution(solution_code: str, inputs: list, entry_func: str = 'solution', runs: int = 100) -> dict:
    """Benchmark a solution function with given inputs."""
    try:
        namespace = {}
        exec(solution_code, namespace)
        func = namespace.get(entry_func)
        if not func:
            return {'success': False, 'data': None, 'error': 'Function ' + entry_func + ' not found'}
        start = time.perf_counter()
        for _ in range(runs):
            result = func(*inputs) if isinstance(inputs, list) else func(inputs)
        elapsed = time.perf_counter() - start
        return {'success': True, 'data': {'avg_ms': round(elapsed/runs*1000, 4), 'total_ms': round(elapsed*1000, 3), 'runs': runs, 'last_result': str(result)[:200]}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def explain_big_o(code: str) -> dict:
    """Heuristic Big-O estimation based on loop nesting."""
    try:
        import ast
        tree = ast.parse(code)
        max_depth = 0
        def _count_loops(node, depth=0):
            nonlocal max_depth
            if isinstance(node, (ast.For, ast.While)):
                depth += 1
                max_depth = max(max_depth, depth)
            for child in ast.iter_child_nodes(node):
                _count_loops(child, depth)
        _count_loops(tree)
        complexity_map = {0: 'O(1)', 1: 'O(n)', 2: 'O(n^2)', 3: 'O(n^3)', 4: 'O(n^4)'}
        complexity = complexity_map.get(max_depth, 'O(n^' + str(max_depth) + ')')
        return {'success': True, 'data': {'estimated_complexity': complexity, 'max_loop_depth': max_depth, 'note': 'Heuristic estimate only — actual complexity may differ'}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_common_patterns() -> dict:
    """Return a reference of common coding interview patterns."""
    try:
        patterns = {'Sliding Window': 'Subarrays/substrings with constraint — move two pointers', 'Two Pointers': 'Sorted array pair problems — left/right pointers', 'Fast & Slow Pointers': 'Cycle detection in linked lists', 'Merge Intervals': 'Overlapping intervals — sort then merge', 'Cyclic Sort': 'Numbers in range [1,n] — place in correct index', 'In-place Reversal': 'Reverse linked list in-place', 'BFS': 'Level-order traversal, shortest path in unweighted graph', 'DFS': 'Tree/graph traversal, path finding, backtracking', 'Two Heaps': 'Median finding — max-heap + min-heap', 'Subsets': 'Generate all combinations/permutations', 'Binary Search': 'Sorted array search — O(log n)', 'Top-K Elements': 'Heap-based selection of K largest/smallest', 'K-Way Merge': 'Merge K sorted lists with a heap', 'Knapsack DP': 'Subset selection with weight constraint', 'Trie': 'Prefix matching, autocomplete', 'Topological Sort': 'Task scheduling, dependency ordering'}
        return {'success': True, 'data': patterns, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
