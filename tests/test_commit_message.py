"""Tests for scripts/commit_message.py. Run from the repo root: uv run pytest"""
import io
import json

import pytest

from scripts.commit_message import commit_message, conventional, main


def tool_call(cmd):
    """A Bash tool call as Claude Code sends it to the hook on stdin."""
    return io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}))


@pytest.mark.parametrize("message", [
    pytest.param("Add login page", id="no_type"),
    pytest.param("feature: add login page", id="type_not_in_the_list"),
    pytest.param("feat: ", id="no_description"),
    pytest.param("fix: handle empty input\nThe body starts right under the header.", id="body_without_blank_line"),
])
def test_not_conventional(message):
    assert not conventional(message)


@pytest.mark.parametrize("message", [
    pytest.param("feat: add login page", id="type_and_description"),
    pytest.param("feat(auth): add passkey login", id="scope"),
    pytest.param("feat(api)!: remove legacy endpoint", id="breaking_change"),
    pytest.param("fix: handle empty input\n\nAn empty form no longer crashes the page.\n\nRefs: #12", id="body_and_footer"),
])
def test_conventional(message):
    assert conventional(message)


@pytest.mark.parametrize("cmd, message", [
    pytest.param('git commit -m "feat: add login page"', "feat: add login page", id="m"),
    pytest.param('git commit -m "feat: add login page" -m "With a form."', "feat: add login page\n\nWith a form.", id="m_twice"),
    pytest.param('git commit -am "fix: handle empty input"', "fix: handle empty input", id="am"),
    pytest.param('git commit --message="fix: handle empty input"', "fix: handle empty input", id="long_option"),
    pytest.param('git commit --message "fix: handle empty input"', "fix: handle empty input", id="long_option_separate_value"),
    pytest.param(
        "git commit -m \"$(cat <<'EOF'\n"
        "fix: don't crash on empty input\n"
        "\n"
        "An empty form no longer crashes the page.\n"
        "EOF\n"
        ')"',
        "fix: don't crash on empty input\n\nAn empty form no longer crashes the page.",
        id="heredoc",
    ),
    pytest.param('git merge -m "Merge the login branch" feature/add-login', None, id="not_commit"),
    pytest.param('git -C /repo commit -m "Add login page"', "Add login page", id="git_directory_option"),
    pytest.param('git -c commit.gpgsign=false commit -m "Add login page"', "Add login page", id="git_config_option"),
    pytest.param("cat > notes.txt <<'EOF'\nDon't stop.\nEOF", None, id="unbalanced_quote_in_heredoc"),
])
def test_commit_message(cmd, message):
    assert commit_message(cmd) == message


def test_main_blocks_unconventional_commit_message():
    assert main(tool_call('git commit -m "Add login page"'), io.StringIO()) == 2


def test_main_allows_conventional_commit_message():
    assert main(tool_call('git commit -m "feat: add login page"'), io.StringIO()) == 0


def test_main_allows_command_without_commit_message():
    assert main(tool_call("ls -la"), io.StringIO()) == 0


def test_main_block_gives_a_reason():
    stderr = io.StringIO()
    main(tool_call('git commit -m "Add login page"'), stderr)
    assert stderr.getvalue().strip() != ""
