#!/usr/bin/env python3
"""Allow work only on a branch: a PreToolUse hook for the files Claude changes, and git's pre-commit hook for the commits Claude makes."""
import json
import os
import subprocess
import sys
from pathlib import Path

# Run by its path, a script can import only from its own folder, and git_hook.py is in the scripts folder above it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import git_hook

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
    if branch not in SHARED_BRANCHES:
        return None
    # git switch -c refuses to run in a merge, cherry-pick or revert stopped at a conflict, which keeps its state in one of these files.
    stopped = git(
        directory, "rev-parse", "--path-format=absolute", "--git-path", "MERGE_HEAD", "--git-path", "CHERRY_PICK_HEAD", "--git-path", "REVERT_HEAD"
    ).stdout.splitlines()
    return None if any(Path(path).is_file() for path in stopped) else f"on {branch}"


def register(env_file, stdout):
    """Make git run this script as the pre-commit hook in the Bash commands of the Claude Code session that owns env_file."""
    git_hook.register(
        env_file, stdout, "work-branch", "pre-commit", [Path(__file__).resolve(), "pre-commit"], "The check that commits are made on a branch"
    )


def pre_commit(stderr):
    """Return git's exit code for the commit it is about to make: 1 rejects the commit, with a reason on stderr."""
    where = off_a_work_branch(".")  # git runs a pre-commit hook at the top of the working tree
    if not where:
        return 0
    print(
        f"Rejected: work happens only on a branch, and this repository is {where}, so nothing was committed. "
        "Create a branch with git switch -c <type>/<description>, which keeps the changes, and commit there.",
        file=stderr,
    )
    return 1


def main(stdin, stdout, stderr, env_file=None):
    """Read the Claude Code hook's input from stdin and return Claude Code's exit code.

    At SessionStart, register this script as git's pre-commit hook in env_file.
    A tool call that changes a file in a repository that is not on a work branch gets a reason on stderr and 2, which blocks it;
    anything else gets 0.
    """
    hook_input = json.load(stdin)
    if hook_input.get("hook_event_name") == "SessionStart":
        register(env_file, stdout)
        return 0
    tool_input = hook_input["tool_input"]
    path = Path(tool_input.get("file_path") or tool_input["notebook_path"])  # NotebookEdit's name for its file
    # Write makes the directories a new file needs, so git is asked in the nearest one that exists.
    directory = next(parent for parent in path.parents if parent.is_dir())
    where = off_a_work_branch(directory)
    # A file git ignores is on no branch; check-ignore exits 0 for one.
    if not where or git(directory, "check-ignore", "-q", path).returncode == 0:
        return 0
    # Nor is a file in the git directory, such as .git/config, where check-ignore fails.
    if git(directory, "rev-parse", "--is-inside-work-tree").stdout.strip() == "false":
        return 0
    print(
        f"Blocked: work happens only on a branch, and this file's repository is {where}. "
        "Create a branch with git switch -c <type>/<description>, then make the change there.",
        file=stderr,
    )
    return 2


if __name__ == "__main__":
    # git runs this script as its pre-commit hook with the argument pre-commit; Claude Code runs it with no arguments
    sys.exit(pre_commit(sys.stderr) if sys.argv[1:2] == ["pre-commit"] else main(sys.stdin.buffer, sys.stdout, sys.stderr, os.environ.get("CLAUDE_ENV_FILE")))
