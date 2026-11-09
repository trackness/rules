"""Tests for scripts/new_files_only.py. Run from the repo root: uv run pytest"""
import io
import json

from scripts.new_files_only import main


def tool_call(file_path):
    """A Write tool call as Claude Code sends it to the hook on stdin."""
    return io.StringIO(json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(file_path), "content": "new text\n"}}))


def test_main_blocks_write_to_existing_file(tmp_path):
    existing = tmp_path / "notes.md"
    existing.write_text("old text\n")
    assert main(tool_call(existing), io.StringIO()) == 2


def test_main_allows_write_to_new_file(tmp_path):
    assert main(tool_call(tmp_path / "notes.md"), io.StringIO()) == 0


def test_main_block_gives_a_reason(tmp_path):
    existing = tmp_path / "notes.md"
    existing.write_text("old text\n")
    stderr = io.StringIO()
    main(tool_call(existing), stderr)
    assert stderr.getvalue().strip() != ""
