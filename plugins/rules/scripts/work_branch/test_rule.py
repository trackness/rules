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


def test_a_repository_on_develop_is_off_a_work_branch(tmp_path):
    assert off_a_work_branch(repo_on(tmp_path, "develop")) == "on develop"


def test_a_repository_on_a_detached_head_is_off_a_work_branch(tmp_path):
    repo = repo_on(tmp_path, "feature/add-login")
    git("-C", repo, "switch", "-q", "--detach")
    assert off_a_work_branch(repo) == "on a detached HEAD"


def test_a_directory_outside_any_repository_is_not_off_a_work_branch(tmp_path):
    assert off_a_work_branch(tmp_path) is None


def test_a_repository_on_a_work_branch_is_not_off_a_work_branch(tmp_path):
    assert off_a_work_branch(repo_on(tmp_path, "feature/add-login")) is None


def test_a_repository_with_no_commits_is_not_off_a_work_branch(tmp_path):
    """A new repository has no main to branch from yet, so its first commit is made on main."""
    git("init", "-q", "-b", "main", tmp_path / "repo")
    assert off_a_work_branch(tmp_path / "repo") is None


def test_a_repository_git_is_rebasing_is_not_off_a_work_branch(tmp_path):
    """git detaches HEAD while it rebases a branch, and resolving a conflict then means changing files."""
    repo = repo_on(tmp_path, "feature/add-login")
    git("-C", repo, "commit", "--allow-empty", "-q", "-m", "feat: continue")
    # The command false fails once the commit is replayed, which stops the rebase there, as a conflict would.
    stopped = subprocess.run(["git", "-C", repo, "rebase", "-q", "--exec", "false", "HEAD~1"], env=GIT_ENV, capture_output=True)
    assert stopped.returncode != 0
    assert off_a_work_branch(repo) is None


def test_a_repository_git_is_rebasing_in_a_directory_with_a_space_in_its_name_is_not_off_a_work_branch(tmp_path):
    (tmp_path / "my projects").mkdir()
    repo = repo_on(tmp_path / "my projects", "feature/add-login")
    git("-C", repo, "commit", "--allow-empty", "-q", "-m", "feat: continue")
    stopped = subprocess.run(["git", "-C", repo, "rebase", "-q", "--exec", "false", "HEAD~1"], env=GIT_ENV, capture_output=True)
    assert stopped.returncode != 0
    assert off_a_work_branch(repo) is None


def test_a_repository_git_is_rebasing_by_applying_patches_is_not_off_a_work_branch(tmp_path):
    """git rebase --apply keeps the rebase's state in another directory than a rebase without it."""
    repo = repo_on(tmp_path, "main")

    def commit_notes(text):
        (repo / "notes.txt").write_text(text)
        git("-C", repo, "add", "notes.txt")
        git("-C", repo, "commit", "-q", "-m", "feat: add notes")

    git("-C", repo, "switch", "-q", "-c", "feature/add-login")
    commit_notes("login\n")
    git("-C", repo, "switch", "-q", "main")
    commit_notes("logout\n")
    git("-C", repo, "switch", "-q", "feature/add-login")
    # Both branches add notes.txt with different text, so the rebase stops at the conflict.
    stopped = subprocess.run(["git", "-C", repo, "rebase", "-q", "--apply", "main"], env=GIT_ENV, capture_output=True)
    assert stopped.returncode != 0 and git("-C", repo, "branch", "--show-current") == ""
    assert off_a_work_branch(repo) is None
