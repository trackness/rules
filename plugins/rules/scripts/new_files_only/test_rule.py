"""Tests for "Write only for new files". Run from the repo root: uv run pytest"""
import io
import json
import subprocess
from pathlib import Path

from .rule import main

SCRIPT = Path(__file__).resolve().parent / "rule.py"


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


def test_the_script_run_as_a_hook_blocks_write_to_existing_file(tmp_path):
    """Claude Code runs the script by its path with the tool call on stdin, and takes exit code 2 as a block."""
    existing = tmp_path / "notes.md"
    existing.write_text("old text\n")
    result = subprocess.run([SCRIPT], input=tool_call(existing).getvalue(), capture_output=True, text=True)
    assert result.returncode == 2
