"""Tests for scripts/branch_name.py. Run from the repo root: uv run pytest"""
import io
import json

import pytest

from scripts.branch_name import conventional, main, new_branch_names


def tool_call(cmd):
    """A Bash tool call as Claude Code sends it to the hook on stdin."""
    return io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}))


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
    pytest.param("release/v1.2.0", id="release_version"),
    pytest.param("main", id="main"),
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
    pytest.param("ls -la", [], id="not_git"),
    pytest.param("git --version", [], id="git_without_subcommand"),
    pytest.param("cat > notes.txt <<'EOF'\nDon't stop.\nEOF", [], id="unbalanced_quote_in_heredoc"),
])
def test_new_branch_names(cmd, names):
    assert new_branch_names(cmd) == names


def test_main_blocks_unconventional_new_branch():
    assert main(tool_call("git checkout -b Add_Login"), io.StringIO()) == 2


def test_main_allows_conventional_new_branch():
    assert main(tool_call("git checkout -b feature/add-login"), io.StringIO()) == 0


def test_main_block_gives_a_reason():
    stderr = io.StringIO()
    main(tool_call("git checkout -b Add_Login"), stderr)
    assert stderr.getvalue().strip() != ""
