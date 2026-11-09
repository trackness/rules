#!/usr/bin/env python3
"""Allow only Conventional Commits messages in the commits Claude makes."""
import os
import re
import shlex
import sys
from pathlib import Path

HEADER = r"(?:(?:fixup|squash|amend)! )*(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore)(?:\([^()\s]+\))?!?: \S"


def conventional(message):
    """True if the commit message follows Conventional Commits: a valid header, which may follow git's fixup!, squash! or amend! prefixes, then a blank line before any body."""
    header, _, rest = message.partition("\n")
    return bool(re.match(HEADER, header)) and not rest.split("\n")[0].strip()


def register(env_file, stdout):
    """Make git run this script as the commit-msg hook in the Bash commands of the Claude Code session that owns env_file."""
    if not env_file:
        # Claude Code adds a SessionStart hook's stdout to Claude's context; Claude never sees its stderr.
        print("The Conventional Commits check is not active: Claude Code gave this hook no CLAUDE_ENV_FILE to register it in.", file=stdout)
        return
    command = shlex.quote(str(Path(__file__).resolve()))  # git runs the command through a shell
    # Each entry goes after those already counted, so other rules' and the user's GIT_CONFIG_* entries stay. The command comes first:
    # git ignores a command with no event, but aborts on an event with no command, as a shell that stops partway through would leave.
    with open(env_file, "a") as session_env:
        session_env.write(
            f"export GIT_CONFIG_KEY_${{GIT_CONFIG_COUNT:-0}}=hook.conventional-commits.command GIT_CONFIG_VALUE_${{GIT_CONFIG_COUNT:-0}}={shlex.quote(command)}\n"
            "export GIT_CONFIG_COUNT=$((${GIT_CONFIG_COUNT:-0} + 1))\n"
            "export GIT_CONFIG_KEY_${GIT_CONFIG_COUNT}=hook.conventional-commits.event GIT_CONFIG_VALUE_${GIT_CONFIG_COUNT}=commit-msg\n"
            "export GIT_CONFIG_COUNT=$((GIT_CONFIG_COUNT + 1))\n"
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
    sys.exit(main(sys.argv[1], sys.stderr) if len(sys.argv) > 1 else register(os.environ.get("CLAUDE_ENV_FILE"), sys.stdout))
