#!/usr/bin/env python3
"""Allow only Conventional Branch names: a PreToolUse hook for the branches a Bash call creates, and git's pre-push hook for the remote branches a push creates."""
import json
import os
import re
import shlex
import sys
from pathlib import Path

# Run by its path, a script can import only from its own folder, and git_hook.py is in the scripts folder above it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import git_hook

# shortcut: git after sudo or env options, such as sudo -u root git, is not checked; skip those options if Claude runs git that way
COMMAND_PREFIXES = ("sudo", "env")
ENVIRONMENT_ASSIGNMENT = r"[A-Za-z_]\w*="
# A word made only of these characters ends a simple command, such as && or a newline, or is a redirection, such as > or the >& of 2>&1.
OPERATOR_CHARACTERS = "();<>|&\n"
REDIRECTION = r"&?[<>]+[&|]?"
GIT_OPTIONS_WITH_VALUE = ("-c", "-C")
# shortcut: --orphan, and git branch with -f or --track, are not checked; add them if Claude creates branches that way
CREATE_OPTIONS = {"checkout": ("-b", "-B"), "switch": ("-c", "-C", "--create"), "worktree": ("-b", "-B")}
# gh-pages is the branch GitHub Pages and the tools that publish to it name, not Claude.
CONVENTIONAL = r"main|master|develop|gh-pages|(?:feature|feat|bugfix|fix|hotfix|chore)/[a-z0-9]+(?:-[a-z0-9]+)*|release/[a-z0-9]+(?:[-.][a-z0-9]+)*"
NAMING = (
    "Use <type>/<description>, lowercase and hyphen-separated, with type feature, feat, bugfix, fix, hotfix, release or chore; "
    "dots are allowed only in a release version, such as release/v1.2.0. main, master, develop and gh-pages take no prefix."
)


def conventional(name):
    """True if the branch name follows Conventional Branch 1.0.0, or is gh-pages."""
    return bool(re.fullmatch(CONVENTIONAL, name))


# shortcut: a value joined to its option, such as --create=<name> or -b<name>, is not read; split it off if Claude writes options that way
def option_values(args, options):
    """The words in args that follow any of the given options."""
    return [args[i + 1] for i, arg in enumerate(args[:-1]) if arg in options]


# shortcut: a line of a heredoc's body is read as a command, and a quoted word that starts with # as the start of a comment; parse quotes as the shell does if either misreads Claude's commands
def simple_commands(cmd):
    """The words of each simple command in the shell command cmd, without redirections and comments; raises ValueError on an unbalanced quote."""
    # A backslash before a newline joins the two lines, where shlex would keep the newline as a word.
    lexer = shlex.shlex(cmd.replace("\\\n", ""), posix=True, punctuation_chars=OPERATOR_CHARACTERS)
    # A newline ends a command, and # starts a comment only as the first character of a word, which shlex's own comments do not check.
    lexer.whitespace, lexer.whitespace_split, lexer.commenters = " \t\r", True, ""
    tokens = iter(lexer)
    commands = [[]]
    for token in tokens:
        if token.startswith("#"):
            next((rest for rest in tokens if rest == "\n"), None)
            commands.append([])
        elif not token or set(token) - set(OPERATOR_CHARACTERS):
            commands[-1].append(token)
        elif re.fullmatch(REDIRECTION, token):
            # Neither the file a redirection names nor the file descriptor before it, the 2 of 2>&1, is a word of the command.
            if commands[-1] and commands[-1][-1].isdigit():
                commands[-1].pop()
            next(tokens, None)
        else:
            commands.append([])
    return commands


def new_branch_names(cmd):
    """The names of the branches the shell command cmd creates or renames a branch to."""
    try:
        commands = simple_commands(cmd)
    except ValueError:  # an unbalanced quote, such as an apostrophe in a heredoc body, leaves no words to read
        return []
    return [name for words in commands for name in command_branch_names(words)]


def command_branch_names(words):
    """The names of the branches the simple command with these words creates or renames a branch to."""
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
    # A push is left to the pre-push hook: only git sees whether the remote branch already exists, and an update of one, or a tag, must go through.
    return option_values(args, CREATE_OPTIONS.get(subcommand, ()))


def register(env_file, stdout):
    """Make git run this script as the pre-push hook in the Bash commands of the Claude Code session that owns env_file."""
    git_hook.register(
        env_file, stdout, "conventional-branch", "pre-push", [Path(__file__).resolve(), "pre-push"], "The Conventional Branch check on pushes"
    )


def new_remote_branches(push_lines):
    """The names of the remote branches a push creates, from the lines <local-ref> <local-oid> <remote-ref> <remote-oid> git passes a pre-push hook."""
    refs = [line.rsplit(maxsplit=3) for line in push_lines]  # the local ref is as typed, and can hold spaces, such as HEAD@{1 day ago}
    # An all-zero remote object is a ref the remote doesn't have yet, and an all-zero local object a deletion, which must stay possible
    # for a badly named branch; deleting a branch the remote no longer has gives both.
    return [
        remote_ref.removeprefix("refs/heads/")
        for local_ref, local_oid, remote_ref, remote_oid in refs
        if remote_ref.startswith("refs/heads/") and not remote_oid.strip("0") and local_oid.strip("0")
    ]


def pre_push(stdin, stderr):
    """Check the refs git passes a pre-push hook on stdin and return git's exit code: 1 refuses the push, with a reason on stderr."""
    unconventional = [name for name in new_remote_branches(stdin) if not conventional(name)]
    if not unconventional:
        return 0
    branches, names_do = ("branch", "name does") if len(unconventional) == 1 else ("branches", "names do")
    print(
        f"Rejected: this push would create the remote {branches} {', '.join(unconventional)}, whose {names_do} not follow Conventional Branch 1.0.0, so nothing was pushed. "
        "Rename the local branch to a conventional name with git branch -m <old> <new> and push it under that name, or, for a <src>:<dst> refspec, push to a conventional <dst>. "
        + NAMING,
        file=stderr,
    )
    return 1


def main(stdin, stdout, stderr, env_file=None):
    """Read the Claude Code hook's input from stdin and return Claude Code's exit code.

    At SessionStart, register this script as git's pre-push hook in env_file.
    A Bash call that creates or renames a branch with a name that isn't Conventional Branch gets a reason on stderr and 2, which blocks it;
    anything else gets 0.
    """
    hook_input = json.load(stdin)
    if hook_input.get("hook_event_name") == "SessionStart":
        register(env_file, stdout)
        return 0
    unconventional = [name for name in new_branch_names(hook_input["tool_input"]["command"]) if not conventional(name)]
    if not unconventional:
        return 0
    print(f"Blocked: branch name {', '.join(unconventional)} does not follow Conventional Branch 1.0.0. {NAMING}", file=stderr)
    return 2


if __name__ == "__main__":
    # git runs this script as its pre-push hook with the argument pre-push, then the remote's name and URL; Claude Code runs it with no arguments
    sys.exit(pre_push(sys.stdin, sys.stderr) if sys.argv[1:2] == ["pre-push"] else main(sys.stdin.buffer, sys.stdout, sys.stderr, os.environ.get("CLAUDE_ENV_FILE")))
