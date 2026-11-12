# Work only on a branch

Keeps Claude's work on a branch with two checks: one on each Edit, Write and NotebookEdit call, which blocks a change to a file whose repository is not on a work branch before the change is made, and one in git's `pre-commit` hook, which rejects a commit made there.

A repository is on a work branch when the branch checked out has any name but main, master or develop, in any case, such as MAIN. A detached HEAD is on no branch, so it is not on a work branch either. Three states are let through:

- a repository with no commits yet, which has no main to branch from, so its first commit is made on main
- a rebase in progress, with or without `--apply`, during which git detaches HEAD, so that a conflict can still be resolved and the rebase continued
- a merge, cherry-pick or revert stopped at a conflict on main, master or develop, during which `git switch -c` refuses to run, so that the conflict can still be resolved and the commit that finishes it made

## File changes

Blocks an Edit, Write or NotebookEdit call for a file in a repository that is not on a work branch, with a message saying where the repository is, such as:

> Blocked: work happens only on a branch, and this file's repository is on main. Create a branch with git switch -c `<type>/<description>`, then make the change there.

The check goes by the checkout that holds the file, not by the session's working directory. So a file in a worktree on its own branch can be changed while the main checkout is on main, and a file in a checkout on main is blocked even when the session started somewhere else. For a new file in a directory that does not exist yet, git is asked in the nearest directory that does.

Allowed:

- a file in a repository on a work branch
- a file outside any repository, such as a scratch file or Claude's memory
- a file git ignores, such as `.claude/settings.local.json`, which is on no branch
- a file in the git directory, such as `.git/config` or `.git/info/exclude`, which is on no branch either
- a file in a repository with no commits, in the middle of a rebase, or with a merge, cherry-pick or revert stopped at a conflict

## Commits

When a session starts, the script registers itself as git's `pre-commit` hook under the name `work-branch`, as the plugin's [git hooks](../../README.md#git-hooks) are registered. Git then runs it before every commit that `git commit` makes through Claude's Bash commands, an amended one included.

The hook rejects the commit when the repository is not on a work branch, with a message such as:

> Rejected: work happens only on a branch, and this repository is on main, so nothing was committed. Create a branch with git switch -c `<type>/<description>`, which keeps the changes, and commit there.

This check is what stops the work a Bash command does. Nothing in a command's text says whether it writes files, so a Bash call cannot be blocked before it runs, and a formatter, an installer or `rm` can still change files on main. Those changes cannot be committed there with `git commit`, and `git switch -c` carries them onto a new branch.

## Not checked

- files a Bash command changes, until `git commit` is asked to commit them, and never if they are never committed
- files changed by any other tool, such as one an MCP server provides
- `git commit --no-verify`, which skips the `pre-commit` hook
- commits that other git commands make on main, master or develop, such as `git cherry-pick`, `git revert` and `git merge`, whether it fast-forwards or makes a merge commit: none runs a `pre-commit` hook unless they stop at a conflict, and then the hook lets through the commit that finishes them; a fast-forward is how `git pull` brings main up to date
- a repository whose shared branch has another name, such as trunk: only main, master and develop are kept free of work
- what none of the plugin's [git hooks](../../README.md#git-hooks) checks, such as a commit run with `-c hook.work-branch.enabled=false`
