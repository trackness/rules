#!/usr/bin/env python3
"""Allow only Conventional Commits messages in the commits Claude makes."""
import os
import re
import shlex
import sys
from pathlib import Path

HEADER = r"(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore)(?:\([^()\s]+\))?!?: \S"


def conventional(message):
    """True if the commit message follows Conventional Commits: a valid header, then a blank line before any body."""
    header, _, rest = message.partition("\n")
    return bool(re.match(HEADER, header)) and not rest.split("\n")[0].strip()


def register(env_file, stderr):
    """Make git run this script as the commit-msg hook in the Bash commands of the Claude Code session that owns env_file."""
    if not env_file:
        print("The Conventional Commits check is not active: Claude Code gave this hook no CLAUDE_ENV_FILE to register it in.", file=stderr)
        return
    command = shlex.quote(str(Path(__file__).resolve()))  # git runs the command through a shell
    # shortcut: replaces any GIT_CONFIG_COUNT already set in the session; offset the keys if something else sets it
    with open(env_file, "a") as session_env:
        session_env.write(
            "export GIT_CONFIG_COUNT=2\n"
            "export GIT_CONFIG_KEY_0=hook.conventional-commits.event\n"
            "export GIT_CONFIG_VALUE_0=commit-msg\n"
            "export GIT_CONFIG_KEY_1=hook.conventional-commits.command\n"
            f"export GIT_CONFIG_VALUE_1={shlex.quote(command)}\n"
        )


def main(message_file, stderr):
    """Check the message git passes to a commit-msg hook and return git's exit code: 1 rejects the commit, with a reason on stderr."""
    if conventional(Path(message_file).read_text()):
        return 0
    print(
        "Rejected: the commit message does not follow Conventional Commits. Start it with <type>[optional scope][!]: <description>, "
        "with type feat, fix, docs, style, refactor, perf, test, build, ci or chore, and leave a blank line before any body.",
        file=stderr,
    )
    return 1


if __name__ == "__main__":
    # git runs this script with the message file; Claude Code's SessionStart runs it with no arguments
    sys.exit(main(sys.argv[1], sys.stderr) if len(sys.argv) > 1 else register(os.environ.get("CLAUDE_ENV_FILE"), sys.stderr))
