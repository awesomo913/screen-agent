"""toolkit_119_ast_transformer.py
Transform and rewrite Python AST — rename variables, add logging, instrument code.
"""
import ast
import sys
import re
import textwrap

class _RenameTransformer(ast.NodeTransformer):
    def __init__(self, old, new):
        self.old = old; self.new = new
    def visit_Name(self, node):
        if node.id == self.old: node.id = self.new
        return node
    def visit_FunctionDef(self, node):
        if node.name == self.old: node.name = self.new
        self.generic_visit(node); return node

class _AddLoggingTransformer(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        log_stmt = ast.parse('import logging; logging.debug("Entering " + node.name + "")').body
        node.body = log_stmt + node.body
        self.generic_visit(node); return node

def rename_identifier(code: str, old_name: str, new_name: str) -> dict:
    """Rename all occurrences of an identifier in Python code."""
    try:
        tree = ast.parse(code)
        new_tree = _RenameTransformer(old_name, new_name).visit(tree)
        ast.fix_missing_locations(new_tree)
        result = ast.unparse(new_tree)
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_all_names(code: str) -> dict:
    """Extract all Name nodes (variables, functions) from AST."""
    try:
        tree = ast.parse(code)
        names = sorted(set(n.id for n in ast.walk(tree) if isinstance(n, ast.Name)))
        return {"success": True, "data": names, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_ast_dump(code: str, indent: int = 2) -> dict:
    """Get the AST dump of Python code."""
    try:
        tree = ast.parse(code)
        dump = ast.dump(tree, indent=indent)
        return {"success": True, "data": dump, "error": None}
    except SyntaxError as e:
        return {"success": False, "data": None, "error": "SyntaxError: " + str(e)}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_node_types(code: str) -> dict:
    """Count each AST node type in Python code."""
    try:
        from collections import Counter
        tree = ast.parse(code)
        counts = Counter(type(n).__name__ for n in ast.walk(tree))
        return {"success": True, "data": dict(counts.most_common()), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_all_constants(code: str) -> dict:
    """Find all literal constants in Python code."""
    try:
        tree = ast.parse(code)
        constants = [{"value": n.value, "type": type(n.value).__name__, "line": n.lineno} for n in ast.walk(tree) if isinstance(n, ast.Constant)]
        return {"success": True, "data": constants, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_string_constants(code: str) -> dict:
    """Find all string literals in Python code."""
    try:
        tree = ast.parse(code)
        strings = [{"value": n.value, "line": n.lineno} for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        return {"success": True, "data": strings, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def ast_to_code(code: str) -> dict:
    """Round-trip: parse AST and unparse back to code."""
    try:
        tree = ast.parse(code)
        unparsed = ast.unparse(tree)
        return {"success": True, "data": unparsed, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_comparisons(code: str) -> dict:
    """Find all comparison operations in Python code."""
    try:
        tree = ast.parse(code)
        ops_map = {"Eq": "==", "NotEq": "!=", "Lt": "<", "LtE": "<=", "Gt": ">", "GtE": ">=", "Is": "is", "IsNot": "is not", "In": "in", "NotIn": "not in"}
        comps = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                op_names = [ops_map.get(type(op).__name__, "?") for op in node.ops]
                comps.append({"line": node.lineno, "ops": op_names, "code": ast.unparse(node)})
        return {"success": True, "data": comps, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_function_calls(code: str) -> dict:
    """Find all function call expressions."""
    try:
        tree = ast.parse(code)
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = ast.unparse(node.func)
                else:
                    name = "?"
                calls.append({"name": name, "line": node.lineno, "args": len(node.args)})
        return {"success": True, "data": calls, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def replace_string_constant(code: str, old_value: str, new_value: str) -> dict:
    """Replace all occurrences of a string constant in AST."""
    try:
        class _StrReplacer(ast.NodeTransformer):
            def visit_Constant(self, node):
                if isinstance(node.value, str) and node.value == old_value:
                    return ast.Constant(value=new_value)
                return node
        tree = ast.parse(code)
        new_tree = _StrReplacer().visit(tree)
        ast.fix_missing_locations(new_tree)
        return {"success": True, "data": ast.unparse(new_tree), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_function_signatures(code: str) -> dict:
    """Extract function signatures with type annotations."""
    try:
        tree = ast.parse(code)
        sigs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = []
                for arg in node.args.args:
                    ann = ast.unparse(arg.annotation) if arg.annotation else ""
                    args.append({"name": arg.arg, "annotation": ann})
                ret = ast.unparse(node.returns) if node.returns else ""
                sigs.append({"name": node.name, "args": args, "returns": ret, "line": node.lineno, "async": isinstance(node, ast.AsyncFunctionDef)})
        return {"success": True, "data": sigs, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_global_assignments(code: str) -> dict:
    """Find module-level assignments."""
    try:
        tree = ast.parse(code)
        assigns = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assigns.append({"name": target.id, "line": node.lineno, "value": ast.unparse(node.value)[:50]})
        return {"success": True, "data": assigns, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}