"""toolkit_106_code_diff_tools.py
Compare code versions, generate unified diffs, apply patches, analyze changes.
"""
import difflib
import os
import re
import json
from pathlib import Path

def diff_strings(text1: str, text2: str, label1: str = "original", label2: str = "modified", context_lines: int = 3) -> dict:
    """Generate a unified diff between two strings."""
    try:
        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)
        diff = list(difflib.unified_diff(lines1, lines2, fromfile=label1, tofile=label2, n=context_lines))
        diff_text = "".join(diff)
        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
        return {"success": True, "data": {"diff": diff_text, "added_lines": added, "removed_lines": removed, "changed": len(diff) > 0}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def diff_files(file1: str, file2: str, context_lines: int = 3) -> dict:
    """Generate unified diff between two files."""
    try:
        with open(file1, encoding="utf-8", errors="replace") as f:
            text1 = f.read()
        with open(file2, encoding="utf-8", errors="replace") as f:
            text2 = f.read()
        return diff_strings(text1, text2, file1, file2, context_lines)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def diff_directories(dir1: str, dir2: str) -> dict:
    """Compare two directories and report differing files."""
    try:
        import filecmp
        cmp = filecmp.dircmp(dir1, dir2)
        only_left = [os.path.join(dir1, f) for f in cmp.left_only]
        only_right = [os.path.join(dir2, f) for f in cmp.right_only]
        different = [os.path.join(dir1, f) for f in cmp.diff_files]
        return {"success": True, "data": {"only_in_left": only_left, "only_in_right": only_right, "different_files": different, "identical": cmp.same_files}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def apply_patch(original: str, patch: str) -> dict:
    """Apply a unified diff patch to original text."""
    try:
        lines = original.splitlines(keepends=True)
        patch_lines = patch.splitlines()
        result = list(lines)
        hunk_header = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
        i = 0
        offset = 0
        while i < len(patch_lines):
            m = hunk_header.match(patch_lines[i])
            if m:
                orig_start = int(m.group(1)) - 1 + offset
                hunk_lines = []
                i += 1
                while i < len(patch_lines) and not patch_lines[i].startswith("@@") and not patch_lines[i].startswith("---") and not patch_lines[i].startswith("+++"):
                    hunk_lines.append(patch_lines[i])
                    i += 1
                removes = [l[1:] for l in hunk_lines if l.startswith("-")]
                adds = [l[1:] for l in hunk_lines if l.startswith("+")]
                del_count = len(removes)
                for j in range(del_count):
                    if orig_start < len(result):
                        result.pop(orig_start)
                for j, line in enumerate(adds):
                    result.insert(orig_start + j, line if line.endswith("\n") else line + "\n")
                offset += len(adds) - del_count
            else:
                i += 1
        return {"success": True, "data": "".join(result), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_changed_lines(text1: str, text2: str) -> dict:
    """Get list of changed line numbers between two texts."""
    try:
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()
        matcher = difflib.SequenceMatcher(None, lines1, lines2)
        changes = []
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op != "equal":
                changes.append({"operation": op, "original_lines": [i1+1, i2], "new_lines": [j1+1, j2]})
        return {"success": True, "data": {"changes": changes, "count": len(changes)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def similarity_ratio(text1: str, text2: str) -> dict:
    """Calculate similarity ratio between two texts (0.0 to 1.0)."""
    try:
        ratio = difflib.SequenceMatcher(None, text1, text2).ratio()
        return {"success": True, "data": {"ratio": round(ratio, 4), "percent": round(ratio*100, 2)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_close_matches(word: str, possibilities: list, n: int = 3, cutoff: float = 0.6) -> dict:
    """Find closest matching strings using difflib."""
    try:
        matches = difflib.get_close_matches(word, possibilities, n=n, cutoff=cutoff)
        return {"success": True, "data": matches, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def word_diff(text1: str, text2: str) -> dict:
    """Generate word-level diff between two texts."""
    try:
        words1 = text1.split()
        words2 = text2.split()
        diff = list(difflib.ndiff(words1, words2))
        added = [w[2:] for w in diff if w.startswith("+ ")]
        removed = [w[2:] for w in diff if w.startswith("- ")]
        return {"success": True, "data": {"diff": " ".join(diff), "added": added, "removed": removed}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def git_diff_file(file_path: str, repo_path: str = ".") -> dict:
    """Get git diff for a specific file."""
    try:
        import subprocess
        result = subprocess.run(["git", "diff", "HEAD", file_path], capture_output=True, text=True, cwd=repo_path, timeout=10)
        return {"success": result.returncode == 0, "data": result.stdout, "error": result.stderr if result.returncode != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def save_diff_to_file(text1: str, text2: str, output_path: str, label1: str = "original", label2: str = "modified") -> dict:
    """Generate and save a diff to a patch file."""
    try:
        result = diff_strings(text1, text2, label1, label2)
        if result["success"]:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result["data"]["diff"])
            return {"success": True, "data": {"path": output_path, "size": len(result["data"]["diff"])}, "error": None}
        return result
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def three_way_merge(base: str, version1: str, version2: str) -> dict:
    """Perform a simple 3-way text merge."""
    try:
        base_lines = base.splitlines(keepends=True)
        v1_lines = version1.splitlines(keepends=True)
        v2_lines = version2.splitlines(keepends=True)
        result = list(difflib.Differ().compare(base_lines, v1_lines))
        conflicts = sum(1 for l in result if l.startswith("? "))
        merged = "".join(l[2:] for l in result if not l.startswith("? "))
        return {"success": True, "data": {"merged": merged, "conflicts": conflicts}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def diff_json(json1_str: str, json2_str: str) -> dict:
    """Compare two JSON objects and report differences."""
    try:
        d1 = json.loads(json1_str) if isinstance(json1_str, str) else json1_str
        d2 = json.loads(json2_str) if isinstance(json2_str, str) else json2_str
        def _compare(obj1, obj2, path=""):
            diffs = []
            if type(obj1) != type(obj2):
                diffs.append({"path": path, "type": "type_change", "from": type(obj1).__name__, "to": type(obj2).__name__})
            elif isinstance(obj1, dict):
                all_keys = set(obj1) | set(obj2)
                for k in all_keys:
                    new_path = path + "." + str(k) if path else str(k)
                    if k not in obj1:
                        diffs.append({"path": new_path, "type": "added", "value": obj2[k]})
                    elif k not in obj2:
                        diffs.append({"path": new_path, "type": "removed", "value": obj1[k]})
                    else:
                        diffs.extend(_compare(obj1[k], obj2[k], new_path))
            elif obj1 != obj2:
                diffs.append({"path": path, "type": "changed", "from": obj1, "to": obj2})
            return diffs
        diffs = _compare(d1, d2)
        return {"success": True, "data": {"differences": diffs, "count": len(diffs), "identical": len(diffs)==0}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
