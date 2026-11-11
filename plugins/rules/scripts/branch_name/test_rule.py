"""Tests for "Conventional Branch names". Run from the repo root: uv run pytest"""
import io
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from ..git_testing import EXISTING_GIT_CONFIG, GIT_ENV, git, needs_config_hooks, needs_zsh, run_in_session, start_session
from .rule import conventional, main, new_branch_names

SCRIPT = Path(__file__).resolve().parent / "rule.py"
COMMIT_MESSAGE_RULE = SCRIPT.parent.parent / "commit_message" / "rule.py"


def tool_call(cmd):
    """A Bash tool call as Claude Code sends it to the hook on stdin."""
    return io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}))


def repo_with_remote(tmp_path):
    """A new repo with one commit on main, and an empty bare repo as its remote origin."""
    repo, remote = tmp_path / "repo", tmp_path / "remote.git"
    git("init", "-q", "-b", "main", repo)
    git("init", "-q", "--bare", remote)
    git("-C", repo, "remote", "add", "origin", remote)
    git("-C", repo, "commit", "--allow-empty", "-q", "-m", "feat: start")
    return repo, remote


def remote_branches(remote):
    """The names of the branches in the remote repo."""
    return git("-C", remote, "for-each-ref", "--format=%(refname:short)", "refs/heads/").split()


def git_in_session(tmp_path, repo, *args, shell="bash", script=SCRIPT):
    """Start a session, then run git in repo with the given arguments as Claude's Bash tool would, with the env file sourced."""
    return run_in_session(tmp_path, script, "git", "-C", repo, *args, shell=shell)


@pytest.mark.parametrize("name", [
    pytest.param("add-login-page", id="no_type"),
    pytest.param("docs/update-readme", id="type_not_in_the_list"),
    pytest.param("feature/Add-Login-Page", id="uppercase"),
    pytest.param("feature/add-login-", id="trailing_hyphen"),
    pytest.param("feature/upgrade-python-3.15", id="dot_outside_release"),
])
def test_not_conventional(name):
    assert not conventional(name)


@pytest.mark.parametrize("name", [
    pytest.param("feature/add-login-page", id="feature"),
    pytest.param("feat/add-login-page", id="feat"),
    pytest.param("bugfix/fix-header-overflow", id="bugfix"),
    pytest.param("fix/fix-header-overflow", id="fix"),
    pytest.param("hotfix/security-patch", id="hotfix"),
    pytest.param("chore/update-dependencies", id="chore"),
    pytest.param("release/v1.2.0", id="release_version"),
    pytest.param("main", id="main"),
    pytest.param("master", id="master"),
    pytest.param("develop", id="develop"),
    pytest.param("gh-pages", id="gh_pages"),
])
def test_conventional(name):
    assert conventional(name)


@pytest.mark.parametrize("cmd, names", [
    pytest.param("git checkout -b Add_Login", ["Add_Login"], id="checkout_b"),
    pytest.param("git checkout -B Add_Login", ["Add_Login"], id="checkout_force_b"),
    pytest.param("git switch -c Add_Login", ["Add_Login"], id="switch_c"),
    pytest.param("git switch -C Add_Login", ["Add_Login"], id="switch_force_c"),
    pytest.param("git switch --create Add_Login", ["Add_Login"], id="switch_create"),
    pytest.param("git -c color.ui=never log -1", [], id="git_config_option"),
    pytest.param("git -C /repo checkout -b Add_Login", ["Add_Login"], id="git_directory_option"),
    pytest.param("git worktree add -b Add_Login ../add-login", ["Add_Login"], id="worktree_add_b"),
    pytest.param("git worktree add -B Add_Login ../add-login", ["Add_Login"], id="worktree_add_force_b"),
    pytest.param("git branch Add_Login", ["Add_Login"], id="branch"),
    pytest.param("git branch -d Add_Login", [], id="branch_delete"),
    pytest.param("git branch -m Add_Login", ["Add_Login"], id="branch_rename_current"),
    pytest.param("git branch -m old-name Add_Login", ["Add_Login"], id="branch_rename_other"),
    pytest.param("git branch -M Add_Login", ["Add_Login"], id="branch_force_rename"),
    pytest.param("sudo git checkout -b Add_Login", ["Add_Login"], id="sudo"),
    pytest.param("/usr/bin/git checkout -b Add_Login", ["Add_Login"], id="git_by_full_path"),
    pytest.param("GIT_TRACE=1 git checkout -b Add_Login", ["Add_Login"], id="environment_assignment"),
    pytest.param("env GIT_TRACE=1 git checkout -b Add_Login", ["Add_Login"], id="env"),
    pytest.param("git push origin HEAD:Add_Login", ["Add_Login"], id="push_refspec"),
    pytest.param("git push -u origin local-name:refs/heads/Add_Login", ["Add_Login"], id="push_refspec_full_ref"),
    pytest.param("git push origin :Add_Login", [], id="push_delete"),
    pytest.param("git push -u origin Add_Login", [], id="push_without_colon"),
    pytest.param("git push origin V1.0:refs/tags/V1.0", [], id="push_tag"),
    pytest.param("git push git@github.com:trackness/rules.git HEAD:Add_Login", ["Add_Login"], id="push_to_url"),
    pytest.param("git push --force-with-lease=feature/add-login:4f2a9c1 origin feature/add-login", [], id="push_force_with_lease"),
    pytest.param("git push -o ci.skip git@github.com:trackness/rules.git HEAD:Add_Login", ["Add_Login"], id="push_option_short"),
    pytest.param("git push --push-option ci.skip git@github.com:trackness/rules.git feature/add-login", [], id="push_option_long"),
    pytest.param("git push --recurse-submodules check git@github.com:trackness/rules.git feature/add-login", [], id="push_recurse_submodules"),
    pytest.param("git push --receive-pack /opt/git/bin/git-receive-pack git@example.com:repo.git feature/add-login", [], id="push_receive_pack"),
    pytest.param("git push --exec /opt/git/bin/git-receive-pack git@example.com:repo.git feature/add-login", [], id="push_exec"),
    pytest.param("git push backup 'refs/heads/*:refs/heads/*'", [], id="push_pattern"),
    pytest.param("gh pr checkout 5 -b Add_Login", ["Add_Login"], id="gh_pr_checkout_b"),
    pytest.param("gh pr checkout 5 --branch Add_Login", ["Add_Login"], id="gh_pr_checkout_branch"),
    pytest.param("gh pr checkout 5", [], id="gh_pr_checkout_own_branch"),
    pytest.param("ls -la", [], id="not_git"),
    pytest.param("git --version", [], id="git_without_subcommand"),
    pytest.param("cat > notes.txt <<'EOF'\nDon't stop.\nEOF", [], id="unbalanced_quote_in_heredoc"),
    pytest.param("/usr/bin/gh pr checkout 5 -b Add_Login", ["Add_Login"], id="gh_by_full_path"),
    pytest.param("git --git-dir=/repo/.git checkout -b Add_Login", ["Add_Login"], id="git_option_as_one_word"),
    # Not read, as the README lists: a push through Claude's Bash commands still meets the pre-push check.
    pytest.param("git checkout --orphan Add_Login", [], id="unread_checkout_orphan"),
    pytest.param("git switch --orphan Add_Login", [], id="unread_switch_orphan"),
    pytest.param("git branch -c main Add_Login", [], id="unread_branch_copy"),
    pytest.param("git branch -C main Add_Login", [], id="unread_branch_force_copy"),
    pytest.param("git branch --copy main Add_Login", [], id="unread_branch_copy_long"),
    pytest.param("git branch --move old-name Add_Login", [], id="unread_branch_move_long"),
    pytest.param("git branch -f Add_Login", [], id="unread_branch_force"),
    pytest.param("git branch --track Add_Login origin/main", [], id="unread_branch_track"),
    pytest.param("git branch -q Add_Login", [], id="unread_branch_quiet"),
    pytest.param("git worktree add ../Add_Login", [], id="unread_worktree_add_named_after_path"),
    pytest.param("git stash branch Add_Login", [], id="unread_stash_branch"),
    pytest.param("git update-ref refs/heads/Add_Login HEAD", [], id="unread_update_ref"),
    pytest.param("git fetch origin main:Add_Login", [], id="unread_fetch_refspec"),
    pytest.param("git switch --create=Add_Login", [], id="unread_joined_long_value"),
    pytest.param("git checkout -bAdd_Login", [], id="unread_joined_short_value"),
    pytest.param("gh pr checkout 5 --branch=Add_Login", [], id="unread_joined_gh_value"),
    pytest.param("git --git-dir /repo/.git checkout -b Add_Login", [], id="unread_git_option_value_as_next_word"),
    pytest.param("git co -b Add_Login", [], id="unread_git_alias"),
    pytest.param("gh pr co 5 -b Add_Login", [], id="unread_gh_alias"),
    pytest.param("sudo -u root git checkout -b Add_Login", [], id="unread_sudo_option"),
    pytest.param("bash -c 'git checkout -b Add_Login'", [], id="unread_bash_c"),
    pytest.param("xargs git checkout -b Add_Login", [], id="unread_xargs"),
])
def test_new_branch_names(cmd, names):
    assert new_branch_names(cmd) == names


def test_main_blocks_unconventional_new_branch():
    assert main(tool_call("git checkout -b Add_Login"), io.StringIO(), io.StringIO()) == 2


def test_main_allows_conventional_new_branch():
    assert main(tool_call("git checkout -b feature/add-login"), io.StringIO(), io.StringIO()) == 0


def test_main_allows_gh_pages_branch():
    """GitHub Pages and the tools that publish to it, such as mkdocs gh-deploy and ghp-import, name this branch, not Claude."""
    assert main(tool_call("git checkout -b gh-pages"), io.StringIO(), io.StringIO()) == 0


def test_main_block_gives_a_reason():
    stderr = io.StringIO()
    main(tool_call("git checkout -b Add_Login"), io.StringIO(), stderr)
    assert "Blocked: branch name Add_Login does not follow Conventional Branch 1.0.0." in stderr.getvalue()


@needs_config_hooks
def test_registered_hook_refuses_push_creating_unconventional_branch(tmp_path):
    repo, remote = repo_with_remote(tmp_path)
    git("-C", repo, "branch", "Bad_Name")
    result = git_in_session(tmp_path, repo, "push", "-q", "origin", "Bad_Name")
    assert result.returncode != 0 and "Rejected: this push would create the remote branch Bad_Name, whose name does not follow Conventional Branch 1.0.0," in result.stderr
    assert remote_branches(remote) == []


@needs_config_hooks
def test_registered_hook_refuses_the_whole_push_naming_each_unconventional_branch(tmp_path):
    """git pushes nothing when the hook refuses, so a conventional branch in the same push stays local too."""
    repo, remote = repo_with_remote(tmp_path)
    for name in ("feature/add-login", "Bad_One", "Bad_Two"):
        git("-C", repo, "branch", name)
    result = git_in_session(tmp_path, repo, "push", "-q", "origin", "feature/add-login", "Bad_One", "Bad_Two")
    assert "Rejected: this push would create the remote branches Bad_One, Bad_Two, whose names do not follow Conventional Branch" in result.stderr
    assert remote_branches(remote) == []


@needs_config_hooks
def test_registered_hook_refusal_says_how_to_rename_the_branch(tmp_path):
    repo, _ = repo_with_remote(tmp_path)
    git("-C", repo, "branch", "Bad_Name")
    stderr = git_in_session(tmp_path, repo, "push", "-q", "origin", "Bad_Name").stderr
    assert "Bad_Name" in stderr and "git branch -m" in stderr


@needs_config_hooks
@pytest.mark.parametrize("shell", ["bash", pytest.param("zsh", marks=needs_zsh)])
def test_registered_hook_runs_from_a_path_with_spaces_and_quotes(tmp_path, shell):
    """The plugin can be installed under such a path; the session's shell must still parse the env file, and git still run the script."""
    scripts = tmp_path / "it's a \"plugin\"" / "scripts"
    shutil.copytree(SCRIPT.parent.parent, scripts, ignore=shutil.ignore_patterns("__pycache__"))  # the rule imports git_hook.py from there
    repo, _ = repo_with_remote(tmp_path)
    git("-C", repo, "branch", "Bad_Name")
    result = git_in_session(tmp_path, repo, "push", "-q", "origin", "Bad_Name", shell=shell, script=scripts / SCRIPT.parent.name / "rule.py")
    assert "Rejected: this push would create the remote branch Bad_Name," in result.stderr


@needs_config_hooks
def test_registered_hook_allows_push_creating_conventional_branch(tmp_path):
    repo, remote = repo_with_remote(tmp_path)
    git("-C", repo, "branch", "feature/add-login")
    assert git_in_session(tmp_path, repo, "push", "-q", "origin", "feature/add-login").returncode == 0
    assert remote_branches(remote) == ["feature/add-login"]


@needs_config_hooks
def test_registered_hook_allows_push_creating_gh_pages(tmp_path):
    """ghp-import, which mkdocs gh-deploy uses, pushes with a plain git push origin gh-pages."""
    repo, remote = repo_with_remote(tmp_path)
    git("-C", repo, "branch", "gh-pages")
    assert git_in_session(tmp_path, repo, "push", "-q", "origin", "gh-pages").returncode == 0
    assert remote_branches(remote) == ["gh-pages"]


@needs_config_hooks
def test_registered_hook_refuses_refspec_creating_unconventional_remote_branch(tmp_path):
    repo, remote = repo_with_remote(tmp_path)
    result = git_in_session(tmp_path, repo, "push", "-q", "origin", "main:Bad")
    assert result.returncode != 0 and "Rejected: this push would create the remote branch Bad," in result.stderr
    assert remote_branches(remote) == []


@needs_config_hooks
@pytest.mark.parametrize("refspec", [pytest.param(["HEAD"], id="head"), pytest.param(["refs/heads/*:refs/heads/*"], id="pattern")])
def test_registered_hook_refuses_push_naming_the_remote_branch_after_the_local_one(tmp_path, refspec):
    """HEAD names the remote branch after the current branch, and the pattern after each local branch."""
    repo, remote = repo_with_remote(tmp_path)
    git("-C", repo, "switch", "-q", "-c", "Bad_Name")
    result = git_in_session(tmp_path, repo, "push", "-q", "origin", *refspec)
    assert result.returncode != 0 and "Rejected: this push would create the remote branch Bad_Name," in result.stderr
    assert remote_branches(remote) == []


@needs_config_hooks
@pytest.mark.parametrize("deletion", [pytest.param([":Bad_Name"], id="empty_src"), pytest.param(["--delete", "Bad_Name"], id="delete_option")])
def test_registered_hook_allows_deleting_unconventional_remote_branch(tmp_path, deletion):
    repo, remote = repo_with_remote(tmp_path)
    git("-C", repo, "push", "-q", "--no-verify", "origin", "main:Bad_Name")
    assert git_in_session(tmp_path, repo, "push", "-q", "origin", *deletion).returncode == 0
    assert remote_branches(remote) == []


@needs_config_hooks
def test_registered_hook_allows_deleting_a_remote_branch_already_gone(tmp_path):
    """git passes all-zero objects on both sides for it, which is not a new branch."""
    repo, _ = repo_with_remote(tmp_path)
    assert git_in_session(tmp_path, repo, "push", "-q", "origin", ":refs/heads/Bad_Gone").returncode == 0


@needs_config_hooks
def test_registered_hook_allows_pushing_a_ref_outside_refs_heads(tmp_path):
    repo, remote = repo_with_remote(tmp_path)
    assert git_in_session(tmp_path, repo, "push", "-q", "origin", "main:refs/custom/Bad_Name").returncode == 0
    assert git("-C", remote, "for-each-ref", "--format=%(refname)", "refs/custom/").split() == ["refs/custom/Bad_Name"]


@needs_config_hooks
def test_repository_pre_push_hook_still_runs_after_a_refusal(tmp_path):
    """The README says git still runs the repository's own pre-push hook after this one, even when this one refuses the push."""
    repo, _ = repo_with_remote(tmp_path)
    ran = tmp_path / "repository-hook-ran"
    repository_hook = repo / ".git" / "hooks" / "pre-push"
    repository_hook.write_text(f"#!/bin/sh\ntouch '{ran}'\n")
    repository_hook.chmod(0o755)
    git("-C", repo, "branch", "Bad_Name")
    # GIT_TRACE logs each hook git runs, in order.
    result = run_in_session(tmp_path, SCRIPT, "env", "GIT_TRACE=1", "git", "-C", repo, "push", "-q", "origin", "Bad_Name")
    hooks_run = [line for line in result.stderr.splitlines() if "trace: run_command:" in line and "pre-push" in line]
    assert result.returncode != 0 and ran.exists()
    assert [str(SCRIPT) in hooks_run[0], ".git/hooks/pre-push" in hooks_run[-1]] == [True, True]


@needs_config_hooks
@pytest.mark.parametrize("command", [
    pytest.param(lambda repo, remote: ["git", "-C", repo, "push", "-q", "--no-verify", "origin", "Bad_Name"], id="no_verify"),
    pytest.param(lambda repo, remote: ["git", "-C", repo, "send-pack", remote, "Bad_Name"], id="send_pack"),
    pytest.param(lambda repo, remote: ["git", "-C", repo, "-c", "hook.conventional-branch.enabled=false", "push", "-q", "origin", "Bad_Name"], id="enabled_false"),
    pytest.param(lambda repo, remote: ["git", "-C", repo, "-c", "hook.conventional-branch.event=", "push", "-q", "origin", "Bad_Name"], id="empty_event"),
    pytest.param(lambda repo, remote: ["env", "GIT_CONFIG_COUNT=0", "git", "-C", repo, "push", "-q", "origin", "Bad_Name"], id="git_config_count_0"),
    pytest.param(lambda repo, remote: ["env", "-i", f"PATH={os.environ['PATH']}", "git", "-C", repo, "push", "-q", "origin", "Bad_Name"], id="env_i"),
])
def test_ways_past_the_pre_push_check_the_readme_lists(tmp_path, command):
    """Each command gets an unconventional branch onto the remote despite the registered hook, as the README's Not checked list says."""
    repo, remote = repo_with_remote(tmp_path)
    git("-C", repo, "branch", "Bad_Name")
    assert run_in_session(tmp_path, SCRIPT, *command(repo, remote)).returncode == 0
    assert remote_branches(remote) == ["Bad_Name"]


@needs_config_hooks
def test_repository_config_can_turn_the_pre_push_check_off(tmp_path):
    """The README lists a repository's or user's hook.conventional-branch.enabled false among the ways past the check."""
    repo, remote = repo_with_remote(tmp_path)
    git("-C", repo, "config", "hook.conventional-branch.enabled", "false")
    git("-C", repo, "branch", "Bad_Name")
    assert git_in_session(tmp_path, repo, "push", "-q", "origin", "Bad_Name").returncode == 0
    assert remote_branches(remote) == ["Bad_Name"]


@needs_config_hooks
def test_registered_hook_allows_pushing_a_tag(tmp_path):
    repo, remote = repo_with_remote(tmp_path)
    git("-C", repo, "tag", "V1.0")
    assert git_in_session(tmp_path, repo, "push", "-q", "origin", "V1.0").returncode == 0
    assert git("-C", remote, "tag").split() == ["V1.0"]


@needs_config_hooks
def test_registered_hook_allows_updating_existing_remote_branch(tmp_path):
    repo, remote = repo_with_remote(tmp_path)
    git("-C", repo, "push", "-q", "--no-verify", "origin", "main:Bad_Name")
    git("-C", repo, "commit", "--allow-empty", "-q", "-m", "feat: continue")
    assert git_in_session(tmp_path, repo, "push", "-q", "origin", "main:Bad_Name").returncode == 0
    assert git("-C", remote, "rev-parse", "Bad_Name") == git("-C", repo, "rev-parse", "main")


def test_pre_push_reads_a_local_ref_typed_with_spaces(tmp_path):
    """git passes the local ref as typed, such as HEAD@{0 seconds ago}, so a line can hold more than four words."""
    push_line = f"HEAD@{{0 seconds ago}} {'4' * 40} refs/heads/Bad {'0' * 40}\n"
    result = subprocess.run([SCRIPT, "pre-push", "origin", tmp_path / "remote.git"], input=push_line, capture_output=True, text=True)
    assert result.returncode == 1 and "Rejected: this push would create the remote branch Bad," in result.stderr


@needs_config_hooks
def test_registration_cut_short_leaves_git_working(tmp_path):
    """A shell can stop partway through the env file, such as at a line it cannot parse; what it has counted by then must leave git working."""
    repo, remote = repo_with_remote(tmp_path)
    git("-C", repo, "branch", "feature/add-login")
    env_file = start_session(tmp_path / "session.env", SCRIPT)
    env_file.write_text("".join(env_file.read_text().splitlines(keepends=True)[:2]))  # the first entry, and the count that takes it in
    result = subprocess.run(
        ["bash", "-c", '. "$1" && shift && git -C "$@"', "_", env_file, repo, "push", "-q", "origin", "feature/add-login"],
        env=GIT_ENV,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert remote_branches(remote) == ["feature/add-login"]


def test_session_start_without_env_file_tells_claude_the_push_check_is_inactive():
    """Claude Code gives no CLAUDE_ENV_FILE to a SessionStart hook run in PowerShell, so there is nowhere to register the hook.

    Claude Code adds a SessionStart hook's stdout at exit 0 to Claude's context; Claude never sees its stderr.
    """
    env = {name: value for name, value in os.environ.items() if name != "CLAUDE_ENV_FILE"}
    result = subprocess.run([SCRIPT], input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}), env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) == 1 and "not active" in result.stdout


@pytest.mark.parametrize("shell", ["bash", pytest.param("zsh", marks=needs_zsh)])
@pytest.mark.parametrize("branch_rule_first", [False, True], ids=["commit_rule_first", "branch_rule_first"])
def test_both_git_rules_register_beside_existing_git_config(tmp_path, shell, branch_rule_first):
    """Claude Code runs both rules' SessionStart hooks, each with its own env file, and sources the files one after another in every Bash command."""
    env_files = [start_session(tmp_path / f"{rule.parent.name}.env", rule) for rule in (COMMIT_MESSAGE_RULE, SCRIPT)]
    if branch_rule_first:
        env_files.reverse()
    result = subprocess.run(
        [shell, "-c", '. "$1" && . "$2" && git config --list --show-scope', "_", *env_files], env={**GIT_ENV, **EXISTING_GIT_CONFIG}, capture_output=True, text=True
    )
    assert sorted(line for line in result.stdout.splitlines() if line.startswith("command\t")) == sorted([
        "command\ttest.kept=yes",
        "command\thook.conventional-commits.event=commit-msg",
        f"command\thook.conventional-commits.command={shlex.quote(str(COMMIT_MESSAGE_RULE))}",
        "command\thook.conventional-branch.event=pre-push",
        f"command\thook.conventional-branch.command={shlex.quote(str(SCRIPT))} pre-push",
    ])
