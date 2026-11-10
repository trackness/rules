"""Tests for "Work only on a branch". Run from the repo root: uv run pytest"""
import os
import subprocess

from .rule import off_a_work_branch

# git in the tests reads none of the user's config, global, system or in the environment, such as a global core.hooksPath, and commits as a test identity.
GIT_ENV = {
    **{name: value for name, value in os.environ.items() if not name.startswith("GIT_CONFIG")}, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com", "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com",
}


def git(*args):
    """Run git with the given arguments for a test's setup, and return its output."""
    return subprocess.run(["git", *map(str, args)], env=GIT_ENV, check=True, capture_output=True, text=True).stdout


def repo_on(tmp_path, branch):
    """A new repo with one commit, on the given branch."""
    repo = tmp_path / "repo"
    git("init", "-q", "-b", branch, repo)
    git("-C", repo, "commit", "--allow-empty", "-q", "-m", "feat: start")
    return repo


def test_a_repository_on_main_is_off_a_work_branch(tmp_path):
    assert off_a_work_branch(repo_on(tmp_path, "main")) == "on main"


def test_a_repository_on_master_is_off_a_work_branch(tmp_path):
    assert off_a_work_branch(repo_on(tmp_path, "master")) == "on master"


def test_a_directory_outside_any_repository_is_not_off_a_work_branch(tmp_path):
    assert off_a_work_branch(tmp_path) is None


def test_a_repository_on_a_work_branch_is_not_off_a_work_branch(tmp_path):
    assert off_a_work_branch(repo_on(tmp_path, "feature/add-login")) is None
