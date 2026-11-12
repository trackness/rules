"""Tests for git_hook.py, the registration every rule that git enforces shares. Run from the repo root: uv run pytest"""
import io
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from .git_hook import register
from .git_testing import BASE_ENV, EXISTING_GIT_CONFIG, GIT_ENV, git, needs_config_hooks, needs_zsh, run_with_env_files, start_session

SCRIPTS = Path(__file__).resolve().parent
# The git config each git rule's SessionStart hook adds, in order: its hook's command, then its event.
REGISTERED = {
    "commit_message": [
        f"hook.conventional-commits.command={shlex.quote(str(SCRIPTS / 'commit_message' / 'rule.py'))}",
        "hook.conventional-commits.event=commit-msg",
    ],
    "branch_name": [
        f"hook.conventional-branch.command={shlex.quote(str(SCRIPTS / 'branch_name' / 'rule.py'))} pre-push",
        "hook.conventional-branch.event=pre-push",
    ],
    "work_branch": [
        f"hook.work-branch.command={shlex.quote(str(SCRIPTS / 'work_branch' / 'rule.py'))} pre-commit",
        "hook.work-branch.event=pre-commit",
    ],
}


def session_with_test_hook(tmp_path):
    """The env file of a session that registers, as the pre-commit hook test-check, a command that rejects every commit."""
    env_file = tmp_path / "session.env"
    env_file.touch()  # Claude Code hands the hook an existing file to append to
    register(str(env_file), io.StringIO(), "test-check", "pre-commit", ["false"], "The test check")
    return env_file


def new_repo(tmp_path):
    """A new, empty repo."""
    repo = tmp_path / "repo"
    git("init", "-q", repo)
    return repo


def start_session_with_git(tmp_path, rule, git_script):
    """Run the rule's SessionStart hook with only a stand-in git on the PATH, running the sh script git_script, or no git if it is None.

    Return the finished hook and the env file it was given.
    """
    stand_ins = tmp_path / "bin"
    stand_ins.mkdir()
    if git_script is not None:
        (stand_ins / "git").write_text(f"#!/bin/sh\n{git_script}\n")
        (stand_ins / "git").chmod(0o755)
    env_file = tmp_path / "session.env"
    env_file.touch()  # Claude Code hands the hook an existing file to append to
    hook_input = json.dumps({"hook_event_name": "SessionStart", "source": "startup"})
    # Run by this Python, since the PATH holds no python3 for the script's #! line to find.
    result = subprocess.run(
        [sys.executable, SCRIPTS / rule / "rule.py"], input=hook_input, env={**BASE_ENV, "PATH": str(stand_ins), "CLAUDE_ENV_FILE": str(env_file)},
        capture_output=True, text=True,
    )
    return result, env_file


def test_test_subprocesses_get_a_minimal_environment(tmp_path, monkeypatch):
    """A variable of the user's, such as a secret, reaches no subprocess a test starts, where pytest would print it when the call fails."""
    monkeypatch.setenv("TEST_MARKER", "leaked")
    script = tmp_path / "hook.sh"
    script.write_text('#!/bin/sh\necho "${TEST_MARKER-absent}" >> "$CLAUDE_ENV_FILE"\n')
    script.chmod(0o755)
    assert start_session(tmp_path / "session.env", script).read_text() == "absent\n"
    assert set(GIT_ENV) == {
        "PATH", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
    }


def test_each_wired_command_is_an_executable_file_and_session_start_runs_the_registered_rules():
    """hooks.json names scripts that exist, which `claude plugin validate` does not check."""
    plugin = SCRIPTS.parent
    hooks = json.loads((plugin / "hooks" / "hooks.json").read_text())["hooks"]
    commands = {
        event: [shlex.split(hook["command"].replace("${CLAUDE_PLUGIN_ROOT}", str(plugin)))[0] for group in groups for hook in group["hooks"]]
        for event, groups in hooks.items()
    }
    for command in sum(commands.values(), []):
        assert os.access(command, os.X_OK) and Path(command).is_file(), command
    assert commands["SessionStart"] == [str(SCRIPTS / rule / "rule.py") for rule in REGISTERED]


@needs_config_hooks
@pytest.mark.parametrize("shell", ["bash", pytest.param("zsh", marks=needs_zsh)])
@pytest.mark.parametrize("rules", [
    pytest.param(["commit_message", "branch_name", "work_branch"], id="commit_rule_first"),
    pytest.param(["work_branch", "branch_name", "commit_message"], id="work_rule_first"),
])
def test_the_git_rules_register_after_git_config_already_in_the_session_and_after_each_other(tmp_path, shell, rules):
    """Claude Code runs each rule's SessionStart hook with its own env file, and sources the files one after another in every Bash command."""
    env_files = [start_session(tmp_path / f"{rule}.env", SCRIPTS / rule / "rule.py") for rule in rules]
    result = run_with_env_files(env_files, "git", "config", "--list", "--show-scope", shell=shell, env={**GIT_ENV, **EXISTING_GIT_CONFIG})
    assert [line for line in result.stdout.splitlines() if line.startswith("command\t")] == [
        "command\ttest.kept=yes",
        *(f"command\t{entry}" for rule in rules for entry in REGISTERED[rule]),
    ]


@pytest.mark.parametrize("rule", REGISTERED)
@pytest.mark.parametrize(("git_script", "found"), [
    pytest.param("echo 'git version 2.53.0'", "git 2.53.0", id="older_git"),
    pytest.param("exit 1", "no git whose version it could read", id="git_that_fails"),
    pytest.param(None, "no git whose version it could read", id="no_git"),
])
def test_session_start_without_git_2_54_registers_nothing_and_tells_claude(tmp_path, rule, git_script, found):
    """Git runs no hook defined in config before 2.54.0, so a hook registered there would check nothing, and Claude would not know it.

    Claude Code adds a SessionStart hook's stdout at exit 0 to Claude's context; Claude never sees its stderr.
    """
    result, env_file = start_session_with_git(tmp_path, rule, git_script)
    assert result.returncode == 0 and env_file.read_text() == ""
    assert len(result.stdout.splitlines()) == 1
    assert result.stdout.endswith(f" is not active: the git-rules plugin requires git 2.54.0 or later, and found {found}.\n")


@pytest.mark.parametrize("rule", REGISTERED)
def test_session_start_with_a_vendor_git_2_54_registers_the_rule(tmp_path, rule):
    """A vendor's git adds to its version, as Apple's does."""
    result, env_file = start_session_with_git(tmp_path, rule, "echo 'git version 2.54.0 (Apple Git-157)'")
    assert result.returncode == 0 and result.stdout == ""
    listed = run_with_env_files([env_file], "git", "config", "--list", "--show-scope")
    assert [line for line in listed.stdout.splitlines() if line.startswith("command\t")] == [f"command\t{entry}" for entry in REGISTERED[rule]]


@needs_config_hooks
def test_registration_cut_short_leaves_git_working(tmp_path):
    """A shell can stop partway through the env file, such as at a line it cannot parse; what it has counted by then must leave git working."""
    env_file = session_with_test_hook(tmp_path)
    env_file.write_text("".join(env_file.read_text().splitlines(keepends=True)[:2]))  # the first entry, and the count that takes it in
    result = run_with_env_files([env_file], "git", "-C", new_repo(tmp_path), "commit", "--allow-empty", "-q", "-m", "feat: start")
    assert result.returncode == 0, result.stderr


@needs_config_hooks
def test_a_later_session_start_replaces_the_registration_in_the_same_env_file(tmp_path):
    """Claude Code hands a hook the same env file at every session start, such as a resume or a compaction, and a plugin update moves the script between two."""
    env_file = tmp_path / "session.env"
    env_file.write_text("export KEPT=yes\n")
    register(str(env_file), io.StringIO(), "test-check", "pre-commit", ["old path/rule.py"], "The test check")
    register(str(env_file), io.StringIO(), "other-check", "pre-push", ["other"], "The other check")
    register(str(env_file), io.StringIO(), "test-check", "pre-commit", ["new path/rule.py"], "The test check")
    listed = run_with_env_files([env_file], "git", "config", "--list", "--show-scope")
    assert [line for line in listed.stdout.splitlines() if line.startswith("command\t")] == [
        "command\thook.other-check.command=other",
        "command\thook.other-check.event=pre-push",
        "command\thook.test-check.command='new path/rule.py'",
        "command\thook.test-check.event=pre-commit",
    ]
    assert env_file.read_text().startswith("export KEPT=yes\n")


@needs_config_hooks
def test_registered_command_runs_as_git_hook_for_its_event(tmp_path):
    """The test hook rejects every commit, so each way that commits despite it, below, gets past every git rule."""
    repo = new_repo(tmp_path)
    assert run_with_env_files([session_with_test_hook(tmp_path)], "git", "-C", repo, "commit", "--allow-empty", "-q", "-m", "feat: start").returncode != 0


@needs_config_hooks
@pytest.mark.parametrize("command", [
    pytest.param(lambda repo: ["git", "-C", repo, "-c", "hook.test-check.enabled=false", "commit", "--allow-empty", "-q", "-m", "WIP"], id="enabled_false"),
    pytest.param(lambda repo: ["git", "-C", repo, "-c", "hook.test-check.event=", "commit", "--allow-empty", "-q", "-m", "WIP"], id="empty_event"),
    pytest.param(lambda repo: ["env", "GIT_CONFIG_COUNT=0", "git", "-C", repo, "commit", "--allow-empty", "-q", "-m", "WIP"], id="git_config_count_0"),
    pytest.param(
        lambda repo: [
            "env", "-i", f"PATH={os.environ['PATH']}", "git", "-C", repo, "-c", "user.name=Test", "-c", "user.email=test@example.com",
            "commit", "--allow-empty", "-q", "-m", "WIP",
        ],
        id="env_i",
    ),
])
def test_ways_past_every_git_rule(tmp_path, command):
    """Each command commits despite the registered hook, as the plugin README's Git hooks section says of every git rule."""
    repo = new_repo(tmp_path)
    assert run_with_env_files([session_with_test_hook(tmp_path)], *command(repo)).returncode == 0


@needs_config_hooks
def test_repository_config_can_turn_any_git_rule_off(tmp_path):
    """A repository's or user's hook.<name>.enabled false turns the hook off for every later git command there."""
    repo = new_repo(tmp_path)
    git("-C", repo, "config", "hook.test-check.enabled", "false")
    assert run_with_env_files([session_with_test_hook(tmp_path)], "git", "-C", repo, "commit", "--allow-empty", "-q", "-m", "WIP").returncode == 0
