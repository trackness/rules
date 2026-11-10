#!/usr/bin/env python3
"""Allow work only on a branch."""
import subprocess
from pathlib import Path

# shortcut: a shared branch with another name, such as trunk, is not kept free of work; read the remote's HEAD if a repository uses one
SHARED_BRANCHES = ("main", "master", "develop")


def git(directory, *args):
    """Run git in directory with the given arguments, and return the finished process."""
    return subprocess.run(["git", "-C", directory, *args], capture_output=True, text=True)


def off_a_work_branch(directory):
    """Where the repository holding directory is checked out when that is not a work branch, such as "on main"."""
    # git fails here outside a repository, and in a new one, which has no main to branch from yet, so its first commit is made on main.
    if git(directory, "rev-parse", "--verify", "-q", "HEAD").returncode != 0:
        return None
    branch = git(directory, "branch", "--show-current").stdout.strip()
    if not branch:
        # git detaches HEAD while it rebases a branch, and keeps the rebase's state in this directory.
        rebase_state = git(directory, "rev-parse", "--path-format=absolute", "--git-path", "rebase-merge").stdout.strip()
        return None if Path(rebase_state).is_dir() else "on a detached HEAD"
    return f"on {branch}" if branch in SHARED_BRANCHES else None
