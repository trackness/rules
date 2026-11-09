#!/usr/bin/env python3
"""PreToolUse hook: allow Write only for files that do not exist yet."""
import json
import sys
from pathlib import Path


def main(stdin, stderr):
    """Read the Write tool call from stdin and return Claude Code's exit code.

    A Write to a file that already exists gets a reason on stderr and 2, which blocks the call; anything else gets 0.
    """
    if not Path(json.load(stdin)["tool_input"]["file_path"]).exists():
        return 0
    print(
        "Blocked: Write is only for new files, and this one already exists. "
        "Change it with Edit, or NotebookEdit for a notebook.",
        file=stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.stdin, sys.stderr))
