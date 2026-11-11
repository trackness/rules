"""Tests for "One command per Bash call". Run from the repo root: uv run pytest"""
import io
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from .rule import chains, main

SCRIPT = Path(__file__).resolve().parent / "rule.py"


def tool_call(cmd):
    """A Bash tool call as Claude Code sends it to the hook on stdin."""
    return io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}))


@pytest.mark.parametrize("cmd", [
    pytest.param("cd /tmp && ls", id="and_chain"),
    pytest.param("ls; pwd", id="semicolon"),
    pytest.param("ls | wc -l", id="pipe"),
    pytest.param("ls\npwd", id="newline"),
    pytest.param("npm start & npm test", id="background_then_another_command"),
    pytest.param("bash -c 'cd /tmp && ls'", id="inside_bash_c"),
    pytest.param('sh -c "npm run build && npm test"', id="inside_sh_c_double_quoted"),
    pytest.param("bash -lc 'cd /tmp && ls'", id="inside_bash_with_combined_flags"),
    pytest.param("zsh -c 'cd /tmp && ls'", id="inside_zsh_c"),
    pytest.param("bash -l -c 'cd /tmp && ls'", id="inside_bash_c_after_an_option"),
    pytest.param("bash -o pipefail -c 'ls | wc -l'", id="inside_bash_c_after_an_option_with_a_value"),
    pytest.param("bash --login -c 'cd /tmp && ls'", id="inside_bash_c_after_a_long_option"),
    pytest.param("bash -cx 'cd /tmp && ls'", id="inside_bash_with_flags_after_c"),
    pytest.param("bash -c -- 'cd /tmp && ls'", id="inside_bash_c_after_end_of_options"),
    pytest.param("bash -c  'cd /tmp && ls'", id="inside_bash_c_after_two_spaces"),
    pytest.param('bash -c "cd $(git rev-parse \\\n  --show-toplevel) && make"', id="inside_bash_c_after_a_continued_line"),
    pytest.param("ssh deploy@web 'cd /srv/app && git pull'", id="inside_ssh_command"),
    pytest.param("ssh -p 2222 deploy@web 'cd /srv/app && git pull'", id="inside_ssh_command_with_options"),
    pytest.param("ssh -o 'StrictHostKeyChecking no' deploy@web 'cd /srv/app && git pull'", id="inside_ssh_command_after_a_quoted_option"),
    pytest.param("find . -name '*.py' -exec sh -c 'true' \\; -exec sh -c 'cd /tmp && ls' \\;", id="inside_a_second_sh_c"),
    pytest.param('eval "cd /tmp && ls"', id="inside_eval"),
    pytest.param("echo \"Branch: $(git branch | grep '*')\"", id="inside_substitution_in_double_quotes"),
    pytest.param("echo \"Last: $(git log -1 --format='%s (%h)' | cut -c1-50)\"", id="inside_substitution_with_quoted_parenthesis"),
    pytest.param('echo "Last: $(git log -1 --format="%s" | cut -c1-50)"', id="inside_substitution_with_nested_double_quotes"),
    pytest.param("echo \"Branch: `git branch | grep '*'`\"", id="inside_backticks_in_double_quotes"),
    pytest.param('echo "Total: $(grep -c foo $(git ls-files) | sort)"', id="inside_substitution_after_a_nested_substitution"),
    pytest.param('echo "$(echo $((1+2)); ls)"', id="inside_substitution_after_arithmetic"),
    pytest.param('echo "n: $( (ls) | wc -l)"', id="inside_substitution_after_a_subshell"),
    pytest.param('echo "$(date +\\%F)"; ls "dir"', id="after_a_substitution_holding_an_escape"),
    pytest.param("cat <<'EOF' > run.sh && chmod +x run.sh\necho hi\nEOF", id="on_heredoc_line"),
    pytest.param("cat > run.sh <<'EOF'\necho hi\nEOF\nbash run.sh", id="command_after_heredoc"),
    pytest.param("ssh deploy@web <<'EOF'\ncd /srv/app && git pull\nEOF", id="in_heredoc_fed_to_ssh"),
    pytest.param("bash <<'EOF'\ncd /tmp\nls\nEOF", id="in_heredoc_fed_to_a_shell"),
    pytest.param("sudo bash <<'EOF'\ncd /tmp\nls\nEOF", id="in_heredoc_fed_to_a_shell_after_sudo"),
    pytest.param("env FOO=1 bash <<'EOF'\ncd /tmp\nls\nEOF", id="in_heredoc_fed_to_a_shell_after_env"),
    pytest.param("bash <<<'a && b'", id="in_here_string_fed_to_a_shell"),
    pytest.param("cat <<EOF > notes.txt\nBranch: $(git branch | grep '*')\nEOF", id="inside_substitution_in_unquoted_heredoc"),
    pytest.param("cat <<EOF > notes.txt\nFiles: `ls; pwd`\nEOF", id="inside_backticks_in_unquoted_heredoc"),
    pytest.param("ls # don't\npwd # it's done", id="newline_between_comments_holding_apostrophes"),
    pytest.param("echo $#; pwd", id="after_a_hash_that_starts_no_comment"),
    pytest.param("echo `ls # the files`; pwd", id="after_a_comment_ended_by_a_backtick"),
])
def test_chains(cmd):
    assert chains(cmd)


@pytest.mark.parametrize("cmd", [
    pytest.param("ls -la /tmp", id="single_command"),
    pytest.param("ls > out.txt 2>&1", id="redirect_stderr_to_stdout"),
    pytest.param("npm run build &> build.log", id="redirect_both_streams"),
    pytest.param("npm start &", id="one_command_in_background"),
    pytest.param('git commit -m "fix: a; b"', id="separator_in_double_quotes"),
    pytest.param("rg 'foo|bar' src", id="separator_in_single_quotes"),
    pytest.param("find . -name x -exec rm {} \\;", id="escaped_separator"),
    pytest.param('echo "say \\"a; b\\""', id="escaped_quote_in_double_quotes"),
    pytest.param("ls \\\n  -la", id="line_continuation"),
    pytest.param("find . -name '*.py' -exec sh -c 'black \"$1\"' _ {} \\;", id="wrapper_running_one_command"),
    pytest.param("find scripts/publish -type f -exec grep -c 'a|b' {} +", id="exec_after_a_word_ending_in_sh"),
    pytest.param("bash -c 'echo \"$1\"' _ 'a; b'", id="argument_after_the_sh_c_string"),
    pytest.param("rg 'TODO|FIXME' src/evaluation", id="separator_in_quotes_before_a_word_holding_eval"),
    pytest.param("grep -E 'foo|bar' build.sh -c", id="separator_in_quotes_before_a_word_ending_in_sh"),
    pytest.param("node --eval 'const a = 1; console.log(a)'", id="separator_in_quotes_after_an_eval_option"),
    pytest.param("rg retrieval 'foo|bar'", id="separator_in_quotes_after_a_word_ending_in_eval"),
    pytest.param("find ~/.ssh -exec grep -l 'Host|Match' {} +", id="separator_in_quotes_after_the_ssh_folder"),
    pytest.param("ls -la # list them; then stop", id="separator_in_a_comment"),
    pytest.param('echo "a # b; c"', id="hash_and_separator_in_double_quotes"),
    pytest.param("echo $#", id="hash_after_a_dollar"),
    pytest.param("curl https://x.test/page#top", id="hash_inside_a_word"),
    pytest.param('git commit -m "docs: explain \\`make && make install\\`"', id="escaped_backticks_in_double_quotes"),
    pytest.param('git commit -m "Release $(date +%F)"', id="substitution_running_one_command"),
    pytest.param('echo "Total: $(grep -c foo $(git ls-files))"', id="nested_substitution_running_one_command"),
    pytest.param('echo "Total; $(echo $((1 + 2)))"', id="separator_in_double_quotes_beside_brackets_nested_two_deep"),
    pytest.param("./publish.sh <<'EOF'\nfirst\nsecond\nEOF", id="heredoc_fed_to_a_script_ending_in_sh"),
    pytest.param("cat > /etc/ssh/sshd_config <<'EOF'\nPort 22\nPermitRootLogin no\nEOF", id="heredoc_written_to_a_path_holding_ssh"),
    pytest.param("cat notes.sh <<< 'a; b'", id="here_string_fed_to_a_command_reading_a_sh_file"),
    pytest.param("cat <<-EOF > f.txt\n\tone\n\ttwo\n\tEOF", id="tab_stripping_heredoc"),
    pytest.param("cat <&3", id="input_from_a_file_descriptor"),
    pytest.param("cat <<'EOF' > notes.txt\nBranch: $(git branch | grep '*')\nEOF", id="substitution_in_quoted_heredoc"),
    pytest.param("cat <<EOF > notes.txt\nReleased $(date +%F)\nEOF", id="substitution_in_unquoted_heredoc_running_one_command"),
    pytest.param(
        "git commit -m \"$(cat <<'EOF'\n"
        'fix(auth): handle "quoted" names; add tests\n'
        "\n"
        "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        "EOF\n"
        ')"',
        id="commit_message_heredoc",
    ),
])
def test_does_not_chain(cmd):
    assert not chains(cmd)


@pytest.mark.parametrize("cmd", [
    pytest.param('echo "' + "$(x)" * 22, id="unclosed_double_quote_after_substitutions"),
    pytest.param('echo "' + "$( (a))" * 22, id="unclosed_double_quote_after_bracketed_substitutions"),
    pytest.param('echo "' + "$((1+2)) " * 22 + '$(echo \\"x)"', id="arithmetic_before_an_escaped_quote"),
])
def test_long_command_is_checked_without_backtracking(cmd):
    """A pattern that can read the same text two ways backtracks exponentially: these take seconds there, twice as long per repeat."""
    start = time.perf_counter()
    assert not chains(cmd)
    assert time.perf_counter() - start < 0.5


def test_main_blocks_chained_command():
    assert main(tool_call("cd /tmp && ls"), io.StringIO()) == 2


def test_main_allows_single_command():
    assert main(tool_call("ls -la /tmp"), io.StringIO()) == 0


def test_main_block_gives_a_reason():
    stderr = io.StringIO()
    main(tool_call("cd /tmp && ls"), stderr)
    assert stderr.getvalue().strip() != ""


def test_the_script_run_as_a_hook_blocks_a_chained_command():
    """Claude Code runs the script by its path with the tool call on stdin, and takes exit code 2 as a block."""
    result = subprocess.run([SCRIPT], input=tool_call("cd /tmp && ls").getvalue(), capture_output=True, text=True)
    assert result.returncode == 2


def test_the_script_reads_utf_8_whatever_the_locale():
    """Claude Code sends UTF-8; PYTHONIOENCODING stands in for a locale whose encoding is not UTF-8, which Python 3.9 to 3.14 decode stdin with."""
    call = json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo café && ls"}}, ensure_ascii=False).encode()
    env = {"PATH": os.environ["PATH"], "PYTHONIOENCODING": "ascii:strict"}
    result = subprocess.run([SCRIPT], input=call, capture_output=True, env=env)
    assert result.returncode == 2
