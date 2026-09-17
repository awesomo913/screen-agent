"""toolkit_92_git_workflow.py
Advanced git workflow tools — branching, PRs, tagging, changelog generation.
"""
import subprocess
import os
import re
import json
from pathlib import Path
import datetime

def _git(args: list, cwd: str = '.') -> dict:
    try:
        result = subprocess.run(['git'] + args, capture_output=True, text=True, cwd=cwd, timeout=30)
        return {'stdout': result.stdout.strip(), 'stderr': result.stderr.strip(), 'code': result.returncode}
    except Exception as e:
        return {'stdout': '', 'stderr': str(e), 'code': -1}

def get_current_branch(repo_path: str = '.') -> dict:
    """Get the current git branch name."""
    try:
        r = _git(['rev-parse', '--abbrev-ref', 'HEAD'], repo_path)
        return {'success': r['code']==0, 'data': r['stdout'], 'error': r['stderr'] or None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_branches(repo_path: str = '.', all_branches: bool = False) -> dict:
    """List git branches."""
    try:
        args = ['branch', '-a'] if all_branches else ['branch']
        r = _git(args, repo_path)
        if r['code'] == 0:
            branches = [b.strip().lstrip('* ') for b in r['stdout'].splitlines() if b.strip()]
            return {'success': True, 'data': branches, 'error': None}
        return {'success': False, 'data': None, 'error': r['stderr']}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_branch(branch_name: str, repo_path: str = '.', from_branch: str = '') -> dict:
    """Create a new git branch."""
    try:
        args = ['checkout', '-b', branch_name]
        if from_branch:
            args.append(from_branch)
        r = _git(args, repo_path)
        return {'success': r['code']==0, 'data': {'branch': branch_name}, 'error': r['stderr'] if r['code']!=0 else None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def delete_branch(branch_name: str, repo_path: str = '.', force: bool = False) -> dict:
    """Delete a git branch."""
    try:
        flag = '-D' if force else '-d'
        r = _git(['branch', flag, branch_name], repo_path)
        return {'success': r['code']==0, 'data': {'deleted': branch_name}, 'error': r['stderr'] if r['code']!=0 else None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_git_log(repo_path: str = '.', max_commits: int = 20, format_str: str = '') -> dict:
    """Get git commit log."""
    try:
        fmt = format_str or '%H|%h|%s|%an|%ae|%ai'
        r = _git(['log', '--pretty=format:' + fmt, '-n', str(max_commits)], repo_path)
        if r['code'] == 0:
            commits = []
            for line in r['stdout'].splitlines():
                parts = line.split('|')
                if len(parts) >= 6:
                    commits.append({'hash': parts[0], 'short_hash': parts[1], 'message': parts[2], 'author': parts[3], 'email': parts[4], 'date': parts[5]})
                else:
                    commits.append({'raw': line})
            return {'success': True, 'data': commits, 'error': None}
        return {'success': False, 'data': None, 'error': r['stderr']}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_commit_diff(commit_hash: str, repo_path: str = '.') -> dict:
    """Get diff for a specific commit."""
    try:
        r = _git(['show', '--stat', commit_hash], repo_path)
        return {'success': r['code']==0, 'data': r['stdout'], 'error': r['stderr'] if r['code']!=0 else None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_tag(tag_name: str, message: str = '', repo_path: str = '.') -> dict:
    """Create an annotated git tag."""
    try:
        if message:
            r = _git(['tag', '-a', tag_name, '-m', message], repo_path)
        else:
            r = _git(['tag', tag_name], repo_path)
        return {'success': r['code']==0, 'data': {'tag': tag_name}, 'error': r['stderr'] if r['code']!=0 else None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_tags(repo_path: str = '.') -> dict:
    """List all git tags."""
    try:
        r = _git(['tag', '-l', '--sort=-version:refname'], repo_path)
        return {'success': r['code']==0, 'data': r['stdout'].splitlines(), 'error': r['stderr'] if r['code']!=0 else None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_changelog(repo_path: str = '.', from_tag: str = '', to_ref: str = 'HEAD') -> dict:
    """Generate a changelog from git commit messages."""
    try:
        if from_tag:
            r = _git(['log', from_tag + '..' + to_ref, '--pretty=format:%h|%s|%an|%ai'], repo_path)
        else:
            r = _git(['log', '--pretty=format:%h|%s|%an|%ai', '-n', '50'], repo_path)
        if r['code'] != 0:
            return {'success': False, 'data': None, 'error': r['stderr']}
        features, fixes, other = [], [], []
        for line in r['stdout'].splitlines():
            parts = line.split('|')
            if len(parts) >= 2:
                msg = parts[1]
                if re.match(r'^feat(ure)?[:(]', msg, re.IGNORECASE):
                    features.append('- ' + msg)
                elif re.match(r'^fix[:(]', msg, re.IGNORECASE) or 'bug' in msg.lower():
                    fixes.append('- ' + msg)
                else:
                    other.append('- ' + msg)
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        changelog = ['# Changelog', '', '## [Unreleased] - ' + today]
        if features:
            changelog.append('\n### Features'); changelog.extend(features)
        if fixes:
            changelog.append('\n### Bug Fixes'); changelog.extend(fixes)
        if other:
            changelog.append('\n### Other'); changelog.extend(other)
        return {'success': True, 'data': '\n'.join(changelog), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_repo_stats(repo_path: str = '.') -> dict:
    """Get overall repository statistics."""
    try:
        total_commits = _git(['rev-list', '--count', 'HEAD'], repo_path)
        contributors = _git(['shortlog', '-sn', '--all'], repo_path)
        files = _git(['ls-files'], repo_path)
        first_commit = _git(['log', '--reverse', '--pretty=format:%ai', '-1'], repo_path)
        last_commit = _git(['log', '--pretty=format:%ai', '-1'], repo_path)
        contribs = []
        for line in contributors['stdout'].splitlines():
            parts = line.strip().split('\t')
            if len(parts) == 2:
                contribs.append({'commits': int(parts[0].strip()), 'name': parts[1]})
        return {'success': True, 'data': {'total_commits': int(total_commits['stdout']) if total_commits['stdout'].isdigit() else 0, 'total_files': len(files['stdout'].splitlines()), 'contributors': contribs, 'first_commit': first_commit['stdout'], 'last_commit': last_commit['stdout']}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_unstaged_changes(repo_path: str = '.') -> dict:
    """Get a list of modified/unstaged files."""
    try:
        r = _git(['status', '--porcelain'], repo_path)
        if r['code'] == 0:
            changes = [{'status': line[:2].strip(), 'file': line[3:]} for line in r['stdout'].splitlines() if line.strip()]
            return {'success': True, 'data': changes, 'error': None}
        return {'success': False, 'data': None, 'error': r['stderr']}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def stash_changes(message: str = '', repo_path: str = '.') -> dict:
    """Stash current changes."""
    try:
        args = ['stash', 'push']
        if message:
            args += ['-m', message]
        r = _git(args, repo_path)
        return {'success': r['code']==0, 'data': r['stdout'], 'error': r['stderr'] if r['code']!=0 else None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def pop_stash(repo_path: str = '.') -> dict:
    """Apply and remove most recent stash."""
    try:
        r = _git(['stash', 'pop'], repo_path)
        return {'success': r['code']==0, 'data': r['stdout'], 'error': r['stderr'] if r['code']!=0 else None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def find_repos(search_dir: str = os.path.expanduser('~'), max_depth: int = 3) -> dict:
    """Find all git repositories in a directory."""
    try:
        repos = []
        for root, dirs, files in os.walk(search_dir):
            depth = root.replace(search_dir,'').count(os.sep)
            if depth > max_depth:
                dirs[:] = []
                continue
            if '.git' in dirs:
                repos.append(root)
                dirs[:] = []
        return {'success': True, 'data': repos, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
