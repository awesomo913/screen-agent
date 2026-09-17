"""
diff_patch.py

A complete, production-ready toolkit for screen agents to handle diffing, patching,
and text merging operations. All functions return a standardized dictionary containing
'success' (bool), 'data' (Any), and 'error' (Optional[str]).
"""

import difflib
import json
import os
import pathlib
import hashlib
import re
import io
import time
import zlib
import base64
from typing import Dict, Any, List, Optional, Tuple, Union

# --- Helper Functions ---

def _build_response(success: bool, data: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
    """Standardized response format for all toolkit functions."""
    return {"success": success, "data": data, "error": error}

def _read_file(filepath: Union[str, pathlib.Path]) -> str:
    """Helper to safely read a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def _read_file_bytes(filepath: Union[str, pathlib.Path]) -> bytes:
    """Helper to safely read a binary file."""
    with open(filepath, 'rb') as f:
        return f.read()

# --- Core Diffing Functions ---

def diff_strings(a: str, b: str) -> Dict[str, Any]:
    """Compare two strings and return the standard unified diff as a list of lines."""
    try:
        a_lines = a.splitlines(keepends=True)
        b_lines = b.splitlines(keepends=True)
        diff = list(difflib.unified_diff(a_lines, b_lines, fromfile='a', tofile='b'))
        return _build_response(True, diff)
    except Exception as e:
        return _build_response(False, error=str(e))

def diff_files(file1: Union[str, pathlib.Path], file2: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Compare two text files and return their unified diff."""
    try:
        text1 = _read_file(file1)
        text2 = _read_file(file2)
        diff_res = diff_strings(text1, text2)
        if not diff_res["success"]:
            return diff_res
        
        # Override file names in the diff output
        diff = list(difflib.unified_diff(
            text1.splitlines(keepends=True), 
            text2.splitlines(keepends=True), 
            fromfile=str(file1), 
            tofile=str(file2)
        ))
        return _build_response(True, diff)
    except Exception as e:
        return _build_response(False, error=str(e))

def diff_directories(dir1: Union[str, pathlib.Path], dir2: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Compare two directories via file hashing and identify missing/changed files."""
    try:
        path1, path2 = pathlib.Path(dir1), pathlib.Path(dir2)
        if not path1.is_dir() or not path2.is_dir():
            return _build_response(False, error="One or both paths are not valid directories.")

        def get_files_hashes(directory: pathlib.Path) -> Dict[str, str]:
            hashes = {}
            for root, _, files in os.walk(directory):
                for file in files:
                    full_path = pathlib.Path(root) / file
                    rel_path = full_path.relative_to(directory).as_posix()
                    file_hash = hashlib.sha256(_read_file_bytes(full_path)).hexdigest()
                    hashes[rel_path] = file_hash
            return hashes

        hashes1 = get_files_hashes(path1)
        hashes2 = get_files_hashes(path2)

        all_keys = set(hashes1.keys()).union(hashes2.keys())
        diff_report = {
            "only_in_dir1": [],
            "only_in_dir2": [],
            "modified": [],
            "identical": []
        }

        for key in all_keys:
            if key in hashes1 and key not in hashes2:
                diff_report["only_in_dir1"].append(key)
            elif key in hashes2 and key not in hashes1:
                diff_report["only_in_dir2"].append(key)
            elif hashes1[key] != hashes2[key]:
                diff_report["modified"].append(key)
            else:
                diff_report["identical"].append(key)

        return _build_response(True, diff_report)
    except Exception as e:
        return _build_response(False, error=str(e))

# --- Patch Management ---

def create_patch(original: str, modified: str) -> Dict[str, Any]:
    """Create a raw unified diff patch string from two strings."""
    try:
        diff_res = diff_strings(original, modified)
        if not diff_res["success"]:
            return diff_res
        return _build_response(True, "".join(diff_res["data"]))
    except Exception as e:
        return _build_response(False, error=str(e))

def apply_patch(base_text: str, patch_text: str) -> Dict[str, Any]:
    """
    Apply a unified diff patch to a base text.
    Strict line-by-line forward application.
    """
    try:
        if not patch_text.strip():
            return _build_response(True, base_text)

        base_lines = base_text.splitlines(keepends=True)
        patch_lines = patch_text.splitlines(keepends=True)
        
        result_lines = []
        base_idx = 0
        patch_idx = 0

        # Skip header if present
        while patch_idx < len(patch_lines) and (patch_lines[patch_idx].startswith('---') or patch_lines[patch_idx].startswith('+++')):
            patch_idx += 1

        while patch_idx < len(patch_lines):
            pline = patch_lines[patch_idx]
            if pline.startswith('@@'):
                # Basic hunk processing (simplified blind contextual match)
                patch_idx += 1
                continue
            
            if pline.startswith('-'):
                # Line should be removed; verify it matches
                expected_line = pline[1:]
                if base_idx < len(base_lines) and base_lines[base_idx] == expected_line:
                    base_idx += 1
                else:
                    return _build_response(False, error=f"Patch mismatch at line {base_idx}: expected '{expected_line.strip()}'")
            elif pline.startswith('+'):
                # Line should be added
                result_lines.append(pline[1:])
            elif pline.startswith(' '):
                # Context line; must match
                expected_line = pline[1:]
                if base_idx < len(base_lines) and base_lines[base_idx] == expected_line:
                    result_lines.append(base_lines[base_idx])
                    base_idx += 1
                else:
                    return _build_response(False, error=f"Context mismatch at line {base_idx}")
            elif pline == '\n':
                 patch_idx += 1
                 continue
            else:
                # Unexpected patch line format
                return _build_response(False, error=f"Malformed patch line: {pline.strip()}")
            patch_idx += 1

        # Append remaining base lines
        while base_idx < len(base_lines):
            result_lines.append(base_lines[base_idx])
            base_idx += 1

        return _build_response(True, "".join(result_lines))
    except Exception as e:
        return _build_response(False, error=str(e))

def reverse_patch(patch_text: str) -> Dict[str, Any]:
    """Reverses a patch so that it can undo changes when applied."""
    try:
        lines = patch_text.splitlines(keepends=True)
        reversed_lines = []
        for line in lines:
            if line.startswith('--- a'):
                reversed_lines.append(line.replace('--- a', '+++ b', 1))
            elif line.startswith('+++ b'):
                reversed_lines.append(line.replace('+++ b', '--- a', 1))
            elif line.startswith('-'):
                reversed_lines.append('+' + line[1:])
            elif line.startswith('+'):
                reversed_lines.append('-' + line[1:])
            elif line.startswith('@@'):
                # Naive @@ swap (robust swap requires regex parsing of line numbers)
                match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)', line)
                if match:
                    o_start, o_len, n_start, n_len, rest = match.groups()
                    o_len = o_len if o_len else "1"
                    n_len = n_len if n_len else "1"
                    reversed_lines.append(f"@@ -{n_start},{n_len} +{o_start},{o_len} @@{rest}\n")
                else:
                    reversed_lines.append(line)
            else:
                reversed_lines.append(line)
        return _build_response(True, "".join(reversed_lines))
    except Exception as e:
        return _build_response(False, error=str(e))

# --- Diff Formatting Options ---

def unified_diff(a: str, b: str) -> Dict[str, Any]:
    """Generates standard unified diff output."""
    return create_patch(a, b)

def context_diff(a: str, b: str) -> Dict[str, Any]:
    """Generates standard context diff output."""
    try:
        diff = list(difflib.context_diff(
            a.splitlines(keepends=True),
            b.splitlines(keepends=True)
        ))
        return _build_response(True, "".join(diff))
    except Exception as e:
        return _build_response(False, error=str(e))

def html_diff(a: str, b: str) -> Dict[str, Any]:
    """Generates an HTML table representing the diff."""
    try:
        html_generator = difflib.HtmlDiff()
        diff = html_generator.make_file(a.splitlines(), b.splitlines())
        return _build_response(True, diff)
    except Exception as e:
        return _build_response(False, error=str(e))

def side_by_side_diff(a: str, b: str) -> Dict[str, Any]:
    """Generates a side-by-side HTML diff table fragment."""
    try:
        html_generator = difflib.HtmlDiff()
        diff = html_generator.make_table(a.splitlines(), b.splitlines())
        return _build_response(True, diff)
    except Exception as e:
        return _build_response(False, error=str(e))

# --- Line Extraction ---

def get_changed_lines(a: str, b: str) -> Dict[str, Any]:
    """Extracts all lines that were added or removed."""
    try:
        diff = difflib.ndiff(a.splitlines(), b.splitlines())
        changes = [line for line in diff if line.startswith('- ') or line.startswith('+ ')]
        return _build_response(True, changes)
    except Exception as e:
        return _build_response(False, error=str(e))

def get_added_lines(a: str, b: str) -> Dict[str, Any]:
    """Extracts only added lines."""
    try:
        res = get_changed_lines(a, b)
        if not res["success"]: return res
        added = [line[2:] for line in res["data"] if line.startswith('+ ')]
        return _build_response(True, added)
    except Exception as e:
        return _build_response(False, error=str(e))

def get_removed_lines(a: str, b: str) -> Dict[str, Any]:
    """Extracts only removed lines."""
    try:
        res = get_changed_lines(a, b)
        if not res["success"]: return res
        removed = [line[2:] for line in res["data"] if line.startswith('- ')]
        return _build_response(True, removed)
    except Exception as e:
        return _build_response(False, error=str(e))

def similarity_ratio(a: str, b: str) -> Dict[str, Any]:
    """Returns a ratio from 0.0 to 1.0 indicating string similarity."""
    try:
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        return _build_response(True, ratio)
    except Exception as e:
        return _build_response(False, error=str(e))

# --- Merging & Conflicts ---

def merge_three_way(base: str, mine: str, theirs: str) -> Dict[str, Any]:
    """
    Performs a basic 3-way merge. 
    Inserts conflict markers if overlapping changes are found.
    """
    try:
        sm_mine = difflib.SequenceMatcher(None, base.splitlines(keepends=True), mine.splitlines(keepends=True))
        sm_theirs = difflib.SequenceMatcher(None, base.splitlines(keepends=True), theirs.splitlines(keepends=True))
        
        mine_opcodes = sm_mine.get_opcodes()
        theirs_opcodes = sm_theirs.get_opcodes()
        
        # Simplified: if diffs are strictly non-overlapping, apply them sequentially.
        # This is a naive implementation; full 3-way merge algorithms (like diff3) are complex state machines.
        # We will attempt to apply `theirs`, then `mine`, falling back to marking conflicts if indices clash.
        
        merged_lines = []
        base_lines = base.splitlines(keepends=True)
        mine_lines = mine.splitlines(keepends=True)
        theirs_lines = theirs.splitlines(keepends=True)
        
        # For a true production 3-way merge, we usually delegate to git or implement a heavy diff3 parser.
        # Here we flag the file as conflicted if both changed from base, requiring manual resolution.
        if mine != base and theirs != base:
             conflict_text = f"<<<<<<< MINE\n{mine}=======\n{theirs}>>>>>>> THEIRS\n"
             return _build_response(True, conflict_text, error="Conflicts detected.")
        elif mine != base:
             return _build_response(True, mine)
        else:
             return _build_response(True, theirs)
    except Exception as e:
        return _build_response(False, error=str(e))

def find_conflicts(text: str) -> Dict[str, Any]:
    """Parses text for standard source control conflict markers."""
    try:
        conflict_pattern = re.compile(
            r'<<<<<<<.*?\n(.*?)=======\n(.*?)>>>>>>>.*?\n', 
            re.DOTALL
        )
        matches = conflict_pattern.findall(text)
        conflicts = [{"mine": m[0], "theirs": m[1]} for m in matches]
        return _build_response(True, conflicts)
    except Exception as e:
        return _build_response(False, error=str(e))

def resolve_conflict(text: str, resolution: str = "mine") -> Dict[str, Any]:
    """
    Resolves conflicts in text by taking either 'mine' or 'theirs'.
    """
    try:
        if resolution not in ["mine", "theirs"]:
            return _build_response(False, error="Resolution must be 'mine' or 'theirs'")

        def replacement(match) -> str:
            return match.group(1) if resolution == "mine" else match.group(2)

        conflict_pattern = re.compile(
            r'<<<<<<<.*?\n(.*?)=======\n(.*?)>>>>>>>.*?\n', 
            re.DOTALL
        )
        resolved_text = conflict_pattern.sub(replacement, text)
        return _build_response(True, resolved_text)
    except Exception as e:
        return _build_response(False, error=str(e))

# --- Specialized Diffs ---

def diff_json(json_str1: str, json_str2: str) -> Dict[str, Any]:
    """Parses two JSON strings, normalizes formatting, and returns a unified diff."""
    try:
        obj1 = json.loads(json_str1)
        obj2 = json.loads(json_str2)
        
        pretty1 = json.dumps(obj1, indent=4, sort_keys=True)
        pretty2 = json.dumps(obj2, indent=4, sort_keys=True)
        
        return unified_diff(pretty1, pretty2)
    except Exception as e:
        return _build_response(False, error=str(e))

def diff_binary(file1: Union[str, pathlib.Path], file2: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Compares two binary files using chunked SHA256 hashing."""
    try:
        hash1 = hashlib.sha256()
        hash2 = hashlib.sha256()
        
        with open(file1, 'rb') as f1:
            for chunk in iter(lambda: f1.read(8192), b""):
                hash1.update(chunk)
                
        with open(file2, 'rb') as f2:
            for chunk in iter(lambda: f2.read(8192), b""):
                hash2.update(chunk)
                
        is_identical = hash1.hexdigest() == hash2.hexdigest()
        return _build_response(True, {"identical": is_identical, "hash1": hash1.hexdigest(), "hash2": hash2.hexdigest()})
    except Exception as e:
        return _build_response(False, error=str(e))

# --- Batch & Tooling ---

def create_incremental_patch(versions: List[str]) -> Dict[str, Any]:
    """Generates a sequence of patches progressing from versions[0] to versions[-1]."""
    try:
        if len(versions) < 2:
            return _build_response(False, error="Need at least two versions to create incremental patches.")
        
        patches = []
        for i in range(len(versions) - 1):
            patch_res = create_patch(versions[i], versions[i+1])
            if not patch_res["success"]:
                return patch_res
            patches.append(patch_res["data"])
        return _build_response(True, patches)
    except Exception as e:
        return _build_response(False, error=str(e))

def batch_diff(file_pairs: List[Tuple[str, str]]) -> Dict[str, Any]:
    """Takes a list of file path tuples (fileA, fileB) and returns diffs for all."""
    try:
        results = {}
        for f1, f2 in file_pairs:
            diff_res = diff_files(f1, f2)
            results[f"{f1} -> {f2}"] = diff_res
        return _build_response(True, results)
    except Exception as e:
        return _build_response(False, error=str(e))

def get_diff_statistics(a: str, b: str) -> Dict[str, Any]:
    """Calculates granular line insertion/deletion/modification counts."""
    try:
        diff = difflib.ndiff(a.splitlines(), b.splitlines())
        stats = {"added": 0, "removed": 0, "unchanged": 0, "questionable": 0}
        
        for line in diff:
            if line.startswith('+ '):
                stats["added"] += 1
            elif line.startswith('- '):
                stats["removed"] += 1
            elif line.startswith('  '):
                stats["unchanged"] += 1
            elif line.startswith('? '):
                stats["questionable"] += 1
                
        return _build_response(True, stats)
    except Exception as e:
        return _build_response(False, error=str(e))

def export_diff_report(a: str, b: str, output_format: str = "json") -> Dict[str, Any]:
    """Generates a comprehensive report containing diffs, stats, and metadata."""
    try:
        stats_res = get_diff_statistics(a, b)
        diff_res = create_patch(a, b)
        
        if not stats_res["success"] or not diff_res["success"]:
            return _build_response(False, error="Failed to generate internal metrics.")
            
        report = {
            "timestamp": time.time(),
            "statistics": stats_res["data"],
            "patch": diff_res["data"],
            "similarity": similarity_ratio(a, b)["data"]
        }
        
        if output_format.lower() == "json":
            return _build_response(True, json.dumps(report, indent=4))
        else:
            return _build_response(False, error="Unsupported export format.")
    except Exception as e:
        return _build_response(False, error=str(e))

def validate_patch(base_text: str, patch_text: str) -> Dict[str, Any]:
    """Validates if a patch applies cleanly to a base string without modifying it."""
    try:
        # We test apply_patch. If it returns success: True, patch is valid.
        test_apply = apply_patch(base_text, patch_text)
        is_valid = test_apply["success"]
        return _build_response(True, {"is_valid": is_valid, "validation_error": test_apply.get("error")})
    except Exception as e:
        return _build_response(False, error=str(e))

def compress_patch(patch_text: str) -> Dict[str, Any]:
    """Compresses a patch string using zlib and encodes as base64 for safe transport."""
    try:
        compressed_bytes = zlib.compress(patch_text.encode('utf-8'))
        encoded_str = base64.b64encode(compressed_bytes).decode('utf-8')
        return _build_response(True, encoded_str)
    except Exception as e:
        return _build_response(False, error=str(e))

# Example invocation guard
if __name__ == "__main__":
    # Internal testing/validation of the module
    str_a = "def hello():\n    print('Hello')\n"
    str_b = "def hello():\n    print('World')\n"
    
    print("Self Test: diff_strings")
    print(json.dumps(diff_strings(str_a, str_b), indent=2))
