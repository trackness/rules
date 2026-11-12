#!/usr/bin/env python3
"""PreToolUse hook: allow one command per Bash call."""
import json
import re
import sys

# A $'...' string ends at the first quote that no backslash escapes; a plain '...' string at the next quote.
SINGLE_QUOTED = r"\$'(?:\\.|[^'\\])*'|'[^']*'"
# A ")" that is quoted, escaped or closes a "(" does not end a $(...). Each of those starts with a character that plain text excludes,
# so each character has one reading and a long unclosed string cannot backtrack exponentially.
ESCAPED_OR_QUOTED = r'''\\.|'[^']*'|"[^"]*"'''
# shortcut: brackets nest two deep in a $(...); a third "(" is read as text, so the $(...) ends one ")" early and its rest goes unchecked; add a level if that is seen.
INNERMOST_BRACKETS = rf'''\((?:{ESCAPED_OR_QUOTED}|[^)\\'"])*\)'''
BRACKETS = rf'''\((?:{ESCAPED_OR_QUOTED}|{INNERMOST_BRACKETS}|[^()\\'"])*\)'''
DOLLAR_PAREN_BODY = rf'''(?:{ESCAPED_OR_QUOTED}|{BRACKETS}|[^()\\'"])*'''
# A lone "$" is matched only when no "(" follows, for the same one reading.
DOUBLE_QUOTED = rf'''"(?:\\.|\$\({DOLLAR_PAREN_BODY}\)|\$(?!\()|[^"\\$])*"'''
# A comment starts with a "#" that begins a word and runs to the end of the line, or to a backtick that closes a `...` around it.
COMMENT = r"(?:^|(?<=\s))#[^\n`]*"
QUOTED_OR_ESCAPED = rf"\\.|{SINGLE_QUOTED}|{DOUBLE_QUOTED}|{COMMENT}"
SUBSTITUTION = rf"\$\((?P<dollar>{DOLLAR_PAREN_BODY})\)|`(?P<backtick>[^`]*)`"
# A backslash before the delimiter quotes it as quote marks around it do; the body, with its last line break, may be empty.
HEREDOC = r"<<-?\s*(?P<quote>\\?(?P<mark>['\"]?))(?P<delimiter>[\w.-]+)(?P=mark)(?P<rest_of_line>[^\n]*)\n(?P<body>(?:.*?\n)??)[ \t]*(?P=delimiter)[ \t]*(?=\n|$)"
# A shell, or ssh, as a whole word anywhere (after sudo or env too), with or without its path: it runs a heredoc or here-string as a script.
SHELL = r"(?:^|\s)(?:\S*/)?(?:ba|z|da|k|c|tc|fi|s)?sh(?=[\s<])"
HEREDOC_FED_TO_A_SHELL = rf"{SHELL}[^\n<]*{HEREDOC}"
# No word boundary before "sh", so bash, zsh, dash and any other *sh -c match, after other options such as -o pipefail
# (find's -exec is not one, so "publish -exec grep -c" is not read as a shell); ssh's command comes after its options and host.
# eval and ssh are whole words, not part of --eval, retrieval or ~/.ssh.
RUN_STRING = (
    rf"(?:(?:sh(?: +-(?!exec )[^\s'\"]*(?: +[a-z]+)?)*? +-\w*c\w*(?: +--)?|(?<![\w.-])eval|(?<![\w.-])ssh(?: [^\s'\"]+)+) +|{SHELL}[^\n<]*<<< *)"
    rf"(?P<quoted>{SINGLE_QUOTED}|{DOUBLE_QUOTED})"
)
# shortcut: ssh as an argument (rsync -e ssh) also gets every quoted string checked, so a quoted separator there is blocked; read ssh's own
# arguments if that blocks real commands.
SSH_WORD = r"(?:^|[\s/])ssh "
# A command that starts with eval or ssh joins its arguments into one command line that a shell reads again,
# so a separator kept from this shell by quotes or a backslash chains there.
REREAD = r"(?:\S*/)?(?:eval|ssh) "
# "&" chains only when another command follows it; in 2>&1 and &> it is a redirection, and a trailing "&" backgrounds a single command.
CHAIN_OPERATOR = r"[;|\n]|(?<![<>])&(?!>|\s*$)"
# $((...)) is arithmetic, where | and & are operators, only when its own brackets, nested once at most, close on "))":
# $((a) | (b)) runs two subshells. Without $( or ` it runs no command, and without quotes, which can hide a ")" from bash.
ARITHMETIC = r"""\$\(\((?:[^()$`'"]|\$(?!\()|\([^()$`'"]*\))*\)\)"""


def substituted_commands(double_quoted):
    """The commands run by each $(...) or `...` inside a double-quoted string."""
    unescaped = re.sub(ARITHMETIC, "", re.sub(r"\\.", "", double_quoted, flags=re.S))  # an escaped \` or \$ is literal text
    return [match["dollar"] if match["dollar"] is not None else match["backtick"] for match in re.finditer(SUBSTITUTION, unescaped)]


def chains(cmd):
    """True if the shell command cmd runs more than one command."""
    if any(chains(heredoc["body"]) for heredoc in re.finditer(HEREDOC_FED_TO_A_SHELL, cmd, flags=re.S | re.M)):
        return True
    # An unquoted heredoc's body is expanded, so its $(...) and `...` run as commands.
    if any(chains(c) for heredoc in re.finditer(HEREDOC, cmd, flags=re.S) if not heredoc["quote"] for c in substituted_commands(heredoc["body"])):
        return True
    # Any other heredoc body is input to its command, not commands; strip() drops the newline a heredoc leaves before a closing ")".
    # shortcut: a << inside quotes, as in echo '<<EOF', is read as a heredoc too, so the lines after it up to a line EOF go unchecked; skip quoted text first if Claude writes that.
    cmd = re.sub(HEREDOC, r"\g<rest_of_line>", cmd, flags=re.S).strip()
    if any(chains(run_string["quoted"].removeprefix("$")[1:-1]) for run_string in re.finditer(RUN_STRING, cmd, flags=re.S)):
        return True
    matches = [match[0] for match in re.finditer(QUOTED_OR_ESCAPED, cmd, flags=re.S)]
    quoted = [m.removeprefix("$") for m in matches if m[0] in "'\"$"]
    outside_quotes = re.sub(ARITHMETIC, "", re.sub(QUOTED_OR_ESCAPED, "", cmd, flags=re.S))
    reread = re.match(REREAD, cmd)
    if reread and any(m in ("\\;", "\\|", "\\&") for m in matches):
        return True
    # ssh joins its arguments into one remote command, and a quoted option before the host hides that command from RUN_STRING.
    if (reread or re.search(SSH_WORD, outside_quotes)) and any(chains(q[1:-1]) for q in quoted):
        return True
    double_quoted = [q for q in quoted if q.startswith('"')]
    return bool(re.search(CHAIN_OPERATOR, outside_quotes)) or any(chains(c) for s in double_quoted for c in substituted_commands(s))


def main(stdin, stderr):
    """Read the Bash tool call from stdin and return Claude Code's exit code.

    A chained command gets a reason on stderr and 2, which blocks the call; anything else gets 0.
    """
    if not chains(json.load(stdin)["tool_input"]["command"]):
        return 0
    print(
        "Blocked: one command per Bash or Monitor call. Find a single command or tool that does the whole job. "
        "Only if there isn't one, send the commands as separate calls.",
        file=stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.stdin.buffer, sys.stderr))
