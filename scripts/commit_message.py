#!/usr/bin/env python3
"""PreToolUse hook: allow only Conventional Commits messages in git commit calls."""
import json
import re
import shlex
import sys

GIT_OPTIONS_WITH_VALUE = ("-c", "-C")
# shortcut: a message passed with -F or --file is not read; read the file if Claude starts committing that way
MESSAGE_OPTION = r"-[a-zA-Z]*m|--message"  # -m, or short flags combined with it such as -am
HEREDOC = r"\$\(cat <<-?\s*(['\"]?)(\w+)\1\n(?P<body>.*)\n\s*\2\s*\)"
HEADER = r"(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore)(?:\([^()\s]+\))?!?: \S"


def conventional(message):
    """True if the commit message follows Conventional Commits: a valid header, then a blank line before any body."""
    header, _, rest = message.partition("\n")
    return bool(re.match(HEADER, header)) and not rest.split("\n")[0].strip()


def commit_message(cmd):
    """The message the shell command cmd gives git commit, or None if it gives none."""
    try:
        words = shlex.split(cmd)
    except ValueError:  # an unbalanced quote, such as an apostrophe in a heredoc body, leaves no words to read
        return None
    if words[:1] != ["git"]:
        return None
    words = words[1:]
    while words and words[0].startswith("-"):
        words = words[2:] if words[0] in GIT_OPTIONS_WITH_VALUE else words[1:]
    if words[:1] != ["commit"]:
        return None
    paragraphs = []
    for i, word in enumerate(words):
        if re.fullmatch(MESSAGE_OPTION, word) and i + 1 < len(words):
            paragraphs.append(words[i + 1])
        elif word.startswith("--message="):
            paragraphs.append(word.removeprefix("--message="))
    return "\n\n".join(heredoc_body(paragraph) for paragraph in paragraphs) if paragraphs else None


def heredoc_body(text):
    """The body of a "$(cat <<'EOF' … EOF)" message, or the text itself."""
    heredoc = re.fullmatch(HEREDOC, text, flags=re.S)
    return heredoc["body"] if heredoc else text


def main(stdin, stderr):
    """Read the Bash tool call from stdin and return Claude Code's exit code.

    A git commit whose message isn't Conventional Commits gets a reason on stderr and 2, which blocks it; anything else gets 0.
    """
    message = commit_message(json.load(stdin)["tool_input"]["command"])
    if message is None or conventional(message):
        return 0
    print(
        "Blocked: the commit message does not follow Conventional Commits. Start it with <type>[optional scope][!]: <description>, "
        "with type feat, fix, docs, style, refactor, perf, test, build, ci or chore, and leave a blank line before any body.",
        file=stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.stdin, sys.stderr))
