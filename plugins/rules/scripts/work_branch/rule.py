#!/usr/bin/env python3
"""Allow work only on a branch."""
import subprocess


def off_a_work_branch(directory):
    """Where the repository holding directory is checked out when that is not a work branch, such as "on main"."""
    in_repository = subprocess.run(["git", "-C", directory, "rev-parse", "--git-dir"], capture_output=True).returncode == 0
    branch = subprocess.run(["git", "-C", directory, "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
    return "on main" if in_repository and branch == "main" else None
