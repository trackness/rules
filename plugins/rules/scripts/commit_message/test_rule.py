"""Tests for "Conventional Commits messages". Run from the repo root: uv run pytest"""
import io
import os
import subprocess
from pathlib import Path

import pytest

from .rule import conventional, main, register

SCRIPT = Path(__file__).resolve().parent / "rule.py"
TEST_IDENTITY = {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com", "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com"}


def commit_in_session(tmp_path, message):
    """Register the hook in a session env file, then commit in a new repo as Claude's Bash tool would, with that file sourced."""
    env_file, repo = tmp_path / "session.env", tmp_path / "repo"
    env_file.touch()  # Claude Code hands the hook an existing file to append to
    register(str(env_file), io.StringIO())
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return subprocess.run(
        ["bash", "-c", 'source "$1" && git -C "$2" -c commit.gpgsign=false commit --allow-empty -q -m "$3"', "_", env_file, repo, message],
        env={**os.environ, **TEST_IDENTITY},
        capture_output=True,
    )


def message_file(tmp_path, message):
    """The file git passes to a commit-msg hook, holding the message."""
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(message)
    return str(path)


@pytest.mark.parametrize("message", [
    pytest.param("Add login page", id="no_type"),
    pytest.param("feature: add login page", id="type_not_in_the_list"),
    pytest.param("feat: ", id="no_description"),
    pytest.param("fix: handle empty input\nThe body starts right under the header.", id="body_without_blank_line"),
    pytest.param("fixup! Add login page\n\n", id="fixup_of_unconventional_commit"),
])
def test_not_conventional(message):
    assert not conventional(message)


@pytest.mark.parametrize("message", [
    pytest.param("feat: add login page", id="type_and_description"),
    pytest.param("feat(auth): add passkey login", id="scope"),
    pytest.param("feat(api)!: remove legacy endpoint", id="breaking_change"),
    pytest.param("fix: handle empty input\n\nAn empty form no longer crashes the page.\n\nRefs: #12", id="body_and_footer"),
    pytest.param("fixup! feat: add login page\n\n", id="fixup_of_conventional_commit"),
    pytest.param("squash! feat: add login page\n\nSquash note.\n", id="squash_of_conventional_commit"),
    pytest.param("amend! feat: add login page\n\nfeat: add login page\n\nBody of the target.\n", id="amend_of_conventional_commit"),
    pytest.param("fixup! fixup! feat: add login page\n\n", id="fixup_of_fixup_commit"),
])
def test_conventional(message):
    assert conventional(message)


def test_main_rejects_unconventional_message(tmp_path):
    assert main(message_file(tmp_path, "Add login page\n"), io.StringIO()) == 1


def test_main_accepts_conventional_message(tmp_path):
    assert main(message_file(tmp_path, "feat: add login page\n"), io.StringIO()) == 0


def test_main_rejection_gives_a_reason(tmp_path):
    stderr = io.StringIO()
    main(message_file(tmp_path, "Add login page\n"), stderr)
    assert stderr.getvalue().strip() != ""


def test_registered_hook_rejects_unconventional_commit(tmp_path):
    assert commit_in_session(tmp_path, "Add login page").returncode != 0


def test_registered_hook_accepts_conventional_commit(tmp_path):
    assert commit_in_session(tmp_path, "feat: add login page").returncode == 0


def test_session_start_without_env_file_says_the_check_is_inactive():
    """Claude Code gives no CLAUDE_ENV_FILE to a SessionStart hook run in PowerShell, so there is nowhere to register the hook."""
    env = {name: value for name, value in os.environ.items() if name != "CLAUDE_ENV_FILE"}
    result = subprocess.run([SCRIPT], env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert len(result.stderr.splitlines()) == 1 and "not active" in result.stderr
