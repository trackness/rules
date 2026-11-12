"""Tests for "No hard-wrapped Markdown". Run from the repo root: uv run pytest"""
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from .rule import hard_wraps, main

SCRIPT = Path(__file__).resolve().parent / "rule.py"
WRAPPED ="# Title\n\nThis paragraph runs on\nto a second line.\n"


def write_call(file_path, content):
    """A Write tool call as Claude Code sends it to the hook on stdin."""
    return io.StringIO(json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(file_path), "content": content}}, ensure_ascii=False))


def edit_call(file_path, old_string, new_string, replace_all=False):
    """An Edit tool call as Claude Code sends it to the hook on stdin."""
    tool_input = {"file_path": str(file_path), "old_string": old_string, "new_string": new_string, "replace_all": replace_all}
    return io.StringIO(json.dumps({"tool_name": "Edit", "tool_input": tool_input}, ensure_ascii=False))


@pytest.mark.parametrize("text", [
    pytest.param("This paragraph runs on\nto a second line.\n", id="paragraph_runs_on"),
    pytest.param("- This list item runs on\n  to a second line.\n", id="list_item_runs_on"),
    pytest.param("---\r\nname: rules\r\n---\r\n\r\nThis paragraph runs on\r\nto a second line.\r\n", id="paragraph_runs_on_after_front_matter_with_crlf"),
    pytest.param("This heading runs on\nto a second line\n---\n", id="heading_runs_on_above_its_underline"),
    pytest.param("<!-- a note -->\nThis paragraph runs on\nto a second line.\n", id="paragraph_runs_on_after_one_line_html_comment"),
    pytest.param("This paragraph runs on\n    to an indented second line\n    and a third.\n", id="paragraph_runs_on_to_indented_lines"),
    pytest.param("- Run:\n\n     ```sh\n     uv sync\n     ```\n\n  Then the tests\n  run on their own.\n", id="paragraph_runs_on_after_fence_closed_at_its_own_indent"),
    pytest.param("---\nThis paragraph runs on\nto a second line.\n", id="paragraph_runs_on_after_a_rule_line_that_opens_the_file"),
    pytest.param("This paragraph runs on\n*emphasis* first.\n", id="paragraph_runs_on_to_a_line_starting_with_emphasis"),
    pytest.param("The water cooled to\n-5 degrees overnight.\n", id="paragraph_runs_on_to_a_line_starting_with_a_negative_number"),
    pytest.param("The build got faster by\n1.5 times this week.\n", id="paragraph_runs_on_to_a_line_starting_with_a_decimal"),
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
    pytest.param("Steps:\n-\tone item\n1)\tanother item\n", id="list_items_with_a_tab_after_the_mark"),
    pytest.param("1. First step.\n2.\n-\n3. Third step.\n", id="empty_list_items"),
    pytest.param("## Install\nRun the installer.\n", id="paragraph_right_under_heading"),
    pytest.param("Run the installer.\n## Usage\n", id="heading_right_under_paragraph"),
    pytest.param("Title\n=====\n\nUsage\n-----\nRun the installer.\n", id="underlined_headings"),
    pytest.param("Above the rules.\n***\nBetween.\n___\nBetween.\n- - -\nBelow the rules.\n", id="rule_lines"),
    pytest.param("| Rule | Script |\n|---|---|\n| One command | `one_command.py` |\n", id="table_rows"),
    pytest.param("Run:\n\n```sh\nuv sync\nuv run pytest\n```\n", id="fenced_code"),
    pytest.param("Run:\n\n~~~sh\nuv sync\nuv run pytest\n~~~\n", id="tilde_fenced_code"),
    pytest.param("Run:\n\n    uv sync\n    uv run pytest\n\nOr:\n\n\tuv sync\n\tuv run pytest\n", id="indented_code"),
    pytest.param("Fence the commands with tildes:\n\n```markdown\n~~~sh\nuv sync\nuv run pytest\n~~~\n```\n", id="backtick_fence_showing_tilde_fence"),
    pytest.param("Fence the commands like this:\n\n````markdown\n```sh\nuv sync\nuv run pytest\n```\n````\n", id="longer_fence_showing_shorter_fence"),
    pytest.param("Run:\n\n```markdown\n```sh\nuv sync\nuv run pytest\n```\n", id="fence_line_with_info_string_inside_fence"),
    pytest.param('```yaml\ndescription: |\n    ```json\n    {"files": []}\n    ```\nactiveForm: Implementing\nstatus: open\n```\n', id="fence_indented_four_spaces_more_inside_fence"),
    pytest.param("---\nname: rules\ndescription: Hooks that enforce rules.\n---\n\nThe body.\n", id="front_matter"),
    pytest.param("---\r\nname: rules\r\ndescription: Hooks that enforce rules.\r\n---\r\n\r\nThe body.\r\n", id="front_matter_with_crlf"),
    pytest.param("---\nText right under a rule line that opens the file.\n", id="paragraph_right_under_a_rule_line_that_opens_the_file"),
    pytest.param('<p align="center">\n  <img src="logo.png" alt="Logo">\n</p>\n', id="html_block"),
    pytest.param("<!-- markdownlint-disable -->\nText right under a comment.\n", id="paragraph_right_under_html_comment"),
    pytest.param("<!--\nNotes for maintainers,\nkept on two lines.\n-->\nText right under the comment.\n", id="multi_line_html_comment"),
    pytest.param("> [!NOTE]\n> The hooks run with the python3 on the PATH.\n", id="github_alert"),
    pytest.param("[docs]: https://example.com/docs\n[api]: https://example.com/api\n", id="link_reference_definitions"),
])
def test_no_hard_wraps(text):
    assert not hard_wraps(text)


def test_main_blocks_write_of_wrapped_markdown(tmp_path):
    assert main(write_call(tmp_path / "README.md", WRAPPED), io.StringIO()) == 2


@pytest.mark.parametrize("name", ["README.markdown", "README.MD", "notes.Markdown"])
def test_main_blocks_write_of_wrapped_markdown_whatever_the_extension_and_its_case(tmp_path, name):
    assert main(write_call(tmp_path / name, WRAPPED), io.StringIO()) == 2


def test_the_script_run_as_a_hook_blocks_write_of_wrapped_markdown(tmp_path):
    """Claude Code runs the script by its path with the tool call on stdin, and takes exit code 2 as a block."""
    result = subprocess.run([SCRIPT], input=write_call(tmp_path / "README.md", WRAPPED).getvalue(), capture_output=True, text=True)
    assert result.returncode == 2


def test_the_script_reads_the_call_and_the_file_as_utf8_under_an_ascii_locale(tmp_path):
    """Claude Code sends the call in UTF-8, and the file is UTF-8, but outside UTF-8 mode Python decodes stdin and files in the locale's encoding."""
    readme = tmp_path / "README.md"
    readme.write_text("The café is open.\n", encoding="utf-8")
    call = edit_call(readme, "The café is open.", "The café is open,\nuntil this edit wraps it.").getvalue().encode("utf-8")
    ascii_locale = {"LC_ALL": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"}
    result = subprocess.run([sys.executable, SCRIPT], input=call, capture_output=True, env=ascii_locale)
    assert result.returncode == 2


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


@pytest.mark.parametrize("text, old_string, new_string", [
    pytest.param("Run the installer.\n## Usage\n", "## Usage", "Usage", id="heading_made_text"),
    pytest.param("Steps:\n- run the installer\n", "- run", "run", id="list_item_made_text"),
    pytest.param("Intro.\n## Old heading\nBody.\n", "## Old heading\n", "", id="heading_deleted"),
])
def test_main_blocks_edit_that_wraps_a_line_outside_its_new_string(tmp_path, text, old_string, new_string):
    readme = tmp_path / "README.md"
    readme.write_text(text)
    assert main(edit_call(readme, old_string, new_string), io.StringIO()) == 2


def test_main_blocks_edit_with_replace_all_that_wraps_only_a_later_match(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("```sh\nuv sync\n```\n\nRun uv sync first.\n")
    assert main(edit_call(readme, "uv sync", "uv sync\nuv run pytest", replace_all=True), io.StringIO()) == 2


@pytest.mark.parametrize("text, old_string, new_string", [
    pytest.param("She said “hello” to them.\n", 'She said "hello" to them.', 'She said "hello"\nto them.', id="straight_quotes_for_curly"),
    pytest.param('He said "bye" to them.\n', "He said “bye” to them.", "He said “bye”\nto them.", id="curly_quotes_for_straight"),
    pytest.param("The intro \\u2014 on one line.\n", "The intro — on one line.", "The intro —\non one line.", id="character_for_escape"),
    pytest.param("The intro — on one line.\n", "The intro \\u2014 on one line.", "The intro \\u2014\non one line.", id="escape_for_character"),
])
def test_main_blocks_edit_that_wraps_text_edit_matches_loosely(tmp_path, text, old_string, new_string):
    """Edit finds an old_string that differs from the file by curly quotes or a \\uXXXX escape, so the hook must too."""
    readme = tmp_path / "README.md"
    readme.write_text(text, encoding="utf-8")
    assert main(edit_call(readme, old_string, new_string), io.StringIO()) == 2


def test_main_blocks_edit_that_wraps_where_old_string_is_word_for_word_not_where_it_matches_loosely(tmp_path):
    """Edit tries old_string word for word first, so this edit lands on the paragraph, not on the code line above it."""
    readme = tmp_path / "README.md"
    readme.write_text("```\nShe said “hi”.\n```\n\nShe said \"hi\".\n", encoding="utf-8")
    assert main(edit_call(readme, 'She said "hi".', 'She said "hi".\nMore text.'), io.StringIO()) == 2


def test_main_blocks_edit_that_deletes_a_line_between_two_paragraph_lines(tmp_path):
    """With an empty new_string, Edit also deletes the line break after old_string, so the lines on either side join into one paragraph."""
    readme = tmp_path / "README.md"
    readme.write_text("First paragraph on one line.\n<!-- a note between the paragraphs -->\nSecond paragraph on one line.\n")
    assert main(edit_call(readme, "<!-- a note between the paragraphs -->", ""), io.StringIO()) == 2


@pytest.mark.parametrize("data", [
    pytest.param("﻿This paragraph is on one line.\n".encode("utf-16-le"), id="utf_16_after_its_byte_order_mark"),
    pytest.param("The café paragraph is on one line.\n".encode("latin-1"), id="bytes_that_are_not_utf_8"),
])
def test_main_blocks_edit_that_wraps_a_file_that_is_not_utf_8(tmp_path, data):
    """Edit reads a file that starts with the UTF-16 little-endian byte order mark as UTF-16, and any other as UTF-8 with what does not decode replaced."""
    readme = tmp_path / "README.md"
    readme.write_bytes(data)
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


def test_main_allows_edit_just_before_a_wrap_someone_else_made(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("This paragraph was wrapped\nby someone else.\n")
    assert main(edit_call(readme, "This paragraph", "This old paragraph"), io.StringIO()) == 0


def test_main_leaves_edit_with_missing_old_string_to_edit(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("This paragraph was wrapped\nby someone else.\n")
    assert main(edit_call(readme, "text that is not in the file", "a replacement that is long and on one line"), io.StringIO()) == 0
