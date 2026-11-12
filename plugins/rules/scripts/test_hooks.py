"""Tests for the wiring of the "Rules" plugin. Run from the repo root: uv run pytest"""
import json
import os
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]


def test_every_wired_command_is_an_existing_executable():
    """Claude Code runs each command in hooks.json as written, and `claude plugin validate` does not check that it exists."""
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
    commands = [hook["command"] for groups in hooks.values() for group in groups for hook in group["hooks"]]
    assert commands
    for command in commands:
        script = Path(command.replace('"${CLAUDE_PLUGIN_ROOT}"', str(PLUGIN)))
        assert script.is_file() and os.access(script, os.X_OK), command
