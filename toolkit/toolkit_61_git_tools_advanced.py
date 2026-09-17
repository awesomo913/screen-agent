"""
toolkit_61_git_tools_advanced.py
Advanced Git operations: status, diff summary, branch management, stash,
log parsing, conflict detection, and repository statistics.
Complements git_actions (basic push/pull/commit) with analysis and inspection.
"""
from __future__ import annotations
import subprocess
import os
import re
from pathlib import Path
from typing import Any, Dict, List

def _git(args: list, cwd: str = "", timeout: int = 30) -> tuple:
    result = subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, timeout=timeout,
        cwd=cwd if cwd else None
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def get_repo_status(repo_path: str = ".") -> Dict[str, Any]:
    try:
        out, err, code = _git(["status", "--porcelain=v1"], cwd=repo_path)
        lines = out.splitlines()
        staged, unstaged, untracked = [], [], []
        for line in lines:
            if not line: continue
            xy = line[:2]
            fname = line[3:]
            if xy[0] in "MADRC": staged.append(fname)
            if xy[1] in "MD": unstaged.append(fname)
            if xy == "??": untracked.append(fname)
        branch_out, _, _ = _git(["branch", "--show-current"], cwd=repo_path)
        return {"success": True, "data": {
            "branch": branch_out.strip(),
            "staged": staged, "unstaged": unstaged, "untracked": untracked,
            "is_clean": len(lines) == 0
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_current_branch(repo_path: str = ".") -> Dict[str, Any]:
    try:
        out, _, code = _git(["branch", "--show-current"], cwd=repo_path)
        return {"success": True, "data": out.strip(), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_branches(repo_path: str = ".", include_remote: bool = True) -> Dict[str, Any]:
    try:
        args = ["branch", "-a"] if include_remote else ["branch"]
        out, _, _ = _git(args, cwd=repo_path)
        branches = [b.strip().lstrip("* ") for b in out.splitlines() if b.strip()]
        return {"success": True, "data": branches, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_recent_commits(repo_path: str = ".", count: int = 10) -> Dict[str, Any]:
    try:
        fmt = "%H|%an|%ae|%ai|%s"
        out, _, _ = _git(["log", "--oneline", "-" + str(count), "--format=" + fmt], cwd=repo_path)
        commits = []
        for line in out.splitlines():
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({"hash": parts[0], "author": parts[1], "email": parts[2], "date": parts[3], "message": parts[4]})
        return {"success": True, "data": commits, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_diff_stat(repo_path: str = ".", staged: bool = False) -> Dict[str, Any]:
    try:
        args = ["diff", "--stat"]
        if staged:
            args = ["diff", "--stat", "--cached"]
        out, _, _ = _git(args, cwd=repo_path)
        return {"success": True, "data": out, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_file_diff(repo_path: str, file_path: str) -> Dict[str, Any]:
    try:
        out, _, _ = _git(["diff", "--", file_path], cwd=repo_path)
        return {"success": True, "data": out[:5000], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_stashes(repo_path: str = ".") -> Dict[str, Any]:
    try:
        out, _, _ = _git(["stash", "list"], cwd=repo_path)
        stashes = out.splitlines() if out else []
        return {"success": True, "data": {"count": len(stashes), "stashes": stashes}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_stash(repo_path: str = ".", message: str = "") -> Dict[str, Any]:
    try:
        args = ["stash", "push", "-m", message] if message else ["stash", "push"]
        out, err, code = _git(args, cwd=repo_path)
        return {"success": code == 0, "data": out, "error": err if code != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def pop_stash(repo_path: str = ".") -> Dict[str, Any]:
    try:
        out, err, code = _git(["stash", "pop"], cwd=repo_path)
        return {"success": code == 0, "data": out, "error": err if code != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_repo_stats(repo_path: str = ".") -> Dict[str, Any]:
    try:
        commit_count, _, _ = _git(["rev-list", "--count", "HEAD"], cwd=repo_path)
        authors_out, _, _ = _git(["shortlog", "-sn", "--no-merges", "HEAD"], cwd=repo_path)
        file_count_out, _, _ = _git(["ls-files"], cwd=repo_path)
        authors = []
        for line in authors_out.splitlines():
            parts = line.strip().split("\t", 1)
            if len(parts) == 2:
                authors.append({"commits": int(parts[0]), "name": parts[1]})
        return {"success": True, "data": {
            "total_commits": int(commit_count) if commit_count.isdigit() else 0,
            "tracked_files": len(file_count_out.splitlines()),
            "top_authors": authors[:5]
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_merge_conflicts(repo_path: str = ".") -> Dict[str, Any]:
    try:
        out, _, _ = _git(["diff", "--name-only", "--diff-filter=U"], cwd=repo_path)
        conflicted = [f for f in out.splitlines() if f]
        return {"success": True, "data": {"conflicted_files": conflicted, "count": len(conflicted)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_tags(repo_path: str = ".") -> Dict[str, Any]:
    try:
        out, _, _ = _git(["tag", "--sort=-version:refname"], cwd=repo_path)
        tags = out.splitlines() if out else []
        return {"success": True, "data": tags, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_remote_info(repo_path: str = ".") -> Dict[str, Any]:
    try:
        out, _, _ = _git(["remote", "-v"], cwd=repo_path)
        remotes: dict = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                remotes[parts[0]] = parts[1]
        return {"success": True, "data": remotes, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_git_repo(path: str) -> Dict[str, Any]:
    try:
        _, _, code = _git(["rev-parse", "--is-inside-work-tree"], cwd=path)
        return {"success": True, "data": code == 0, "error": None}
    except Exception as e:
        return {"success": True, "data": False, "error": None}

def get_ignored_files(repo_path: str = ".") -> Dict[str, Any]:
    try:
        out, _, _ = _git(["ls-files", "--others", "--ignored", "--exclude-standard"], cwd=repo_path)
        files = out.splitlines() if out else []
        return {"success": True, "data": {"count": len(files), "files": files[:100]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
