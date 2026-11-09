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


# shortcut: a value joined to its option, such as --create=<name> or -b<name>, is not read; split it off if Claude writes options that way
def option_values(args, options):
    """The words in args that follow any of the given options."""
    return [args[i + 1] for i, arg in enumerate(args[:-1]) if arg in options]


def new_branch_names(cmd):
    """The names of the branches the shell command cmd creates, renames a branch to, or pushes to by a <src>:<dst> refspec."""
    try:
        words = shlex.split(cmd)
    except ValueError:  # an unbalanced quote, such as an apostrophe in a heredoc body, leaves no words to read
        return []
    while words and (words[0] in COMMAND_PREFIXES or re.match(ENVIRONMENT_ASSIGNMENT, words[0])):
        words = words[1:]
    program = os.path.basename(words[0]) if words else ""
    if program == "gh":
        # Without -b or --branch, gh names the branch after the pull request's own branch, which is not Claude's choice.
        # shortcut: the alias gh pr co is not checked; add it if Claude checks out pull requests that way
        return option_values(words[3:], ("-b", "--branch")) if words[1:3] == ["pr", "checkout"] else []
    if program != "git":
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
    if subcommand == "push":
        # shortcut: a value after -o, or --repo=, shifts which word is taken as the repository; parse push options if Claude pushes that way
        repository_and_refspecs = [arg for arg in args if not arg.startswith("-")]
        refspecs = [arg.partition(":") for arg in repository_and_refspecs[1:]]
        # An empty <src> deletes <dst>, which must stay possible for a badly named branch.
        destinations = [dst.removeprefix("refs/heads/") for src, colon, dst in refspecs if src and colon]
        return [dst for dst in destinations if not dst.startswith("refs/")]  # a ref outside refs/heads/, such as a tag, is not a branch
    return option_values(args, CREATE_OPTIONS.get(subcommand, ()))


def main(stdin, stderr):
    """Read the Bash tool call from stdin and return Claude Code's exit code.

    A call that creates, renames or pushes to a branch with a name that isn't Conventional Branch gets a reason on stderr and 2, which blocks it;
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
