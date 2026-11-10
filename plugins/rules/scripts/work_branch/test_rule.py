"""Tests for "Work only on a branch". Run from the repo root: uv run pytest"""
import io
import json
import os
import subprocess
from pathlib import Path

from .rule import main, off_a_work_branch

SCRIPT = Path(__file__).resolve().parent / "rule.py"

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


def stop_in_a_rebase(repo):
    """Leave git rebasing the branch checked out in repo, stopped partway, as at a conflict."""
    git("-C", repo, "commit", "--allow-empty", "-q", "-m", "feat: continue")
    # The command false fails once the commit is replayed, which stops the rebase there.
    stopped = subprocess.run(["git", "-C", repo, "rebase", "-q", "--exec", "false", "HEAD~1"], env=GIT_ENV, capture_output=True)
    assert stopped.returncode != 0


def tool_call(file_path):
    """An Edit tool call as Claude Code sends it to the hook on stdin."""
    tool_input = {"file_path": str(file_path), "old_string": "old text", "new_string": "new text"}
    return io.StringIO(json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": tool_input}))


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
    stop_in_a_rebase(repo)
    assert off_a_work_branch(repo) is None


def test_a_repository_git_is_rebasing_in_a_directory_with_a_space_in_its_name_is_not_off_a_work_branch(tmp_path):
    (tmp_path / "my projects").mkdir()
    repo = repo_on(tmp_path / "my projects", "feature/add-login")
    stop_in_a_rebase(repo)
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


def test_main_blocks_edit_in_a_repository_on_main(tmp_path):
    repo = repo_on(tmp_path, "main")
    assert main(tool_call(repo / "notes.md"), io.StringIO(), io.StringIO()) == 2


def test_main_tells_claude_why_an_edit_in_a_repository_on_main_is_blocked(tmp_path):
    repo = repo_on(tmp_path, "main")
    stderr = io.StringIO()
    main(tool_call(repo / "notes.md"), io.StringIO(), stderr)
    assert stderr.getvalue() == (
        "Blocked: work happens only on a branch, and this file's repository is on main. "
        "Create a branch with git switch -c <type>/<description>, then make the change there.\n"
    )


def test_main_tells_claude_when_the_repository_is_on_a_detached_head(tmp_path):
    repo = repo_on(tmp_path, "feature/add-login")
    git("-C", repo, "switch", "-q", "--detach")
    stderr = io.StringIO()
    main(tool_call(repo / "notes.md"), io.StringIO(), stderr)
    assert "this file's repository is on a detached HEAD." in stderr.getvalue()


def test_main_blocks_new_file_in_a_directory_that_does_not_exist_yet(tmp_path):
    """Write makes the directories a new file needs, so the file's own directory may not exist when the hook runs."""
    repo = repo_on(tmp_path, "main")
    assert main(tool_call(repo / "docs" / "guide" / "notes.md"), io.StringIO(), io.StringIO()) == 2


def test_main_allows_edit_of_a_file_git_ignores_in_a_repository_on_main(tmp_path):
    """A file git ignores, such as Claude Code's local settings, is on no branch."""
    repo = repo_on(tmp_path, "main")
    (repo / ".gitignore").write_text(".claude/settings.local.json\n")
    assert main(tool_call(repo / ".claude" / "settings.local.json"), io.StringIO(), io.StringIO()) == 0


def test_main_allows_edit_in_a_worktree_on_a_work_branch_while_the_session_is_in_a_checkout_on_main(tmp_path, monkeypatch):
    """The hook goes by the checkout that holds the file, not by the session's working directory."""
    repo = repo_on(tmp_path, "main")
    git("-C", repo, "worktree", "add", "-q", "-b", "feature/add-login", tmp_path / "worktree")
    monkeypatch.chdir(repo)
    assert main(tool_call(tmp_path / "worktree" / "notes.md"), io.StringIO(), io.StringIO()) == 0


def test_the_script_run_as_a_hook_blocks_an_edit_in_a_repository_on_main(tmp_path):
    """Claude Code passes the tool call on stdin, and takes exit code 2 as a block."""
    repo = repo_on(tmp_path, "main")
    result = subprocess.run([SCRIPT], input=tool_call(repo / "notes.md").getvalue(), capture_output=True, text=True)
    assert result.returncode == 2


def test_the_script_run_as_a_hook_blocks_a_notebook_edit_in_a_repository_on_main(tmp_path):
    """NotebookEdit names its file notebook_path, where Edit and Write say file_path."""
    repo = repo_on(tmp_path, "main")
    tool_input = {"notebook_path": str(repo / "analysis.ipynb"), "cell_id": "cell-1", "new_source": "print(1)"}
    notebook_edit = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "NotebookEdit", "tool_input": tool_input})
    result = subprocess.run([SCRIPT], input=notebook_edit, capture_output=True, text=True)
    assert result.returncode == 2
