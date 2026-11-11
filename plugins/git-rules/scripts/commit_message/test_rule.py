"""Tests for "Conventional Commits messages". Run from the repo root: uv run pytest"""
import io
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ..git_testing import git, needs_config_hooks, needs_zsh, run_in_session
from .rule import conventional, main

SCRIPT = Path(__file__).resolve().parent / "rule.py"


def commit_in_session(tmp_path, message, shell="bash", script=SCRIPT):
    """Start a session whose SessionStart hook is the script, then commit in a new repo as Claude's Bash tool would, with the env file sourced."""
    repo = tmp_path / "repo"
    git("init", "-q", repo)
    return run_in_session(tmp_path, script, "git", "-C", repo, "commit", "--allow-empty", "-q", "-m", message, shell=shell)


def repo_with_side_branch(tmp_path):
    """A new repo on main with a conventional commit, and a branch side holding one more commit, whose message is not conventional."""
    repo = tmp_path / "repo"
    git("init", "-q", "-b", "main", repo)
    for branch, file, message in (("main", "start.txt", "feat: start"), ("side", "side.txt", "WIP on side")):
        git("-C", repo, "switch", "-q", "-C", branch)
        (repo / file).write_text(file)
        git("-C", repo, "add", file)
        git("-C", repo, "commit", "-q", "-m", message)
    git("-C", repo, "switch", "-q", "main")
    return repo


def message_file(tmp_path, message):
    """The file git passes to a commit-msg hook, holding the message."""
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(message)
    return str(path)


@pytest.mark.parametrize("message", [
    pytest.param("Add login page", id="no_type"),
    pytest.param("feature: add login page", id="type_not_in_the_list"),
    pytest.param("Feat: add login page", id="type_not_in_lowercase"),
    pytest.param("feat: ", id="no_description"),
    pytest.param("fix: handle empty input\nThe body starts right under the header.", id="body_without_blank_line"),
    pytest.param("fixup! Add login page\n\n", id="fixup_of_unconventional_commit"),
])
def test_not_conventional(message):
    assert not conventional(message)


@pytest.mark.parametrize("message", [
    pytest.param("feat: add login page", id="type_and_description"),
    *[pytest.param(f"{type}: change something", id=type) for type in ("fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore")],
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


@needs_config_hooks
def test_registered_hook_rejects_unconventional_commit(tmp_path):
    assert commit_in_session(tmp_path, "Add login page").returncode != 0


@needs_config_hooks
def test_registered_hook_accepts_conventional_commit(tmp_path):
    assert commit_in_session(tmp_path, "feat: add login page").returncode == 0


@needs_config_hooks
@pytest.mark.parametrize("shell", ["bash", pytest.param("zsh", marks=needs_zsh)])
def test_registered_hook_runs_from_a_path_with_spaces_and_quotes(tmp_path, shell):
    """The plugin can be installed under such a path; the session's shell must still parse the env file, and git still run the script."""
    scripts = tmp_path / "it's a \"plugin\"" / "scripts"
    shutil.copytree(SCRIPT.parent.parent, scripts, ignore=shutil.ignore_patterns("__pycache__"))  # the rule imports git_hook.py from there
    result = commit_in_session(tmp_path, "Add login page", shell=shell, script=scripts / SCRIPT.parent.name / "rule.py")
    assert "Rejected: the commit message does not follow Conventional Commits" in result.stderr


@needs_config_hooks
@pytest.mark.parametrize("command", [
    pytest.param(lambda repo, tmp_path: ["git", "-C", repo, "merge", "--no-ff", "-m", "Merge side", "side"], id="merge"),
    pytest.param(lambda repo, tmp_path: ["git", "-C", repo, "commit", "--allow-empty", "-F", tmp_path / "message.txt"], id="message_file"),
    pytest.param(lambda repo, tmp_path: ["bash", "-c", f"git -C '{repo}' commit --allow-empty -F - <<'EOF'\nAdd login page\nEOF"], id="heredoc"),
    pytest.param(lambda repo, tmp_path: ["git", "-C", repo, "commit", "--amend", "-m", "Add login page"], id="amend"),
])
def test_registered_hook_rejects_unconventional_message_however_given(tmp_path, command):
    repo = repo_with_side_branch(tmp_path)
    (tmp_path / "message.txt").write_text("Add login page\n")
    result = run_in_session(tmp_path, SCRIPT, *command(repo, tmp_path))
    assert result.returncode != 0 and "Rejected: the commit message does not follow Conventional Commits" in result.stderr


@needs_config_hooks
def test_repository_commit_msg_hook_still_runs_after_this_one(tmp_path):
    repo = repo_with_side_branch(tmp_path)
    ran = tmp_path / "repository-hook-ran"
    repository_hook = repo / ".git" / "hooks" / "commit-msg"
    repository_hook.write_text(f"#!/bin/sh\ntouch '{ran}'\n")
    repository_hook.chmod(0o755)
    # GIT_TRACE logs each hook git runs, in order.
    result = run_in_session(tmp_path, SCRIPT, "env", "GIT_TRACE=1", "git", "-C", repo, "commit", "--allow-empty", "-q", "-m", "feat: add login page")
    hooks_run = [line for line in result.stderr.splitlines() if "trace: run_command:" in line and "COMMIT_EDITMSG" in line]
    assert result.returncode == 0 and ran.exists()
    assert [str(SCRIPT) in hooks_run[0], ".git/hooks/commit-msg" in hooks_run[-1]] == [True, True]


@needs_config_hooks
@pytest.mark.parametrize("command", [
    pytest.param(lambda repo: ["git", "-C", repo, "commit", "--allow-empty", "-q", "--no-verify", "-m", "WIP"], id="commit_no_verify"),
    pytest.param(lambda repo: ["git", "-C", repo, "merge", "--no-ff", "--no-verify", "-m", "WIP merge", "side"], id="merge_no_verify"),
    pytest.param(lambda repo: ["git", "-C", repo, "revert", "--no-edit", "HEAD"], id="revert"),
    pytest.param(lambda repo: ["git", "-C", repo, "cherry-pick", "side"], id="cherry_pick"),
    pytest.param(lambda repo: ["git", "-C", repo, "commit-tree", "HEAD^{tree}", "-m", "WIP"], id="commit_tree"),
])
def test_ways_past_the_commit_msg_check_the_readme_lists(tmp_path, command):
    """Each command makes a commit whose message is not conventional despite the registered hook, as the README's Not checked list says.

    The ways past every git rule, such as turning the hook off by its name, are tested once, in test_git_hook.py.
    """
    repo = repo_with_side_branch(tmp_path)
    assert run_in_session(tmp_path, SCRIPT, *command(repo)).returncode == 0


def test_session_start_without_env_file_tells_claude_the_check_is_inactive():
    """Claude Code gives no CLAUDE_ENV_FILE to a SessionStart hook run in PowerShell, so there is nowhere to register the hook.

    Claude Code adds a SessionStart hook's stdout at exit 0 to Claude's context; Claude never sees its stderr.
    """
    env = {name: value for name, value in os.environ.items() if name != "CLAUDE_ENV_FILE"}
    result = subprocess.run([SCRIPT], env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) == 1 and "not active" in result.stdout
