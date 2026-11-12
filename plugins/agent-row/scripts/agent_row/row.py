#!/usr/bin/env python3
"""subagentStatusLine command: draw each background agent's row with its model and spawn description."""
import json
import re
import sys
import time
import unicodedata

GAP = "  "  # between columns, because a description or an activity has single spaces of its own
# The Agent tool asks for a description of 3 to 5 words, which 32 columns holds whole; a longer one is cut here so that
# it never crowds out the activity, the part of the row that changes: a 120-column panel still leaves the activity some 30.
DESCRIPTION_LIMIT = 32
# Likewise for the name and the model, whose widths are not bounded by anything the user sees: one long id must not empty every row's activity.
NAME_LIMIT = 24
MODEL_LIMIT = 16


def clean(text):
    """The text as Claude Code cleans it for its own row: control characters dropped, line breaks and runs of whitespace one space."""
    return " ".join(re.sub(r"[\x00-\x08\x0e-\x1f\x7f-\x9f]", "", text).split())


def short_model(model):
    """The model's id without its provider's prefix, `claude-`, its snapshot's date (`-` or Vertex's `@`) or Bedrock's version, its version's numbers joined by dots.

    `claude-opus-4-6`, `us.anthropic.claude-opus-4-6-v1` and `claude-haiku-4-5@20251001` are `opus-4.6` and `haiku-4.5`.
    """
    name = re.sub(r"^.*claude-|(?:[-@]\d{8})?(?:-v\d+(?::\d+)?)?$", "", model)
    return re.sub(r"(?<=\d)-(?=\d)", ".", name)


def running_time(milliseconds):
    """The running time as Claude Code writes it, such as 5s, 1m 5s, 1h 2m 5s or 1d 1h 1m."""
    if milliseconds < 60_000:
        return f"{milliseconds // 1000}s"
    # Claude Code rounds the seconds down under a minute but half up from one, and the row matches it.
    minutes, seconds = divmod((milliseconds + 500) // 1000, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"


def token_count(count):
    """The count of tokens as Claude Code writes it: 850, 12.3k or 1.2m."""
    if count < 1000:
        return str(count)
    # Whole-number rounding, half up, as Claude Code does; 999,950 and above round up to 1.0m.
    if count < 999_950:
        return f"{(count + 50) // 100 / 10:.1f}k"
    return f"{(count + 50_000) // 100_000 / 10:.1f}m"


def display_width(text):
    """The columns a terminal draws the text across: two for each East Asian wide or fullwidth character, one for any other."""
    return sum(2 if unicodedata.east_asian_width(character) in ("W", "F") else 1 for character in text)


def pad(text, width):
    """The text with spaces after it to fill width columns."""
    return text + " " * (width - display_width(text))


def clip(text, width):
    """The text cut to width columns, with … where it is cut."""
    if display_width(text) <= width:
        return text
    kept, used = "", display_width("…")
    for character in text:
        used += display_width(character)
        if used > width:
            break
        kept += character
    return kept + "…"


def fixed_cells(task):
    """The agent's cells in the columns that line up across the rows: its type or name, its model and its description."""
    return [
        clip(clean(task.get("name") or task["agentType"]), NAME_LIMIT),
        clip(clean(short_model(task.get("model", ""))), MODEL_LIMIT),  # absent only from a task that Claude Code restored from disk
        clip(clean(task["description"]), DESCRIPTION_LIMIT),
    ]


def time_and_tokens(task, now):
    """The right of the agent's row: its running time, or its status once it has stopped, then its tokens, such as 1m 5s · ↓ 12.3k tokens."""
    # Claude Code sends no end time, so the time since a stopped agent's start would go on counting past its end.
    written = running_time(max(0, now - task["startTime"])) if task["status"] == "running" else task["status"]
    if task["tokenCount"]:
        # Always ↓: Claude Code's own row shows ↑ until the agent has had some activity, which it does not send.
        written += f" · ↓ {token_count(task['tokenCount'])} tokens"
    return written


def activity(task):
    """The agent's latest progress summary, or, until it has one, a note that it has none, so that the column never looks lost."""
    # Until the agent has a progress summary, Claude Code sends its description as its label.
    label = clean(task["label"])
    if label != clean(task["description"]):
        return label
    return "no summary yet" if task["status"] == "running" else "no summary"


def body(task, widths, columns, now):
    """The body of the agent's row, columns wide: its fixed cells padded to their columns' widths, its activity, then its time and tokens.

    What does not fit is cut from the left part, so the time and tokens are never lost; a panel too narrow for even those gets None.
    """
    right = time_and_tokens(task, now)
    room = columns - display_width(right) - len(GAP)
    if room < 1:
        return None
    padded = [pad(cell, width) for cell, width in zip(fixed_cells(task), widths)]
    # Without trailing whitespace, so that a … marks only text that was cut.
    left = clip(GAP.join(padded + [activity(task)]).rstrip(), room)
    return pad(left, columns - display_width(right)) + right


def main(stdin, stdout, now):
    """Read the panel of background agents from stdin and print the body of each agent's row to stdout, running or stopped.

    now is the time in milliseconds since the epoch.
    """
    panel = json.load(stdin)
    widths = [max(map(display_width, column)) for column in zip(*map(fixed_cells, panel["tasks"]))]
    contents = {task["id"]: body(task, widths, panel["columns"], now) for task in panel["tasks"]}
    # Claude Code draws its own row for a task given no line, which would not line up with these, so either every row or none.
    if None not in contents.values():
        for task_id, content in contents.items():
            print(json.dumps({"id": task_id, "content": content}), file=stdout)


if __name__ == "__main__":
    main(sys.stdin.buffer, sys.stdout, time.time_ns() // 1_000_000)
