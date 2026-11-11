#!/usr/bin/env python3
"""Allow only Conventional Commits messages in the commits Claude makes."""
import os
import re
import sys
from pathlib import Path

# Run by its path, a script can import only from its own folder, and git_hook.py is in the scripts folder above it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import git_hook

HEADER = r"(?:(?:fixup|squash|amend)! )*(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore)(?:\([^()\s]+\))?!?: \S"


def conventional(message):
    """True if the commit message follows Conventional Commits: a valid header, which may follow git's fixup!, squash! or amend! prefixes, then a blank line before any body."""
    header, _, rest = message.partition("\n")
    return bool(re.match(HEADER, header)) and not rest.split("\n")[0].strip()


def register(env_file, stdout):
    """Make git run this script as the commit-msg hook in the Bash commands of the Claude Code session that owns env_file."""
    git_hook.register(env_file, stdout, "conventional-commits", "commit-msg", [Path(__file__).resolve()], "The Conventional Commits check")


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
