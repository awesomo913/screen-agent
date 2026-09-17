"""toolkit_85_algorithm_tools.py
Common algorithm implementations and helpers for coding challenges.
"""
import heapq
import math
from collections import defaultdict, deque
from typing import Any

def binary_search(arr: list, target: float) -> dict:
    """Binary search in sorted list."""
    try:
        lo, hi = 0, len(arr) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if arr[mid] == target:
                return {'success': True, 'data': {'found': True, 'index': mid}, 'error': None}
            elif arr[mid] < target:
                lo = mid + 1
            else:
                hi = mid - 1
        return {'success': True, 'data': {'found': False, 'index': -1}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def bubble_sort(arr: list) -> dict:
    """Sort list using bubble sort."""
    try:
        a = list(arr)
        n = len(a)
        for i in range(n):
            for j in range(0, n-i-1):
                if a[j] > a[j+1]:
                    a[j], a[j+1] = a[j+1], a[j]
        return {'success': True, 'data': a, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def merge_sort(arr: list) -> dict:
    """Sort list using merge sort."""
    try:
        def _merge_sort(a):
            if len(a) <= 1:
                return a
            mid = len(a) // 2
            left = _merge_sort(a[:mid])
            right = _merge_sort(a[mid:])
            result = []
            i = j = 0
            while i < len(left) and j < len(right):
                if left[i] <= right[j]:
                    result.append(left[i]); i += 1
                else:
                    result.append(right[j]); j += 1
            return result + left[i:] + right[j:]
        return {'success': True, 'data': _merge_sort(list(arr)), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def quicksort(arr: list) -> dict:
    """Sort list using quicksort."""
    try:
        def _qs(a):
            if len(a) <= 1:
                return a
            pivot = a[len(a)//2]
            left = [x for x in a if x < pivot]
            mid = [x for x in a if x == pivot]
            right = [x for x in a if x > pivot]
            return _qs(left) + mid + _qs(right)
        return {'success': True, 'data': _qs(list(arr)), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def bfs(graph: dict, start: str) -> dict:
    """Breadth-first search on a graph (adjacency dict)."""
    try:
        visited = []
        queue = deque([start])
        seen = {start}
        while queue:
            node = queue.popleft()
            visited.append(node)
            for neighbor in graph.get(str(node), []):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        return {'success': True, 'data': {'order': visited, 'nodes_visited': len(visited)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def dfs(graph: dict, start: str) -> dict:
    """Depth-first search on a graph."""
    try:
        visited = []
        seen = set()
        def _dfs(node):
            if node in seen:
                return
            seen.add(node)
            visited.append(node)
            for neighbor in graph.get(str(node), []):
                _dfs(neighbor)
        _dfs(start)
        return {'success': True, 'data': {'order': visited, 'nodes_visited': len(visited)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def dijkstra(graph: dict, start: str) -> dict:
    """Dijkstra shortest path. graph: {node: {neighbor: weight}}."""
    try:
        dist = {node: float('inf') for node in graph}
        dist[start] = 0
        heap = [(0, start)]
        prev = {}
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            for v, w in graph.get(u, {}).items():
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd, v))
        return {'success': True, 'data': {'distances': dist, 'previous': prev}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fibonacci(n: int) -> dict:
    """Return first n Fibonacci numbers."""
    try:
        if n <= 0:
            return {'success': True, 'data': [], 'error': None}
        fibs = [0, 1]
        while len(fibs) < n:
            fibs.append(fibs[-1] + fibs[-2])
        return {'success': True, 'data': fibs[:n], 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def is_prime(n: int) -> dict:
    """Check if n is a prime number."""
    try:
        if n < 2:
            return {'success': True, 'data': False, 'error': None}
        if n < 4:
            return {'success': True, 'data': True, 'error': None}
        if n % 2 == 0 or n % 3 == 0:
            return {'success': True, 'data': False, 'error': None}
        i = 5
        while i * i <= n:
            if n % i == 0 or n % (i+2) == 0:
                return {'success': True, 'data': False, 'error': None}
            i += 6
        return {'success': True, 'data': True, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def primes_up_to(n: int) -> dict:
    """Sieve of Eratosthenes — list all primes up to n."""
    try:
        sieve = [True] * (n + 1)
        sieve[0] = sieve[1] = False
        for i in range(2, int(n**0.5)+1):
            if sieve[i]:
                for j in range(i*i, n+1, i):
                    sieve[j] = False
        primes = [i for i, v in enumerate(sieve) if v]
        return {'success': True, 'data': {'primes': primes, 'count': len(primes)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def gcd(a: int, b: int) -> dict:
    """Greatest common divisor."""
    try:
        result = math.gcd(a, b)
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def lcm(a: int, b: int) -> dict:
    """Least common multiple."""
    try:
        result = abs(a * b) // math.gcd(a, b) if a and b else 0
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def levenshtein_distance(s1: str, s2: str) -> dict:
    """Compute Levenshtein edit distance between two strings."""
    try:
        m, n = len(s1), len(s2)
        dp = list(range(n + 1))
        for i in range(1, m + 1):
            prev = dp[:]
            dp[0] = i
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[j] = prev[j-1]
                else:
                    dp[j] = 1 + min(prev[j], dp[j-1], prev[j-1])
        return {'success': True, 'data': dp[n], 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def anagram_check(s1: str, s2: str) -> dict:
    """Check if two strings are anagrams."""
    try:
        from collections import Counter
        result = Counter(s1.lower().replace(' ','')) == Counter(s2.lower().replace(' ',''))
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def two_sum(numbers: list, target: float) -> dict:
    """Find two indices that sum to target (LeetCode style)."""
    try:
        seen = {}
        for i, num in enumerate(numbers):
            complement = target - num
            if complement in seen:
                return {'success': True, 'data': {'indices': [seen[complement], i], 'values': [complement, num]}, 'error': None}
            seen[num] = i
        return {'success': True, 'data': None, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def longest_common_subsequence(s1: str, s2: str) -> dict:
    """Find longest common subsequence of two strings."""
    try:
        m, n = len(s1), len(s2)
        dp = [[0]*(n+1) for _ in range(m+1)]
        for i in range(1, m+1):
            for j in range(1, n+1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        i, j = m, n
        lcs = []
        while i > 0 and j > 0:
            if s1[i-1] == s2[j-1]:
                lcs.append(s1[i-1]); i -= 1; j -= 1
            elif dp[i-1][j] > dp[i][j-1]:
                i -= 1
            else:
                j -= 1
        return {'success': True, 'data': {'lcs': ''.join(reversed(lcs)), 'length': dp[m][n]}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
