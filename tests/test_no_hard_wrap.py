"""Tests for scripts/no_hard_wrap.py. Run from the repo root: uv run pytest"""
import io
import json

import pytest

from scripts.no_hard_wrap import hard_wraps, main

WRAPPED = "# Title\n\nThis paragraph runs on\nto a second line.\n"


def write_call(file_path, content):
    """A Write tool call as Claude Code sends it to the hook on stdin."""
    return io.StringIO(json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(file_path), "content": content}}))


def edit_call(file_path, old_string, new_string):
    """An Edit tool call as Claude Code sends it to the hook on stdin."""
    tool_input = {"file_path": str(file_path), "old_string": old_string, "new_string": new_string, "replace_all": False}
    return io.StringIO(json.dumps({"tool_name": "Edit", "tool_input": tool_input}))


@pytest.mark.parametrize("text", [
    pytest.param("This paragraph runs on\nto a second line.\n", id="paragraph_runs_on"),
    pytest.param("- This list item runs on\n  to a second line.\n", id="list_item_runs_on"),
    pytest.param("---\r\nname: rules\r\n---\r\n\r\nThis paragraph runs on\r\nto a second line.\r\n", id="paragraph_runs_on_after_front_matter_with_crlf"),
])
def test_hard_wraps(text):
    assert hard_wraps(text)


@pytest.mark.parametrize("text", [
    pytest.param("One paragraph on one line.\n\nAnother paragraph on one line.\n", id="paragraphs_separated_by_blank_line"),
    pytest.param("- one item\n- another item\n", id="list_items"),
    pytest.param("1. First step.\n2. Second step.\n", id="numbered_list_items"),
    pytest.param("1) First step.\n2) Second step.\n", id="parenthesis_numbered_list_items"),
    pytest.param("* one item\n* another item\n", id="asterisk_list_items"),
    pytest.param("+ one item\n+ another item\n", id="plus_list_items"),
    pytest.param("## Install\nRun the installer.\n", id="paragraph_right_under_heading"),
    pytest.param("Run the installer.\n## Usage\n", id="heading_right_under_paragraph"),
    pytest.param("| Rule | Script |\n|---|---|\n| One command | `one_command.py` |\n", id="table_rows"),
    pytest.param("Run:\n\n```sh\nuv sync\nuv run pytest\n```\n", id="fenced_code"),
    pytest.param("Run:\n\n~~~sh\nuv sync\nuv run pytest\n~~~\n", id="tilde_fenced_code"),
    pytest.param("Fence the commands with tildes:\n\n```markdown\n~~~sh\nuv sync\nuv run pytest\n~~~\n```\n", id="backtick_fence_showing_tilde_fence"),
    pytest.param("Fence the commands like this:\n\n````markdown\n```sh\nuv sync\nuv run pytest\n```\n````\n", id="longer_fence_showing_shorter_fence"),
    pytest.param("---\nname: rules\ndescription: Hooks that enforce rules.\n---\n\nThe body.\n", id="front_matter"),
    pytest.param("---\r\nname: rules\r\ndescription: Hooks that enforce rules.\r\n---\r\n\r\nThe body.\r\n", id="front_matter_with_crlf"),
    pytest.param('<p align="center">\n  <img src="logo.png" alt="Logo">\n</p>\n', id="html_block"),
    pytest.param("<!-- markdownlint-disable -->\nText right under a comment.\n", id="paragraph_right_under_html_comment"),
    pytest.param("> [!NOTE]\n> The hooks run with the python3 on the PATH.\n", id="github_alert"),
    pytest.param("[docs]: https://example.com/docs\n[api]: https://example.com/api\n", id="link_reference_definitions"),
])
def test_no_hard_wraps(text):
    assert not hard_wraps(text)


def test_main_blocks_write_of_wrapped_markdown(tmp_path):
    assert main(write_call(tmp_path / "README.md", WRAPPED), io.StringIO()) == 2


def test_main_blocks_write_of_wrapped_markdown_with_long_extension(tmp_path):
    assert main(write_call(tmp_path / "README.markdown", WRAPPED), io.StringIO()) == 2


def test_main_block_gives_a_reason(tmp_path):
    stderr = io.StringIO()
    main(write_call(tmp_path / "README.md", WRAPPED), stderr)
    assert stderr.getvalue().strip() != ""


def test_main_allows_write_of_unwrapped_markdown(tmp_path):
    assert main(write_call(tmp_path / "README.md", "# Title\n\nThis paragraph is on one line.\n"), io.StringIO()) == 0


def test_main_allows_write_of_file_that_is_not_markdown(tmp_path):
    assert main(write_call(tmp_path / "hook.py", "import json\nimport sys\n"), io.StringIO()) == 0


def test_main_allows_write_of_mdx_with_consecutive_imports(tmp_path):
    page = 'import Chart from "./chart"\nimport Tabs from "./tabs"\n\n# Sales\n\n<Tabs>\n  <Chart data={sales} />\n</Tabs>\n'
    assert main(write_call(tmp_path / "sales.mdx", page), io.StringIO()) == 0


def test_main_blocks_edit_that_wraps_a_paragraph(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Title\n\nThis paragraph is on one line.\n")
    assert main(edit_call(readme, "on one line.", "on one line, until\nthis edit wraps it."), io.StringIO()) == 2


def test_main_blocks_edit_that_creates_a_wrapped_file(tmp_path):
    assert main(edit_call(tmp_path / "NOTES.md", "", WRAPPED), io.StringIO()) == 2


def test_main_allows_edit_that_adds_a_line_inside_a_code_fence(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("Run:\n\n```sh\nuv sync\n```\n")
    assert main(edit_call(readme, "uv sync", "uv sync\nuv run pytest"), io.StringIO()) == 0


def test_main_allows_edit_inside_a_paragraph_someone_else_wrapped(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("This paragraph was wrapped\nby someone else.\n")
    assert main(edit_call(readme, "someone else", "another author"), io.StringIO()) == 0


def test_main_leaves_edit_with_missing_old_string_to_edit(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("This paragraph was wrapped\nby someone else.\n")
    assert main(edit_call(readme, "text that is not in the file", "a replacement that is long and on one line"), io.StringIO()) == 0
