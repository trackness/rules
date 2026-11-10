#!/usr/bin/env python3
"""Allow work only on a branch."""
import subprocess

# shortcut: a shared branch with another name, such as trunk, is not kept free of work; read the remote's HEAD if a repository uses one
SHARED_BRANCHES = ("main", "master", "develop")


def off_a_work_branch(directory):
    """Where the repository holding directory is checked out when that is not a work branch, such as "on main"."""
    # Outside a repository git fails and names no branch.
    branch = subprocess.run(["git", "-C", directory, "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
    return f"on {branch}" if branch in SHARED_BRANCHES else None
