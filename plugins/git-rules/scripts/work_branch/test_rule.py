"""Tests for "Work only on a branch". Run from the repo root: uv run pytest"""
import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ..git_testing import GIT_ENV, git, needs_config_hooks, run_in_session
from .rule import main, off_a_work_branch

SCRIPT = Path(__file__).resolve().parent / "rule.py"


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


def commit_notes(repo, text):
    """Commit notes.txt holding text on the branch checked out in repo."""
    (repo / "notes.txt").write_text(text)
    git("-C", repo, "add", "notes.txt")
    git("-C", repo, "commit", "-q", "-m", "feat: add notes")


def branches_that_conflict(tmp_path):
    """A new repo on main, where main and feature/add-login each add notes.txt with different text, so bringing one onto the other stops at a conflict."""
    repo = repo_on(tmp_path, "main")
    git("-C", repo, "switch", "-q", "-c", "feature/add-login")
    commit_notes(repo, "login\n")
    git("-C", repo, "switch", "-q", "main")
    commit_notes(repo, "logout\n")
    return repo


def rebase_with_its_conflict_resolved(tmp_path, branch, *options):
    """A new repo where git rebases branch onto the other of main and feature/add-login, stopped at the conflict in notes.txt, now resolved and staged."""
    repo = branches_that_conflict(tmp_path)
    git("-C", repo, "switch", "-q", branch)
    onto = "feature/add-login" if branch == "main" else "main"
    stopped = subprocess.run(["git", "-C", repo, "rebase", "-q", *options, onto], env=GIT_ENV, capture_output=True)
    assert stopped.returncode != 0 and git("-C", repo, "branch", "--show-current") == ""
    (repo / "notes.txt").write_text("login\nlogout\n")
    git("-C", repo, "add", "notes.txt")
    return repo


def git_in_session(tmp_path, repo, *args, script=SCRIPT):
    """Start a session, then run git in repo with the given arguments as Claude's Bash tool would, with the env file sourced."""
    return run_in_session(tmp_path, script, "git", "-C", repo, *args)


def commits(repo):
    """The number of commits on the branch checked out in repo."""
    return int(git("-C", repo, "rev-list", "--count", "HEAD"))


def tool_call(file_path):
    """An Edit tool call as Claude Code sends it to the hook on stdin."""
    tool_input = {"file_path": str(file_path), "old_string": "old text", "new_string": "new text"}
    # Claude Code writes a character such as é as it is, not as a \u escape.
    return io.StringIO(json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": tool_input}, ensure_ascii=False))


def test_a_repository_on_main_is_off_a_work_branch(tmp_path):
    assert off_a_work_branch(repo_on(tmp_path, "main")) == "on main"


def test_a_repository_on_master_is_off_a_work_branch(tmp_path):
    assert off_a_work_branch(repo_on(tmp_path, "master")) == "on master"


def test_a_repository_on_develop_is_off_a_work_branch(tmp_path):
    assert off_a_work_branch(repo_on(tmp_path, "develop")) == "on develop"


def test_a_repository_on_main_in_another_case_is_off_a_work_branch(tmp_path):
    """On a case-insensitive disk, such as macOS's by default, git checkout MAIN checks out main but names the branch MAIN."""
    assert off_a_work_branch(repo_on(tmp_path, "MAIN")) == "on MAIN"


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


@pytest.mark.parametrize("branch", ["feature/add-login", "main"])
def test_a_repository_git_is_rebasing_is_not_off_a_work_branch(tmp_path, branch):
    """git detaches HEAD while it rebases a branch, and resolving a conflict then means changing files."""
    repo = repo_on(tmp_path, branch)
    stop_in_a_rebase(repo)
    assert off_a_work_branch(repo) is None


def test_a_repository_git_is_rebasing_in_a_directory_with_a_space_in_its_name_is_not_off_a_work_branch(tmp_path):
    (tmp_path / "my projects").mkdir()
    repo = repo_on(tmp_path / "my projects", "feature/add-login")
    stop_in_a_rebase(repo)
    assert off_a_work_branch(repo) is None


def test_a_repository_git_is_rebasing_by_applying_patches_is_not_off_a_work_branch(tmp_path):
    """git rebase --apply keeps the rebase's state in another directory than a rebase without it."""
    repo = branches_that_conflict(tmp_path)
    git("-C", repo, "switch", "-q", "feature/add-login")
    stopped = subprocess.run(["git", "-C", repo, "rebase", "-q", "--apply", "main"], env=GIT_ENV, capture_output=True)
    assert stopped.returncode != 0 and git("-C", repo, "branch", "--show-current") == ""
    assert off_a_work_branch(repo) is None


@pytest.mark.parametrize("command", [
    pytest.param(["merge"], id="merge"),
    pytest.param(["cherry-pick"], id="cherry_pick"),
    pytest.param(["revert", "--no-edit"], id="revert"),
])
def test_a_repository_on_main_where_git_stopped_at_a_conflict_is_not_off_a_work_branch(tmp_path, command):
    """git stops a merge, cherry-pick or revert at a conflict with main still checked out, and resolving the conflict means changing files."""
    repo = branches_that_conflict(tmp_path)
    stopped = subprocess.run(["git", "-C", repo, *command, "feature/add-login"], env=GIT_ENV, capture_output=True)
    assert stopped.returncode != 0 and git("-C", repo, "branch", "--show-current") == "main\n"
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


def test_main_allows_edit_of_a_file_in_the_git_directory_of_a_repository_on_main(tmp_path):
    """A file in the git directory, such as .git/info/exclude, which ignores files in this one clone, is on no branch."""
    repo = repo_on(tmp_path, "main")
    assert main(tool_call(repo / ".git" / "info" / "exclude"), io.StringIO(), io.StringIO()) == 0


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


def test_the_script_run_as_a_hook_reads_a_path_holding_a_non_ascii_character_whatever_pythonioencoding_says(tmp_path):
    """Claude Code writes the tool call in UTF-8, where Python reads stdin in the encoding PYTHONIOENCODING names, such as Latin-1."""
    (tmp_path / "café").mkdir()
    repo = repo_on(tmp_path / "café", "main")
    env = {**GIT_ENV, "PYTHONIOENCODING": "latin-1"}
    result = subprocess.run([SCRIPT], input=tool_call(repo / "notes.md").getvalue().encode(), env=env, capture_output=True)
    assert result.returncode == 2


@needs_config_hooks
def test_registered_hook_rejects_commit_in_a_repository_on_main(tmp_path):
    repo = repo_on(tmp_path, "main")
    result = git_in_session(tmp_path, repo, "commit", "--allow-empty", "-q", "-m", "feat: continue")
    assert result.returncode != 0 and commits(repo) == 1


@needs_config_hooks
def test_registered_hook_tells_claude_why_a_commit_in_a_repository_on_main_is_rejected(tmp_path):
    repo = repo_on(tmp_path, "main")
    result = git_in_session(tmp_path, repo, "commit", "--allow-empty", "-q", "-m", "feat: continue")
    assert result.stderr == (
        "Rejected: work happens only on a branch, and this repository is on main, so nothing was committed. "
        "Create a branch with git switch -c <type>/<description>, which keeps the changes, and commit there.\n"
    )


@needs_config_hooks
def test_registered_hook_tells_claude_when_the_repository_is_on_a_detached_head(tmp_path):
    repo = repo_on(tmp_path, "feature/add-login")
    git("-C", repo, "switch", "-q", "--detach")
    result = git_in_session(tmp_path, repo, "commit", "--allow-empty", "-q", "-m", "feat: continue")
    assert "this repository is on a detached HEAD," in result.stderr


@needs_config_hooks
def test_registered_hook_accepts_commit_on_a_work_branch(tmp_path):
    repo = repo_on(tmp_path, "feature/add-login")
    result = git_in_session(tmp_path, repo, "commit", "--allow-empty", "-q", "-m", "feat: continue")
    assert result.returncode == 0 and commits(repo) == 2


@needs_config_hooks
def test_registered_hook_accepts_the_commit_that_finishes_a_merge_stopped_at_a_conflict_on_main(tmp_path):
    """git switch -c refuses to run in the middle of a merge, so the merge cannot be carried onto a branch and finished there."""
    repo = branches_that_conflict(tmp_path)
    subprocess.run(["git", "-C", repo, "merge", "-q", "feature/add-login"], env=GIT_ENV, capture_output=True)
    (repo / "notes.txt").write_text("login\nlogout\n")
    git("-C", repo, "add", "notes.txt")
    result = git_in_session(tmp_path, repo, "commit", "-q", "--no-edit")
    assert result.returncode == 0 and commits(repo) == 4


@needs_config_hooks
@pytest.mark.parametrize("options", [pytest.param([], id="merge"), pytest.param(["--apply"], id="apply")])
def test_registered_hook_rejects_a_commit_while_git_rebases_main(tmp_path, options):
    """A commit made during a rebase lands on the branch rebased, here main."""
    repo = rebase_with_its_conflict_resolved(tmp_path, "main", *options)
    result = git_in_session(tmp_path, repo, "commit", "-q", "-m", "feat: more")
    assert result.returncode != 0 and result.stderr == (
        "Rejected: work happens only on a branch, and this repository is rebasing main, so nothing was committed. "
        "Finish the rebase with git rebase --continue, then create a branch with git switch -c <type>/<description>, which keeps the changes, and commit there.\n"
    )


@needs_config_hooks
@pytest.mark.parametrize("options", [pytest.param([], id="merge"), pytest.param(["--apply"], id="apply")])
def test_registered_hook_lets_git_rebase_continue_finish_a_rebase_of_main(tmp_path, options):
    """git rebase --continue, which the rejection above asks for, commits without running the pre-commit hook."""
    repo = rebase_with_its_conflict_resolved(tmp_path, "main", *options)
    result = run_in_session(tmp_path, SCRIPT, "env", "GIT_EDITOR=true", "git", "-C", repo, "rebase", "--continue")
    assert result.returncode == 0, result.stderr
    assert git("-C", repo, "branch", "--show-current") == "main\n"


@needs_config_hooks
def test_registered_hook_accepts_a_commit_while_git_rebases_a_work_branch(tmp_path):
    repo = rebase_with_its_conflict_resolved(tmp_path, "feature/add-login")
    assert git_in_session(tmp_path, repo, "commit", "-q", "-m", "feat: more").returncode == 0


@needs_config_hooks
def test_registered_hook_runs_from_a_path_with_spaces_and_quotes(tmp_path):
    """The plugin can be installed under such a path; the session's shell must still parse the env file, and git still run the script."""
    scripts = tmp_path / "it's a \"plugin\"" / "scripts"
    shutil.copytree(SCRIPT.parent.parent, scripts, ignore=shutil.ignore_patterns("__pycache__"))  # the rule imports git_hook.py from there
    repo = repo_on(tmp_path, "main")
    result = git_in_session(tmp_path, repo, "commit", "--allow-empty", "-q", "-m", "feat: continue", script=scripts / SCRIPT.parent.name / "rule.py")
    assert result.stderr.startswith("Rejected: work happens only on a branch")


def test_session_start_without_an_env_file_tells_claude_the_commit_check_is_not_active():
    """A SessionStart hook run without a CLAUDE_ENV_FILE has nowhere to register the git hook.

    Claude Code adds a SessionStart hook's stdout at exit 0 to Claude's context; Claude never sees its stderr.
    """
    env = {name: value for name, value in GIT_ENV.items() if name != "CLAUDE_ENV_FILE"}
    result = subprocess.run([SCRIPT], input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}), env=env, capture_output=True, text=True)
    assert result.returncode == 0 and "not active" in result.stdout
