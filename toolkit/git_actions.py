import subprocess
import os
import json
import re
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Union


def _sanitize_value(val: Any) -> Any:
    """Ensure returned data is JSON-serializable."""
    if isinstance(val, Path):
        return str(val)
    if isinstance(val, (dict, list)):
        return json.loads(json.dumps(val, default=str))
    return val


def _run_git(
    args: List[str],
    cwd: str = ".",
    timeout: int = 120,
    capture_output: bool = True,
    text: bool = True
) -> Dict[str, Any]:
    """Core helper to execute git commands with robust error handling and path resolution."""
    if not shutil.which("git"):
        return {
            "success": False,
            "returncode": -2,
            "stdout": "",
            "stderr": "git executable not found in PATH",
            "error": "GitNotFound",
            "data": None
        }

    cwd_path = Path(cwd).resolve()
    if not cwd_path.is_dir():
        return {
            "success": False,
            "returncode": 1,
            "stdout": "",
            "stderr": f"Directory does not exist: {cwd}",
            "error": "PathNotFound",
            "data": None
        }

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"  # Prevent credential prompts from hanging
    env["GIT_PAGER"] = ""             # Avoid pager interference

    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd_path),
            capture_output=capture_output,
            text=text,
            check=False,
            timeout=timeout,
            env=env
        )
        success = result.returncode == 0
        return {
            "success": success,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "error": None if success else result.stderr.strip(),
            "data": None
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "Command timed out",
            "error": "TimeoutExpired",
            "data": None
        }
    except subprocess.SubprocessError as e:
        return {
            "success": False,
            "returncode": -3,
            "stdout": "",
            "stderr": str(e),
            "error": type(e).__name__,
            "data": None
        }
    except Exception as e:
        return {
            "success": False,
            "returncode": -4,
            "stdout": "",
            "stderr": str(e),
            "error": type(e).__name__,
            "data": None
        }


def git_init(path: str) -> Dict[str, Any]:
    """Initialize a new Git repository at the specified path."""
    repo_path = Path(path).resolve()
    os.makedirs(repo_path, exist_ok=True)
    res = _run_git(["init"], cwd=str(repo_path))
    return res


def git_clone(url: str, dest: str = "") -> Dict[str, Any]:
    """Clone a repository from a URL into the destination directory."""
    cmd = ["clone", url]
    if dest:
        cmd.append(dest)
    return _run_git(cmd, cwd=".")


def git_status(repo_path: str = ".") -> Dict[str, Any]:
    """Return parsed repository status."""
    res = _run_git(["status", "--porcelain=v1", "--untracked-files=all"], cwd=repo_path)
    if res["success"]:
        parsed = []
        for line in res["stdout"].splitlines():
            if not line.strip():
                continue
            match = re.match(r"^([ADMRCU?!.]{2})\s+(.+)$", line)
            if match:
                staged, unstaged = list(match.group(1))
                parsed.append({
                    "xy": match.group(1),
                    "staged": staged != " ",
                    "unstaged": unstaged != " ",
                    "path": match.group(2).strip()
                })
        res["data"] = parsed
    return res


def git_add(files: list = None, repo_path: str = ".") -> Dict[str, Any]:
    """Stage files for commit. If files is None, stages all changes."""
    cmd = ["add"]
    if files is None:
        cmd.append(".")
    else:
        cmd.extend(files)
    return _run_git(cmd, cwd=repo_path)


def git_commit(message: str, repo_path: str = ".") -> Dict[str, Any]:
    """Commit staged changes with a message."""
    if not message.strip():
        return {
            "success": False,
            "returncode": 1,
            "stdout": "",
            "stderr": "Commit message cannot be empty",
            "error": "EmptyMessage",
            "data": None
        }
    return _run_git(["commit", "-m", message], cwd=repo_path)


def git_push(remote: str = "origin", branch: str = "", repo_path: str = ".") -> Dict[str, Any]:
    """Push commits to a remote repository."""
    cmd = ["push", remote]
    if branch:
        cmd.append(branch)
    return _run_git(cmd, cwd=repo_path)


def git_pull(remote: str = "origin", branch: str = "", repo_path: str = ".") -> Dict[str, Any]:
    """Fetch and merge from a remote repository."""
    cmd = ["pull", remote]
    if branch:
        cmd.append(branch)
    return _run_git(cmd, cwd=repo_path)


def git_fetch(remote: str = "origin", repo_path: str = ".") -> Dict[str, Any]:
    """Download objects and refs from a remote repository."""
    return _run_git(["fetch", remote], cwd=repo_path)


def git_branch_list(repo_path: str = ".") -> Dict[str, Any]:
    """List local and remote branches."""
    res = _run_git(["branch", "-a", "--format=%(refname:short)"], cwd=repo_path)
    if res["success"]:
        res["data"] = [b.strip() for b in res["stdout"].splitlines() if b.strip()]
    return res


def git_branch_create(name: str, repo_path: str = ".") -> Dict[str, Any]:
    """Create a new branch without checking it out."""
    if not name or not name.strip():
        return {
            "success": False, "returncode": 1, "stdout": "",
            "stderr": "Branch name cannot be empty", "error": "EmptyName", "data": None
        }
    return _run_git(["branch", name.strip()], cwd=repo_path)


def git_branch_delete(name: str, force: bool = False, repo_path: str = ".") -> Dict[str, Any]:
    """Delete a branch. Use force=True to force delete unmerged branches."""
    if not name or not name.strip():
        return {
            "success": False, "returncode": 1, "stdout": "",
            "stderr": "Branch name cannot be empty", "error": "EmptyName", "data": None
        }
    flag = "-D" if force else "-d"
    return _run_git(["branch", flag, name.strip()], cwd=repo_path)


def git_checkout(branch: str, repo_path: str = ".") -> Dict[str, Any]:
    """Switch branches or restore working tree files."""
    if not branch or not branch.strip():
        return {
            "success": False, "returncode": 1, "stdout": "",
            "stderr": "Branch name cannot be empty", "error": "EmptyName", "data": None
        }
    return _run_git(["checkout", branch.strip()], cwd=repo_path)


def git_merge(branch: str, repo_path: str = ".") -> Dict[str, Any]:
    """Join two or more development histories together."""
    if not branch or not branch.strip():
        return {
            "success": False, "returncode": 1, "stdout": "",
            "stderr": "Branch name cannot be empty", "error": "EmptyName", "data": None
        }
    return _run_git(["merge", branch.strip()], cwd=repo_path)


def git_log(count: int = 10, repo_path: str = ".") -> Dict[str, Any]:
    """Show commit logs as structured list."""
    fmt = "%H|%s|%an|%ae|%ad"
    res = _run_git(["log", f"-n{count}", f"--pretty=format:{fmt}", "--date=iso"], cwd=repo_path)
    if res["success"] and res["stdout"]:
        entries = []
        for line in res["stdout"].splitlines():
            parts = line.split("|")
            if len(parts) == 5:
                entries.append({
                    "hash": parts[0],
                    "subject": parts[1],
                    "author_name": parts[2],
                    "author_email": parts[3],
                    "date": parts[4]
                })
        res["data"] = entries
    return res


def git_diff(file: str = "", staged: bool = False, repo_path: str = ".") -> Dict[str, Any]:
    """Show changes between commits, commit and working tree, etc."""
    cmd = ["diff"]
    if staged:
        cmd.append("--staged")
    if file:
        cmd.extend(["--", file])
    return _run_git(cmd, cwd=repo_path)


def git_stash(action: str = "push", message: str = "", repo_path: str = ".") -> Dict[str, Any]:
    """Stash the changes in a dirty working directory away."""
    valid_actions = {"push", "pop", "apply", "drop", "list", "clear", "save"}
    if action not in valid_actions:
        return {
            "success": False, "returncode": 1, "stdout": "",
            "stderr": f"Invalid stash action. Choose from {valid_actions}", "error": "InvalidAction", "data": None
        }
    cmd = ["stash", action]
    if action == "push" and message.strip():
        cmd.extend(["-m", message.strip()])
    elif action == "save" and message.strip():
        cmd.append(message.strip())
    return _run_git(cmd, cwd=repo_path)


def git_tag(name: str = "", message: str = "", repo_path: str = ".") -> Dict[str, Any]:
    """List, create, or delete tags. If name is empty, lists tags."""
    if not name:
        return _run_git(["tag"], cwd=repo_path)
    
    name = name.strip()
    cmd = ["tag"]
    if message.strip():
        cmd.extend(["-a", name, "-m", message.strip()])
    else:
        cmd.append(name)
    return _run_git(cmd, cwd=repo_path)


def git_remote_list(repo_path: str = ".") -> Dict[str, Any]:
    """List configured remotes with fetch/push URLs."""
    res = _run_git(["remote", "-v"], cwd=repo_path)
    if res["success"]:
        parsed = {}
        for line in res["stdout"].splitlines():
            match = re.match(r"^(\S+)\s+(\S+)\s+\((fetch|push)\)$", line.strip())
            if match:
                name, url, action = match.groups()
                if name not in parsed:
                    parsed[name] = {"fetch": None, "push": None}
                parsed[name][action] = url
        res["data"] = parsed
    return res


def git_remote_add(name: str, url: str, repo_path: str = ".") -> Dict[str, Any]:
    """Add a new remote repository."""
    if not name.strip() or not url.strip():
        return {
            "success": False, "returncode": 1, "stdout": "",
            "stderr": "Remote name and URL cannot be empty", "error": "EmptyInput", "data": None
        }
    return _run_git(["remote", "add", name.strip(), url.strip()], cwd=repo_path)


def git_reset(mode: str = "mixed", commit: str = "HEAD~1", repo_path: str = ".") -> Dict[str, Any]:
    """Reset current HEAD to the specified state."""
    valid_modes = {"soft", "mixed", "hard", "merge", "keep"}
    if mode not in valid_modes:
        return {
            "success": False, "returncode": 1, "stdout": "",
            "stderr": f"Invalid reset mode. Choose from {valid_modes}", "error": "InvalidMode", "data": None
        }
    return _run_git(["reset", f"--{mode}", commit.strip()], cwd=repo_path)


def git_rebase(branch: str, interactive: bool = False, repo_path: str = ".") -> Dict[str, Any]:
    """Reapply commits on top of another base tip."""
    if not branch.strip():
        return {
            "success": False, "returncode": 1, "stdout": "",
            "stderr": "Branch cannot be empty", "error": "EmptyName", "data": None
        }
    cmd = ["rebase"]
    if interactive:
        cmd.append("-i")
    cmd.append(branch.strip())
    return _run_git(cmd, cwd=repo_path)


def git_cherry_pick(commit: str, repo_path: str = ".") -> Dict[str, Any]:
    """Apply the changes introduced by some existing commits."""
    if not commit.strip():
        return {
            "success": False, "returncode": 1, "stdout": "",
            "stderr": "Commit hash cannot be empty", "error": "EmptyName", "data": None
        }
    return _run_git(["cherry-pick", commit.strip()], cwd=repo_path)


def git_blame(file: str, repo_path: str = ".") -> Dict[str, Any]:
    """Show what revision and author last modified each line of a file."""
    if not file.strip():
        return {
            "success": False, "returncode": 1, "stdout": "",
            "stderr": "File path cannot be empty", "error": "EmptyFile", "data": None
        }
    return _run_git(["blame", "-l", file.strip()], cwd=repo_path)


def git_config(key: str, value: str = "", scope: str = "local", repo_path: str = ".") -> Dict[str, Any]:
    """Get or set Git configuration. If value is empty, retrieves the config."""
    valid_scopes = {"local", "global", "system", "worktree"}
    if scope not in valid_scopes:
        return {
            "success": False, "returncode": 1, "stdout": "",
            "stderr": f"Invalid scope. Choose from {valid_scopes}", "error": "InvalidScope", "data": None
        }
    cmd = ["config", f"--{scope}"]
    if value.strip():
        cmd.extend([key.strip(), value.strip()])
    else:
        cmd.append(key.strip())
    res = _run_git(cmd, cwd=repo_path)
    if res["success"] and not value.strip():
        res["data"] = res["stdout"]
    return res


def git_archive(output: str, branch: str = "HEAD", repo_path: str = ".") -> Dict[str, Any]:
    """Create an archive of files from a named tree."""
    out_path = Path(output).resolve()
    os.makedirs(out_path.parent, exist_ok=True)
    return _run_git(["archive", "-o", str(out_path), branch.strip()], cwd=repo_path)