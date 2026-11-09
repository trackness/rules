#!/usr/bin/env python3
"""PreToolUse hook: block hard-wrapped lines in Markdown files."""
import json
import re
import sys
from pathlib import Path

LIST_ITEM = r"\s*(?:[-*+]|\d+[.)]) "
OTHER_BLOCK = r"\s*(?:#{1,6} |[|<>]|\[[^\]]+\]:)"
FENCE = r"\s*(?:```|~~~)"


def hard_wraps(text):
    """The offsets in the Markdown text of each line break that hard-wraps a paragraph or list item."""
    breaks = []
    offset = -1  # of the line break before the current line
    in_fence = False
    continuable = False  # whether the previous line is text that the current line could continue
    front_matter = text.startswith(("---\n", "---\r\n"))
    for number, line in enumerate(text.split("\n")):
        if front_matter:
            front_matter = number == 0 or line.rstrip("\r") != "---"
            continuable = False
        elif re.match(FENCE, line):
            in_fence = not in_fence
            continuable = False
        elif in_fence or not line.strip():
            continuable = False
        else:
            if continuable and not re.match(LIST_ITEM, line) and not re.match(OTHER_BLOCK, line):
                breaks.append(offset)
            continuable = not re.match(OTHER_BLOCK, line)
        offset += len(line) + 1
    return breaks


def main(stdin, stderr):
    """Read the Write or Edit tool call from stdin and return Claude Code's exit code.

    A call that hard-wraps Markdown it writes gets a reason on stderr and 2, which blocks it; anything else gets 0.
    """
    tool_input = json.load(stdin)["tool_input"]
    if not tool_input["file_path"].endswith((".md", ".markdown")):
        return 0
    if "content" in tool_input:
        text, start, end = tool_input["content"], 0, len(tool_input["content"])
    else:
        path = Path(tool_input["file_path"])
        before = path.read_text() if path.exists() else ""  # Edit with an empty old_string creates the file
        # shortcut: with replace_all only the first replacement is checked, check each one if wraps get through that way
        start = before.find(tool_input["old_string"])
        if start == -1:
            return 0  # Edit itself rejects an old_string that isn't in the file
        text = before[:start] + tool_input["new_string"] + before[start + len(tool_input["old_string"]):]
        end = start + len(tool_input["new_string"])
    if not any(start <= offset < end for offset in hard_wraps(text)):
        return 0
    print(
        "Blocked: hard-wrapped Markdown. Write each paragraph and list item as one line; "
        "break lines only between blocks, list items and table rows, and inside code blocks.",
        file=stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.stdin, sys.stderr))
