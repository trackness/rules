#!/usr/bin/env python3
"""PreToolUse hook: allow only Conventional Branch names for branches a Bash call creates."""
import json
import os
import re
import shlex
import sys

# shortcut: git after sudo or env options, such as sudo -u root git, is not checked; skip those options if Claude runs git that way
COMMAND_PREFIXES = ("sudo", "env")
ENVIRONMENT_ASSIGNMENT = r"[A-Za-z_]\w*="
GIT_OPTIONS_WITH_VALUE = ("-c", "-C")
# shortcut: --orphan, and git branch with -f or --track, are not checked; add them if Claude creates branches that way
CREATE_OPTIONS = {"checkout": ("-b", "-B"), "switch": ("-c", "-C", "--create"), "worktree": ("-b", "-B")}
CONVENTIONAL = r"main|master|develop|(?:feature|feat|bugfix|fix|hotfix|chore)/[a-z0-9]+(?:-[a-z0-9]+)*|release/[a-z0-9]+(?:[-.][a-z0-9]+)*"


def conventional(name):
    """True if the branch name follows Conventional Branch."""
    return bool(re.fullmatch(CONVENTIONAL, name))


def new_branch_names(cmd):
    """The names of the branches the shell command cmd creates or renames a branch to."""
    try:
        words = shlex.split(cmd)
    except ValueError:  # an unbalanced quote, such as an apostrophe in a heredoc body, leaves no words to read
        return []
    while words and (words[0] in COMMAND_PREFIXES or re.match(ENVIRONMENT_ASSIGNMENT, words[0])):
        words = words[1:]
    if not words or os.path.basename(words[0]) != "git":
        return []
    words = words[1:]
    while words and words[0].startswith("-"):
        words = words[2:] if words[0] in GIT_OPTIONS_WITH_VALUE else words[1:]
    if not words:
        return []
    subcommand, args = words[0], words[1:]
    if subcommand == "branch":
        names = [arg for arg in args if not arg.startswith("-")]
        if "-m" in args or "-M" in args:
            return names[-1:]
        return [] if any(arg.startswith("-") for arg in args) else args[:1]
    create_options = CREATE_OPTIONS.get(subcommand, ())
    return [args[i + 1] for i, arg in enumerate(args[:-1]) if arg in create_options]


def main(stdin, stderr):
    """Read the Bash tool call from stdin and return Claude Code's exit code.

    A call that creates or renames a branch to a name that isn't Conventional Branch gets a reason on stderr and 2, which blocks it;
    anything else gets 0.
    """
    unconventional = [name for name in new_branch_names(json.load(stdin)["tool_input"]["command"]) if not conventional(name)]
    if not unconventional:
        return 0
    print(
        f"Blocked: branch name {', '.join(unconventional)} does not follow Conventional Branch. "
        "Use <type>/<description>, lowercase and hyphen-separated, with type feature, feat, bugfix, fix, hotfix, release or chore; "
        "dots are allowed only in a release version, such as release/v1.2.0. main, master and develop take no prefix.",
        file=stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.stdin, sys.stderr))
