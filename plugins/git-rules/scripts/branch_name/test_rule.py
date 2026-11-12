"""Tests for "Conventional Branch names". Run from the repo root: uv run pytest"""
import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ..git_testing import GIT_ENV, git, needs_config_hooks, needs_zsh, run_in_session
from .rule import NAMING, conventional, main, new_branch_names

SCRIPT = Path(__file__).resolve().parent / "rule.py"


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
    pytest.param("release/v1..2", id="two_dots_in_a_row"),
    pytest.param("feature/new--login", id="two_hyphens_in_a_row"),
    pytest.param("feature/-new-login", id="leading_hyphen"),
    pytest.param("feature/auth/login", id="slash_in_description"),
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
    pytest.param("git switch --force-create Add_Login", ["Add_Login"], id="switch_force_create"),
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
    pytest.param("gh pr checkout 5 -b Add_Login", ["Add_Login"], id="gh_pr_checkout_b"),
    pytest.param("gh pr checkout 5 --branch Add_Login", ["Add_Login"], id="gh_pr_checkout_branch"),
    pytest.param("gh pr checkout 5", [], id="gh_pr_checkout_own_branch"),
    pytest.param("ls -la", [], id="not_git"),
    pytest.param("git --version", [], id="git_without_subcommand"),
    pytest.param("cat > notes.txt <<'EOF'\nDon't stop.\nEOF", [], id="unbalanced_quote_in_heredoc"),
    pytest.param("/usr/bin/gh pr checkout 5 -b Add_Login", ["Add_Login"], id="gh_by_full_path"),
    pytest.param("git --git-dir=/repo/.git checkout -b Add_Login", ["Add_Login"], id="git_option_as_one_word"),
    pytest.param("cd /repo && git checkout -b Add_Login", ["Add_Login"], id="after_and"),
    pytest.param("git status; git checkout -b Add_Login", ["Add_Login"], id="after_semicolon"),
    pytest.param("git status\ngit checkout -b Add_Login", ["Add_Login"], id="on_a_second_line"),
    pytest.param("(git checkout -b Add_Login)", ["Add_Login"], id="in_a_subshell"),
    pytest.param("git branch -m Add_Login && git checkout main", ["Add_Login"], id="rename_before_another_command"),
    pytest.param("git checkout \\\n  -b Add_Login", ["Add_Login"], id="continued_on_the_next_line"),
    pytest.param("git checkout 2>/dev/null -b Add_Login", ["Add_Login"], id="options_after_a_redirection"),
    pytest.param("# make the branch\ngit checkout -b Add_Login", ["Add_Login"], id="after_a_comment_line"),
    pytest.param("git branch 2>&1", [], id="branch_list_redirected_to_a_file_descriptor"),
    pytest.param("git branch > branches.txt", [], id="branch_list_redirected_to_a_file"),
    pytest.param("git branch | grep feature", [], id="branch_list_piped"),
    pytest.param("git branch -D old && git commit -m 'feat: thing'", [], id="option_of_a_later_command"),
    pytest.param("git checkout main && gh pr create -B main -b 'Fixes the bug'", [], id="gh_option_of_a_later_command"),
    pytest.param("git checkout -b feature/add-login # the -b flag makes it", ["feature/add-login"], id="comment_after_the_command"),
    pytest.param("git checkout -b feature/add-login # made here\ngit branch Add_Login", ["feature/add-login", "Add_Login"], id="line_after_a_comment"),
    # A limit the README lists: a line of a heredoc's body is read as a command, even with the delimiter quoted.
    pytest.param("cat <<'EOF'\ngit branch Add_Login\nEOF", ["Add_Login"], id="line_in_a_heredoc"),
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
    pytest.param("git commit -m '#12 fix' && git checkout -b Add_Login", [], id="unread_after_a_quoted_word_starting_with_hash"),
    pytest.param("if true; then git checkout -b Add_Login; fi", [], id="unread_after_a_shell_keyword"),
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


@pytest.mark.parametrize("cmd", [
    pytest.param("git push origin HEAD:Bad_Name", id="new_branch_by_refspec"),
    pytest.param("git push -u origin local-name:refs/heads/Add_Login", id="new_branch_by_full_ref"),
    pytest.param("git push origin HEAD:dependabot/npm_and_yarn/lodash-4.17.21", id="existing_branch_by_refspec"),
    pytest.param("git push origin v1.2.0:v1.2.0", id="tag_by_refspec"),
    pytest.param("git push origin +:Add_Login", id="forced_deletion"),
    pytest.param("git push --repo origin git@github.com:Owner/Repo.git", id="repository_after_repo_option"),
])
def test_main_leaves_every_push_to_the_pre_push_check(cmd):
    """Only git sees whether the remote branch already exists, so the registered hook, tested below, judges pushes."""
    assert main(tool_call(cmd), io.StringIO(), io.StringIO()) == 0


def test_main_block_gives_a_reason():
    stderr = io.StringIO()
    main(tool_call("git checkout -b Add_Login"), io.StringIO(), stderr)
    assert stderr.getvalue() == f"Blocked: branch name Add_Login does not follow Conventional Branch 1.0.0. {NAMING}\n"


def test_script_reads_its_input_as_utf_8_whatever_pythonioencoding_says():
    """Claude Code sends UTF-8, which Python would decode with the encoding PYTHONIOENCODING names, here ASCII, and fail with exit 1, which blocks nothing."""
    hook_input = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git checkout -b Café"}}, ensure_ascii=False)
    result = subprocess.run([SCRIPT], input=hook_input.encode(), env={**GIT_ENV, "PYTHONIOENCODING": "ascii"}, capture_output=True)
    assert result.returncode == 2, result.stderr


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
])
def test_ways_past_the_pre_push_check_the_readme_lists(tmp_path, command):
    """Each command gets an unconventional branch onto the remote despite the registered hook, as the README's Not checked list says.

    The ways past every git rule, such as turning the hook off by its name, are tested once, in test_git_hook.py.
    """
    repo, remote = repo_with_remote(tmp_path)
    git("-C", repo, "branch", "Bad_Name")
    assert run_in_session(tmp_path, SCRIPT, *command(repo, remote)).returncode == 0
    assert remote_branches(remote) == ["Bad_Name"]


@needs_config_hooks
@pytest.mark.parametrize("refspec", [pytest.param("V1.0", id="by_name"), pytest.param("V1.0:V1.0", id="by_refspec")])
def test_registered_hook_allows_pushing_a_tag(tmp_path, refspec):
    """git takes the <dst> of V1.0:V1.0 as a tag, since its <src> is one."""
    repo, remote = repo_with_remote(tmp_path)
    git("-C", repo, "tag", "V1.0")
    assert git_in_session(tmp_path, repo, "push", "-q", "origin", refspec).returncode == 0
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


def test_session_start_without_env_file_tells_claude_the_push_check_is_inactive():
    """A SessionStart hook run without a CLAUDE_ENV_FILE has nowhere to register the git hook.

    Claude Code adds a SessionStart hook's stdout at exit 0 to Claude's context; Claude never sees its stderr.
    """
    env = {name: value for name, value in GIT_ENV.items() if name != "CLAUDE_ENV_FILE"}
    result = subprocess.run([SCRIPT], input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}), env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) == 1 and "not active" in result.stdout
