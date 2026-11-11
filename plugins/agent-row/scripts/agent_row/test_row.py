"""Tests for "Agent rows". Run from the repo root: uv run pytest"""
import io
import json
import re

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
        "tokenCount": 0,
        **fields,
    }


def drawn(tasks, columns=120):
    """The body the command prints for each task's row, by the task's id."""
    stdout = io.StringIO()
    main(io.StringIO(json.dumps({"columns": columns, "tasks": tasks})), stdout, NOW)
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


def test_row_starts_with_the_agents_type():
    assert cells(body())[0] == "general-purpose"


def test_named_agent_shows_its_name_in_place_of_its_type():
    assert cells(body(name="auth-reviewer"))[0] == "auth-reviewer"


def test_stopped_agent_keeps_claude_codes_row():
    assert drawn([agent(status="completed")]) == {}


def test_model_follows_the_type_in_short():
    assert cells(body(model="claude-opus-5-5"))[:2] == ["general-purpose", "opus-5.5"]


@pytest.mark.parametrize("model, short", [
    pytest.param("us.anthropic.claude-opus-4-6-v1:0", "opus-4.6", id="bedrock"),
    pytest.param("claude-sonnet-4-5-20250929", "sonnet-4.5", id="snapshot_date"),
    pytest.param("us.anthropic.claude-sonnet-4-5-20250929-v1:0", "sonnet-4.5", id="bedrock_snapshot_date"),
])
def test_short_model(model, short):
    assert short_model(model) == short


def test_description_follows_the_model():
    assert cells(body(description="Review the auth module"))[:3] == ["general-purpose", "opus-5.5", "Review the auth module"]


def test_progress_summary_follows_the_description():
    assert cells(body(label="Reading src/auth/session.py"))[2:4] == ["Review the auth module", "Reading src/auth/session.py"]


def test_description_is_not_shown_twice_before_a_progress_summary():
    assert body(description="Review the auth module", label="Review the auth module").count("Review the auth module") == 1


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


def test_model_not_yet_known_leaves_its_cell_blank():
    just_spawned = agent(id="a2", description="Find config loading")
    del just_spawned["model"]
    rows = drawn([agent(id="a1", description="Review the auth module"), just_spawned])
    assert cells(rows["a2"])[:2] == ["general-purpose", "Find config loading"]
    assert column_of(rows["a2"], "Find config loading") == column_of(rows["a1"], "Review the auth module")


def test_row_ends_with_the_running_time_then_the_token_count():
    assert body(startTime=NOW - 5_700, tokenCount=12_345).endswith("5s · ↓ 12.3k tokens")


def test_running_time_and_token_count_stand_at_the_right_edge():
    assert len(body(columns=120, tokenCount=12_345)) == 120


def test_no_token_count_while_it_is_zero():
    assert cells(body(startTime=NOW - 5_700, tokenCount=0))[-1] == "5s"


@pytest.mark.parametrize("count, written", [
    pytest.param(850, "850", id="under_a_thousand"),
    pytest.param(1_234_567, "1.2m", id="millions"),
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
    assert "…" not in body(columns=71, description="Review the auth module", label="Review the auth module", tokenCount=12_345)


def test_panel_too_narrow_for_the_time_and_tokens_keeps_claude_codes_row():
    assert drawn([agent(startTime=NOW - 5_700, tokenCount=12_345)], columns=20) == {}


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
