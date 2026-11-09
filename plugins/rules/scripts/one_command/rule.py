#!/usr/bin/env python3
"""PreToolUse hook: allow one command per Bash call."""
import json
import re
import sys

SINGLE_QUOTED = r"'[^']*'"
DOLLAR_PAREN_BODY = r'''(?:'[^']*'|"[^"]*"|[^)'"])*'''  # a ")" inside quotes does not end the $(...)
# A lone "$" is matched only when no "(" follows, so each character has one reading and a long unclosed string cannot backtrack exponentially.
DOUBLE_QUOTED = rf'''"(?:\\.|\$\({DOLLAR_PAREN_BODY}\)|\$(?!\()|[^"\\$])*"'''
QUOTED_OR_ESCAPED = rf"\\.|{SINGLE_QUOTED}|{DOUBLE_QUOTED}"
SUBSTITUTION = rf"\$\((?P<dollar>{DOLLAR_PAREN_BODY})\)|`(?P<backtick>[^`]*)`"
HEREDOC = r"<<-?\s*(?P<quote>['\"]?)(?P<delimiter>\w+)(?P=quote)(?P<rest_of_line>[^\n]*)\n(?P<body>.*?)\n[ \t]*(?P=delimiter)[ \t]*(?=\n|$)"
# "\S*sh" is a command word ending in "sh": a shell, or ssh, which runs the heredoc as a script.
HEREDOC_FED_TO_A_SHELL = rf"^\s*\S*sh\b[^\n<]*{HEREDOC}"
# No word boundary before "sh", so bash, zsh, dash and any other *sh -c match; ssh's command comes after its options and host.
RUN_STRING = rf"(?:sh -\w*c|eval|ssh(?: [^\s'\"]+)+) (?P<quoted>{SINGLE_QUOTED}|{DOUBLE_QUOTED})"
# "&" chains only when another command follows it; in 2>&1 and &> it is a redirection, and a trailing "&" backgrounds a single command.
CHAIN_OPERATOR = r"[;|\n]|(?<![<>])&(?!>|\s*$)"


def substituted_commands(double_quoted):
    """The commands run by each $(...) or `...` inside a double-quoted string."""
    unescaped = re.sub(r"\\.", "", double_quoted, flags=re.S)  # an escaped \` or \$ is literal text
    return [match["dollar"] if match["dollar"] is not None else match["backtick"] for match in re.finditer(SUBSTITUTION, unescaped)]


def chains(cmd):
    """True if the shell command cmd runs more than one command."""
    if any(chains(heredoc["body"]) for heredoc in re.finditer(HEREDOC_FED_TO_A_SHELL, cmd, flags=re.S | re.M)):
        return True
    # Any other heredoc body is input to its command, not commands; strip() drops the newline a heredoc leaves before a closing ")".
    cmd = re.sub(HEREDOC, r"\g<rest_of_line>", cmd, flags=re.S).strip()
    run_string = re.search(RUN_STRING, cmd)
    if run_string and chains(run_string["quoted"][1:-1]):
        return True
    double_quoted = [match[0] for match in re.finditer(QUOTED_OR_ESCAPED, cmd, flags=re.S) if match[0].startswith('"')]
    outside_quotes = re.sub(QUOTED_OR_ESCAPED, "", cmd, flags=re.S)
    return bool(re.search(CHAIN_OPERATOR, outside_quotes)) or any(chains(c) for s in double_quoted for c in substituted_commands(s))


def main(stdin, stderr):
    """Read the Bash tool call from stdin and return Claude Code's exit code.

    A chained command gets a reason on stderr and 2, which blocks the call; anything else gets 0.
    """
    if not chains(json.load(stdin)["tool_input"]["command"]):
        return 0
    print(
        "Blocked: one command per Bash call. Find a single command or tool that does the whole job. "
        "Only if there isn't one, send the commands as separate calls.",
        file=stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.stdin, sys.stderr))
