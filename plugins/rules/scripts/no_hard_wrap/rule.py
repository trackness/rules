#!/usr/bin/env python3
"""PreToolUse hook: block hard-wrapped lines in Markdown files."""
import json
import re
import sys
from pathlib import Path

LIST_ITEM = r"\s*(?:[-*+]|\d+[.)]) "
OTHER_BLOCK = r"\s*(?:#{1,6} |[|<>]|\[[^\]]+\]:|=+\s*$|(?:-\s*){3,}$|(?:\*\s*){3,}$|(?:_\s*){3,}$)"
FENCE = r"\s*(`{3,}|~{3,})"
STRAIGHT_QUOTES = str.maketrans("‘’“”", "''\"\"")


def loose(text):
    """The text as Edit compares it when an old_string is not in the file word for word: curly quotes made straight and \\uXXXX escapes of non-ASCII characters decoded."""
    # shortcut: unlike Edit, this keeps escapes of ASCII characters and does not join an emoji's two escapes into one character; mirror Edit there too if wraps get through that way
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)) if int(m[1], 16) >= 0x80 else m[0], text.translate(STRAIGHT_QUOTES))


def hard_wraps(text):
    """The offsets in the Markdown text of each line break that hard-wraps a paragraph or list item."""
    breaks = []
    offset = -1  # of the line break before the current line
    fence = ""  # the backticks or tildes that opened the code block the current line is in, if any
    fence_indent = 0  # how far the line that opened that code block is indented
    continuable = False  # whether the previous line is text that the current line could continue
    front_matter = text.startswith(("---\n", "---\r\n"))
    comment = False  # whether the current line is inside an HTML comment that an earlier line opened
    was_blank, indented_code = True, False
    for number, line in enumerate(text.split("\n")):
        blank = not line.strip()
        # as in CommonMark, an indented line after a blank line starts a code block, which goes on while lines stay indented
        # shortcut: a list item's paragraph indented four spaces after a blank line is read as code, so its wraps pass; track list nesting if they get through
        indented_code = not blank and line.startswith(("    ", "\t")) and (was_blank or indented_code)
        was_blank = blank
        if front_matter:
            front_matter = number == 0 or line.rstrip("\r") != "---"
            continuable = False
        elif not fence and (comment or re.match(r" {0,3}<!--", line)):
            # as in CommonMark, a comment block starts at a line that begins with <!-- and ends at the first line holding -->
            comment = "-->" not in line
            continuable = False
        elif (match := re.match(FENCE, line)) and match[1].startswith(fence) and not (fence and (line[match.end():].strip() or match.start(1) > fence_indent + 3)):
            # as in CommonMark, a fence closes only at a line holding nothing but a run of its character at least as long, indented at most three spaces more, so a fence can show other fences
            fence, fence_indent = ("", 0) if fence else (match[1], match.start(1))
            continuable = False
        elif fence or blank or indented_code:
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
    wraps_added = False  # whether an Edit adds a wrap outside its new_string, such as by turning a heading into text
    if "content" in tool_input:
        text, start, end = tool_input["content"], 0, len(tool_input["content"])
    else:
        path = Path(tool_input["file_path"])
        before = path.read_text(encoding="utf-8") if path.exists() else ""  # Edit with an empty old_string creates the file
        old, new = tool_input["old_string"], tool_input["new_string"]
        if old not in before:  # Edit then matches through curly quotes and \uXXXX escapes, so compare the way it does
            before, old, new = loose(before), loose(old), loose(new)
        if not new and not old.endswith("\n") and old + "\n" in before:
            old += "\n"  # as Edit does: with an empty new_string, the line break after old_string goes too
        start = before.find(old)
        if start == -1:
            return 0  # Edit itself rejects an old_string it cannot find, even loosely
        text, end = before[:start] + new + before[start + len(old):], start + len(new)
        after = before.replace(old, new, -1 if tool_input.get("replace_all") else 1)
        wraps_added = len(hard_wraps(after)) > len(hard_wraps(before))
    if not wraps_added and not any(start <= offset < end for offset in hard_wraps(text)):
        return 0
    print(
        "Blocked: hard-wrapped Markdown. Write each paragraph and list item as one line; "
        "break lines only between blocks, list items and table rows, and inside code blocks.",
        file=stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.stdin.buffer, sys.stderr))
