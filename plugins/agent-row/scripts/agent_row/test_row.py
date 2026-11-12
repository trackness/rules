"""Tests for "Agent rows". Run from the repo root: uv run pytest"""
import io
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from .row import display_width, main, running_time, short_model, token_count

NOW = 1_762_860_000_000


def agent(**fields):
    """A running background agent's task as Claude Code passes it to the command, with fields changed."""
    return {
        "id": "a1",
        "type": "local_agent",
        "agentType": "general-purpose",
        "status": "running",
        "description": "Review the auth module",
        "label": "Review the auth module",
        "startTime": NOW - 5_700,
        "model": "claude-opus-5-5",
        "contextWindowSize": 1_000_000,
        "tokenCount": 0,
        "tokenSamples": [0],
        "cwd": "/home/dev/project",
        **fields,
    }


def drawn(tasks, columns=120):
    """The body the command prints for each task's row, by the task's id."""
    stdout = io.StringIO()
    panel = {
        "session_id": "00000000-0000-4000-8000-000000000001",
        "transcript_path": "/home/dev/.claude/projects/project/00000000-0000-4000-8000-000000000001.jsonl",
        "cwd": "/home/dev/project",
        "scratchpad_dir": "/tmp/claude/project/00000000-0000-4000-8000-000000000001/scratchpad",
        "prompt_id": "00000000-0000-4000-8000-000000000002",
        "columns": columns,
        "tasks": tasks,
    }
    main(io.StringIO(json.dumps(panel)), stdout, NOW)
    return {line["id"]: line["content"] for line in map(json.loads, stdout.getvalue().splitlines())}


def body(columns=120, **fields):
    """The body the command prints for one agent's row."""
    return drawn([agent(**fields)], columns)["a1"]


def cells(row):
    """The row's columns, which runs of two or more spaces separate."""
    return re.split(r" {2,}", row.strip())


def column_of(row, text):
    """The terminal column of the row at which the text starts."""
    return display_width(row[:row.index(text)])


def test_running_agent_gets_a_row():
    assert list(drawn([agent()])) == ["a1"]


def test_stopped_agent_gets_a_row():
    assert list(drawn([agent(status="completed")])) == ["a1"]


def test_row_starts_with_the_agents_type():
    assert cells(body())[0] == "general-purpose"


def test_named_agent_shows_its_name_in_place_of_its_type():
    assert cells(body(name="auth-reviewer"))[0] == "auth-reviewer"


def test_model_follows_the_type_in_short():
    assert cells(body(model="claude-opus-5-5"))[:2] == ["general-purpose", "opus-5.5"]


@pytest.mark.parametrize("model, short", [
    pytest.param("us.anthropic.claude-opus-4-6-v1", "opus-4.6", id="bedrock"),
    pytest.param("claude-sonnet-4-5-20250929", "sonnet-4.5", id="snapshot_date"),
    pytest.param("us.anthropic.claude-sonnet-4-5-20250929-v1:0", "sonnet-4.5", id="bedrock_snapshot_date_and_version"),
    pytest.param("claude-haiku-4-5@20251001", "haiku-4.5", id="vertex_at_date"),
    pytest.param("claude-sonnet-4-5@20250929", "sonnet-4.5", id="vertex_at_date_sonnet"),
])
def test_short_model(model, short):
    assert short_model(model) == short


def test_long_name_and_model_are_cut_so_that_they_leave_the_activity_its_room():
    row = body(columns=120, name="n" * 80, model="claude-" + "m" * 80, label="Reading src/auth/session.py")
    assert "Reading src/auth/session.py" in row


def test_control_characters_and_line_breaks_are_cleaned_from_name_description_and_label():
    row = body(name="auth\x1b]8;;http://x\x07-reviewer", description="Review\nthe\tauth  module\x9b", label="Reading\r\nsrc/auth\x00.py")
    assert "\x1b" not in row and "\x07" not in row and "\x00" not in row and "\x9b" not in row
    assert "\n" not in row and "\t" not in row and "\r" not in row
    assert cells(row)[2:4] == ["Review the auth module", "Reading src/auth.py"]


def test_description_cleaned_alike_in_label_still_shows_no_summary():
    assert cells(body(description="Review\nthe auth module", label="Review the auth module"))[3] == "no summary yet"


def test_script_runs_as_a_program_and_the_wired_command_is_that_file():
    script = Path(__file__).with_name("row.py")
    command = json.loads((script.parents[2] / "settings.json").read_text())["subagentStatusLine"]["command"]
    assert command.replace('"${CLAUDE_PLUGIN_ROOT}"', str(script.parents[2])) == str(script)
    panel = {"columns": 120, "tasks": [agent(description="café")]}
    # Real UTF-8 bytes with a Latin-1 stdin: reading stdin as text would turn é into Ã©.
    result = subprocess.run([str(script)], input=json.dumps(panel, ensure_ascii=False).encode("utf-8"), capture_output=True, check=True, env={"PATH": os.environ["PATH"], "PYTHONIOENCODING": "latin-1"})
    row = json.loads(result.stdout)
    assert row["id"] == "a1"
    assert cells(row["content"])[2] == "café"


def test_description_follows_the_model():
    assert cells(body(description="Review the auth module"))[:3] == ["general-purpose", "opus-5.5", "Review the auth module"]


def test_progress_summary_follows_the_description():
    assert cells(body(label="Reading src/auth/session.py"))[2:4] == ["Review the auth module", "Reading src/auth/session.py"]


def test_running_agent_without_a_progress_summary_says_it_has_none_yet():
    assert cells(body(description="Review the auth module", label="Review the auth module"))[2:4] == ["Review the auth module", "no summary yet"]


def test_stopped_agent_without_a_progress_summary_says_it_has_none():
    assert cells(body(status="completed", description="Review the auth module", label="Review the auth module"))[2:4] == ["Review the auth module", "no summary"]


def test_long_description_is_cut_to_its_limit():
    description = "Investigate why the integration tests for the payment service fail intermittently on CI"
    assert cells(body(description=description, label="Reading .github/workflows/ci.yml"))[2] == "Investigate why the integration…"


def test_fixed_columns_line_up_across_rows():
    rows = drawn([
        agent(id="a1", agentType="general-purpose", model="claude-opus-5-5", description="Review the auth module", label="Reading src/auth/session.py"),
        agent(id="a2", agentType="Explore", model="claude-haiku-4-5", description="Find config loading", label="Searching for load_config"),
    ])
    first = [column_of(rows["a1"], text) for text in ("opus-5.5", "Review the auth module", "Reading src/auth/session.py")]
    second = [column_of(rows["a2"], text) for text in ("haiku-4.5", "Find config loading", "Searching for load_config")]
    assert first == second


def test_stopped_agents_row_lines_up_with_the_running_agents_rows():
    rows = drawn([
        agent(id="a1", agentType="Explore", model="claude-haiku-5-5", description="Count files by extension", label="Waiting 65 seconds via Python fallback"),
        agent(id="a2", agentType="general-purpose", status="completed", model="claude-sonnet-5-5", description="Summarise recent commits", label="Waiting 70 seconds via Python"),
    ])
    running = [column_of(rows["a1"], text) for text in ("haiku-5.5", "Count files by extension", "Waiting 65 seconds via Python fallback")]
    stopped = [column_of(rows["a2"], text) for text in ("sonnet-5.5", "Summarise recent commits", "Waiting 70 seconds via Python")]
    assert running == stopped


def test_task_restored_without_a_model_leaves_its_cell_blank():
    restored = agent(id="a2", description="Find config loading")
    del restored["model"]
    rows = drawn([agent(id="a1", description="Review the auth module"), restored])
    assert cells(rows["a2"])[:2] == ["general-purpose", "Find config loading"]
    assert column_of(rows["a2"], "Find config loading") == column_of(rows["a1"], "Review the auth module")


def test_row_ends_with_the_running_time_then_the_token_count():
    assert body(startTime=NOW - 5_700, tokenCount=12_345).endswith("5s · ↓ 12.3k tokens")


def test_stopped_agent_shows_its_status_in_place_of_a_running_time():
    assert cells(body(status="completed", startTime=NOW - 26_900, tokenCount=30_977))[-1] == "completed · ↓ 31.0k tokens"


def test_running_time_and_token_count_stand_at_the_right_edge():
    assert len(body(columns=120, tokenCount=12_345)) == 120


def test_no_token_count_while_it_is_zero():
    assert cells(body(startTime=NOW - 5_700, tokenCount=0))[-1] == "5s"


@pytest.mark.parametrize("count, written", [
    pytest.param(850, "850", id="under_a_thousand"),
    pytest.param(1_234_567, "1.2m", id="millions"),
    pytest.param(12_350, "12.4k", id="half_rounds_up"),
    pytest.param(999_949, "999.9k", id="last_thousands"),
    pytest.param(999_950, "1.0m", id="rounds_up_into_millions"),
])
def test_token_count(count, written):
    assert token_count(count) == written


@pytest.mark.parametrize("milliseconds, written", [
    pytest.param(65_000, "1m 5s", id="minutes"),
    pytest.param(65_500, "1m 6s", id="seconds_rounded_half_up_from_a_minute"),
    pytest.param(3_725_000, "1h 2m 5s", id="hours"),
    pytest.param(90_061_000, "1d 1h 1m", id="days_without_seconds"),
])
def test_running_time(milliseconds, written):
    assert running_time(milliseconds) == written


def test_narrow_panel_cuts_the_activity_and_keeps_the_time_and_tokens():
    row = body(columns=60, label="Reading src/auth/session.py and src/auth/tokens.py", startTime=NOW - 5_700, tokenCount=12_345)
    assert len(row) == 60
    assert row.endswith("…  5s · ↓ 12.3k tokens")


def test_cut_of_only_trailing_spaces_shows_no_ellipsis():
    assert "…" not in body(columns=99, description="Review the auth module", label="Reading src/auth/session.py ", tokenCount=12_345)


def test_panel_too_narrow_for_one_rows_time_and_tokens_leaves_every_row_to_claude_code():
    rows = drawn([
        agent(id="a1", agentType="Explore", startTime=NOW - 62_000, tokenCount=26_333),
        agent(id="a2", agentType="Plan", status="completed", tokenCount=30_977),
    ], columns=27)
    assert rows == {}


def test_each_wide_character_takes_two_of_the_panels_columns():
    description = "認証モジュールを確認"
    row = body(columns=120, description=description, label="Reading src/auth/session.py")
    assert len(row) + len(description) == 120


def test_wide_characters_line_up_by_the_columns_they_take():
    rows = drawn([
        agent(id="a1", description="認証モジュールを確認", label="Reading src/auth/session.py"),
        agent(id="a2", description="Find config loading", label="Searching for load_config"),
    ])
    assert column_of(rows["a1"], "Reading") == column_of(rows["a2"], "Searching")


def test_wide_characters_are_cut_by_the_columns_they_take():
    row = body(columns=90, label="設定ファイルの読み込み処理を確認しています", startTime=NOW - 5_700, tokenCount=12_345)
    assert display_width(row) == 90
