#!/usr/bin/env python3
"""Allow work only on a branch."""
import json
import os
import subprocess
import sys
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
        # git detaches HEAD while it rebases a branch, and keeps the rebase's state in one of these two directories.
        rebase_state = git(directory, "rev-parse", "--path-format=absolute", "--git-path", "rebase-merge", "--git-path", "rebase-apply").stdout.splitlines()
        return None if any(Path(path).is_dir() for path in rebase_state) else "on a detached HEAD"
    return f"on {branch}" if branch in SHARED_BRANCHES else None


def register(env_file):
    """Make git run this script as the pre-commit hook in the Bash commands of the Claude Code session that owns env_file."""
    with open(env_file, "a") as session_env:
        session_env.write(
            f'export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=hook.work-branch.command GIT_CONFIG_VALUE_0="{Path(__file__).resolve()} pre-commit" '
            "GIT_CONFIG_KEY_1=hook.work-branch.event GIT_CONFIG_VALUE_1=pre-commit\n"
        )


def pre_commit():
    """Return git's exit code for the commit it is about to make: 1 rejects the commit."""
    return 1


def main(stdin, stdout, stderr, env_file=None):
    """Read the Claude Code hook's input from stdin and return Claude Code's exit code."""
    hook_input = json.load(stdin)
    if hook_input.get("hook_event_name") == "SessionStart":
        register(env_file)
        return 0
    tool_input = hook_input["tool_input"]
    path = Path(tool_input.get("file_path") or tool_input["notebook_path"])  # NotebookEdit's name for its file
    # Write makes the directories a new file needs, so git is asked in the nearest one that exists.
    directory = next(parent for parent in path.parents if parent.is_dir())
    where = off_a_work_branch(directory)
    # A file git ignores is on no branch; check-ignore exits 0 for one.
    if not where or git(directory, "check-ignore", "-q", path).returncode == 0:
        return 0
    print(
        f"Blocked: work happens only on a branch, and this file's repository is {where}. "
        "Create a branch with git switch -c <type>/<description>, then make the change there.",
        file=stderr,
    )
    return 2


if __name__ == "__main__":
    # git runs this script as its pre-commit hook with the argument pre-commit; Claude Code runs it with no arguments
    sys.exit(pre_commit() if sys.argv[1:2] == ["pre-commit"] else main(sys.stdin, sys.stdout, sys.stderr, os.environ.get("CLAUDE_ENV_FILE")))
