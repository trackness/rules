"""Tests for scripts/one_command.py. Run from the repo root: uv run pytest"""
import io
import json

import pytest

from scripts.one_command import chains, main


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
    pytest.param("ssh deploy@web 'cd /srv/app && git pull'", id="inside_ssh_command"),
    pytest.param("ssh -p 2222 deploy@web 'cd /srv/app && git pull'", id="inside_ssh_command_with_options"),
    pytest.param('eval "cd /tmp && ls"', id="inside_eval"),
    pytest.param("echo \"Branch: $(git branch | grep '*')\"", id="inside_substitution_in_double_quotes"),
    pytest.param("echo \"Last: $(git log -1 --format='%s (%h)' | cut -c1-50)\"", id="inside_substitution_with_quoted_parenthesis"),
    pytest.param('echo "Last: $(git log -1 --format="%s" | cut -c1-50)"', id="inside_substitution_with_nested_double_quotes"),
    pytest.param("echo \"Branch: `git branch | grep '*'`\"", id="inside_backticks_in_double_quotes"),
    pytest.param("cat <<'EOF' > run.sh && chmod +x run.sh\necho hi\nEOF", id="on_heredoc_line"),
    pytest.param("cat > run.sh <<'EOF'\necho hi\nEOF\nbash run.sh", id="command_after_heredoc"),
    pytest.param("ssh deploy@web <<'EOF'\ncd /srv/app && git pull\nEOF", id="in_heredoc_fed_to_ssh"),
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
    pytest.param('git commit -m "docs: explain \\`make && make install\\`"', id="escaped_backticks_in_double_quotes"),
    pytest.param('git commit -m "Release $(date +%F)"', id="substitution_running_one_command"),
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


def test_main_blocks_chained_command():
    assert main(tool_call("cd /tmp && ls"), io.StringIO()) == 2


def test_main_allows_single_command():
    assert main(tool_call("ls -la /tmp"), io.StringIO()) == 0


def test_main_block_gives_a_reason():
    stderr = io.StringIO()
    main(tool_call("cd /tmp && ls"), stderr)
    assert stderr.getvalue().strip() != ""
