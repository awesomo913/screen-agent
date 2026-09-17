"""toolkit_81_unit_test_generator.py
Auto-generate unit tests for Python functions.
"""
import ast
import re
import json
import os
import subprocess
import sys
import tempfile

def _get_func_info(code: str):
    try:
        tree = ast.parse(code)
        funcs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args if a.arg != 'self']
                ret = ''
                if node.returns:
                    try:
                        ret = ast.unparse(node.returns)
                    except:
                        pass
                funcs.append({'name': node.name, 'args': args, 'returns': ret, 'line': node.lineno})
        return funcs
    except:
        return []

def generate_unittest_class(module_name: str, functions: list) -> dict:
    """Generate a unittest.TestCase class for a list of function names."""
    try:
        lines = ['import unittest']
        lines.append('import ' + module_name)
        lines.append('')
        lines.append('class Test' + module_name.title().replace('_','') + '(unittest.TestCase):')
        for func in functions:
            if isinstance(func, dict):
                fname = func.get('name','')
                args = func.get('args',[])
            else:
                fname = str(func)
                args = []
            test_name = 'test_' + fname
            arg_defaults = ', '.join(['None'] * len(args))
            lines.append('')
            lines.append('    def ' + test_name + '(self):')
            lines.append('        # TODO: set up inputs')
            if arg_defaults:
                lines.append('        result = ' + module_name + '.' + fname + '(' + arg_defaults + ')')
            else:
                lines.append('        result = ' + module_name + '.' + fname + '()')
            lines.append('        self.assertIsNotNone(result)')
        lines.append('')
        lines.append("if __name__ == '__main__':")
        lines.append('    unittest.main()')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_tests_from_code(code: str, module_name: str = 'module') -> dict:
    """Parse Python code and auto-generate unit tests."""
    try:
        funcs = _get_func_info(code)
        if not funcs:
            return {'success': False, 'data': None, 'error': 'No functions found in code'}
        return generate_unittest_class(module_name, funcs)
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_pytest_tests(code: str, module_name: str = 'module') -> dict:
    """Generate pytest-style test functions."""
    try:
        funcs = _get_func_info(code)
        lines = ['import pytest', 'import ' + module_name, '']
        for func in funcs:
            fname = func['name']
            args = func['args']
            arg_defaults = ', '.join(['None'] * len(args))
            lines.append('def test_' + fname + '():')
            lines.append('    # TODO: set up inputs')
            if arg_defaults:
                lines.append('    result = ' + module_name + '.' + fname + '(' + arg_defaults + ')')
            else:
                lines.append('    result = ' + module_name + '.' + fname + '()')
            lines.append('    assert result is not None')
            lines.append('')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_test_cases_for_function(func_name: str, test_inputs: list, expected_outputs: list) -> dict:
    """Generate parameterized test cases given inputs and expected outputs."""
    try:
        if len(test_inputs) != len(expected_outputs):
            return {'success': False, 'data': None, 'error': 'inputs and outputs must have same length'}
        lines = ['import pytest', '', '@pytest.mark.parametrize("inputs, expected", [']
        for inp, exp in zip(test_inputs, expected_outputs):
            lines.append('    (' + repr(inp) + ', ' + repr(exp) + '),')
        lines.append('])')
        lines.append('def test_' + func_name + '(inputs, expected):')
        lines.append('    result = ' + func_name + '(*inputs) if isinstance(inputs, (list,tuple)) else ' + func_name + '(inputs)')
        lines.append('    assert result == expected')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_mock_test(func_name: str, mock_targets: list) -> dict:
    """Generate a test with unittest.mock patches."""
    try:
        lines = ['from unittest.mock import patch, MagicMock', 'import unittest', '']
        lines.append('class Test' + func_name.title() + '(unittest.TestCase):')
        lines.append('')
        for target in mock_targets:
            deco = '    @patch("' + target + '")'
            lines.append(deco)
        params = ['mock_' + t.split('.')[-1] for t in reversed(mock_targets)]
        params_str = ', '.join(['self'] + params)
        lines.append('    def test_' + func_name + '(' + params_str + '):')
        for p in params:
            lines.append('        ' + p + '.return_value = MagicMock()')
        lines.append('        # TODO: call ' + func_name + ' and assert results')
        lines.append('        pass')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_tests_inline(test_code: str, code_under_test: str = '') -> dict:
    """Run generated test code and return results."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            if code_under_test:
                with open(os.path.join(tmpdir, 'module.py'), 'w') as f:
                    f.write(code_under_test)
            with open(os.path.join(tmpdir, 'test_module.py'), 'w') as f:
                f.write(test_code)
            result = subprocess.run([sys.executable, '-m', 'pytest', 'test_module.py', '-v', '--tb=short'], capture_output=True, text=True, cwd=tmpdir, timeout=30)
            lines = result.stdout.splitlines()
            passed = sum(1 for l in lines if 'PASSED' in l)
            failed = sum(1 for l in lines if 'FAILED' in l)
            errors = sum(1 for l in lines if 'ERROR' in l)
            return {'success': result.returncode in (0,1), 'data': {'passed': passed, 'failed': failed, 'errors': errors, 'output': result.stdout[-2000:], 'return_code': result.returncode}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_fixture_code(fixtures: list) -> dict:
    """Generate pytest fixture functions."""
    try:
        lines = ['import pytest', '']
        for fix in fixtures:
            if isinstance(fix, dict):
                name = fix.get('name','fixture')
                value = fix.get('value','None')
                scope = fix.get('scope','function')
            else:
                name, value, scope = str(fix), 'None', 'function'
            lines.append('@pytest.fixture(scope="' + scope + '")')
            lines.append('def ' + name + '():')
            lines.append('    return ' + repr(value) if not isinstance(value, str) else '    return ' + value)
            lines.append('')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def check_test_coverage(code_path: str, test_path: str) -> dict:
    """Run pytest with coverage report."""
    try:
        result = subprocess.run([sys.executable, '-m', 'pytest', test_path, '--cov=' + code_path, '--cov-report=term-missing', '-q'], capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr
        coverage_match = re.search(r'TOTAL.*?(\d+)%', output)
        pct = int(coverage_match.group(1)) if coverage_match else None
        return {'success': True, 'data': {'coverage_pct': pct, 'output': output[-2000:], 'return_code': result.returncode}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_property_based_test(func_name: str, strategy_hints: dict) -> dict:
    """Generate a hypothesis property-based test."""
    try:
        type_strategies = {'int': 'st.integers()', 'str': 'st.text()', 'float': 'st.floats(allow_nan=False)', 'bool': 'st.booleans()', 'list': 'st.lists(st.integers())', 'dict': 'st.dictionaries(st.text(), st.integers())'}
        lines = ['from hypothesis import given, settings', 'from hypothesis import strategies as st', '']
        strats = [type_strategies.get(v, 'st.text()') for k, v in strategy_hints.items()]
        strat_str = ', '.join(strats)
        param_str = ', '.join(strategy_hints.keys())
        lines.append('@given(' + strat_str + ')')
        lines.append('@settings(max_examples=100)')
        lines.append('def test_' + func_name + '_property(' + param_str + '):')
        lines.append('    result = ' + func_name + '(' + param_str + ')')
        lines.append('    # TODO: assert invariant properties about result')
        lines.append('    assert result is not None')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
