# Conventional Branch names

Keeps the names of the branches Claude makes to [Conventional Branch 1.0.0](https://conventionalbranch.org/v1.0.0/) with two checks: one on each Bash call, which blocks a command that gives a branch a name that does not follow it before the command runs, and one in git's `pre-push` hook, which refuses a push that would create a remote branch with such a name, whatever command made the branch.

A name passes when it is `<type>/<description>`, with type feature, feat, bugfix, fix, hotfix, release or chore, lowercase and hyphen-separated, or when it is main, master or develop. Like the 1.0.0 rules, it allows dots only in the description of a release branch, for a version number, though the 1.0.0 grammar would allow them in any description. The rule also accepts gh-pages, which the specification does not name, because it is the branch that tools publishing to GitHub Pages, such as `mkdocs gh-deploy` and `ghp-import`, push to by default, a name Claude does not choose. Version 1.1.0 of the specification, now current, adds more types and allows dots in any description; this rule does not.

## Bash calls

Blocks a Bash call that gives a branch a name that does not follow Conventional Branch 1.0.0, by creating it, renaming it or pushing to it, with a message naming the branch, such as:

> Blocked: branch name Add_Login does not follow Conventional Branch 1.0.0. Use `<type>/<description>`, lowercase and hyphen-separated, with type feature, feat, bugfix, fix, hotfix, release or chore; dots are allowed only in a release version, such as release/v1.2.0. main, master, develop and gh-pages take no prefix.

Checked:

- the new branch of `git checkout -b` or `-B`, `git switch -c`, `-C` or `--create`, and `git worktree add -b` or `-B`
- the new name of `git branch <name>` with no options, and of `git branch -m` or `-M`
- the `<dst>` of a `git push` refspec `<src>:<dst>`, the remote branch it creates or updates, with `refs/heads/` stripped; a `<dst>` that does not start with `refs/` is taken as a branch
- the `<name>` of `gh pr checkout <number> -b <name>` or `--branch <name>`, the local branch it creates
- each of these after `sudo`, `env` or an environment assignment such as `GIT_TRACE=1`, with git or gh run by full path, such as `/usr/bin/git`, and, for git, after git options given as one word, such as `--git-dir=<path>`, or as `-C <path>` or `-c <setting>`

Allowed:

- `git branch -d`, and a `git push` deletion with an empty `<src>`, such as `git push origin :<name>`, so a badly named branch can still be deleted
- a `git push` without a colon, such as `git push -u origin <name>`, because the local name was checked when the branch was made
- a `git push` to a ref outside `refs/heads/`, such as a tag `refs/tags/v1.0.0`, or with a pattern refspec whose `<dst>` contains `*`, such as `refs/heads/*:refs/heads/*`, which stands for many existing names
- the repository of a `git push`, even a URL with a colon such as `git@github.com:<owner>/<repo>.git`, options such as `--force-with-lease=<ref>:<expect>`, and the value of an option given as the next word, such as `-o ci.skip`, `--push-option`, `--recurse-submodules`, `--receive-pack` or `--exec`: none is read as a refspec, though the refspecs after them are still checked
- a plain `gh pr checkout <number>`, which names the local branch after the pull request's own branch, not Claude's choice
- every other command

A push this check allows still meets the `pre-push` check below, except as listed under Not checked.

The check reads only the commands listed under Checked, so a branch made any other way is caught only when a push through Claude's Bash commands creates it on the remote. Such ways include:

- `git checkout --orphan` and `git switch --orphan`
- `git branch` with any option but `-m` or `-M`, such as `-c`, `-C`, `--copy`, `--move`, `-f`, `--track` or `-q`
- `git worktree add <path>` without `-b`, which names the branch after the path
- `git stash branch`, `git update-ref` and `git fetch <remote> <src>:<dst>`
- a value joined to its option, such as `--create=<name>`, `-b<name>` or `--branch=<name>`
- a git option other than `-C` and `-c` with its value as the next word, such as `--git-dir <path>`
- a git alias, such as `git co -b <name>`, and the gh alias `gh pr co`
- git or gh after options to `sudo` or `env`, such as `sudo -u root git`, or run by another command, such as `bash -c` or `xargs`
- a command with an unbalanced quote, such as an apostrophe in a heredoc body, which cannot be split into words
- branches created other than through Bash, such as the branch Claude Code makes for an isolated worktree

The name is checked when the branch is made, before it is pushed, while renaming it is still a local change. A push refspec is checked too, because it can give the remote branch a name that was never checked locally.

## Pushes

When a session starts, the script adds `GIT_CONFIG_*` variables to the session's environment, after any already there, that register it as git's `pre-push` hook. Git then runs it before every push made through Claude's Bash commands, and still runs the repository's own `pre-push` hook after it, even when this one refuses the push. Nothing is installed in any repository or git config, so pushes made outside Claude are not checked.

Git passes the hook every ref the push would update, and the hook refuses the push, so that git pushes nothing, when any of them would create a branch on the remote whose name does not follow Conventional Branch 1.0.0, with a message naming each such branch, such as:

> Rejected: this push would create the remote branch Add_Login, whose name does not follow Conventional Branch 1.0.0, so nothing was pushed. Rename the local branch to a conventional name with `git branch -m <old> <new>` and push it under that name, or, for a `<src>:<dst>` refspec, push to a conventional `<dst>`. Use `<type>/<description>`, lowercase and hyphen-separated, with type feature, feat, bugfix, fix, hotfix, release or chore; dots are allowed only in a release version, such as release/v1.2.0. main, master, develop and gh-pages take no prefix.

Refused: a push that creates a branch under `refs/heads/` that the remote does not have yet, with a name that does not follow Conventional Branch 1.0.0, however the push names it: after the local branch, such as `git push origin Add_Login` or `git push origin HEAD`, by a refspec, such as `git push origin main:Add_Login`, or by a pattern refspec, such as `refs/heads/*:refs/heads/*`, that would create it. This includes the branch Claude Code makes for an isolated worktree, such as `worktree-agent-<id>`, which must be renamed before it is pushed.

Allowed:

- a push that creates a remote branch with a conventional name
- deleting a remote branch, such as `git push origin :<name>` or `git push origin --delete <name>`, so a badly named branch can still be deleted
- updating a remote branch that already exists, even a badly named one, whose name was given before
- pushing a tag, or any other ref outside `refs/heads/`

The hook checks the name the branch would have on the remote, not the command, so it applies whatever command made the branch, including those the Bash check cannot read, such as `bash -c 'git branch Add_Login'`.

## Not checked

- a local branch made in a way the Bash check does not read, until a push creates it on the remote, and never if it is never pushed
- `git push --no-verify`, which skips the `pre-push` hook, and `git send-pack`, which runs no `pre-push` hook
- a git command that turns the hook off, such as with `-c hook.conventional-branch.enabled=false` or with `-c hook.conventional-branch.event=`, which empties its list of events, or that runs without the session's `GIT_CONFIG_*` variables or with them changed, such as under `GIT_CONFIG_COUNT=0` or `env -i`
- a repository or user whose git config sets `hook.conventional-branch.enabled` to `false`, which turns the hook off for every later push there
- pushes made with a git older than 2.54.0, the first release with hooks defined in config
- pushes that PowerShell commands make, since the lines the script adds are not plain assignments, so Claude Code gives PowerShell commands none of the session's `CLAUDE_ENV_FILE` variables, from this hook or any other. On Windows without Git Bash, Claude Code has no Bash tool, only PowerShell, and runs the `SessionStart` hook in PowerShell with no `CLAUDE_ENV_FILE` to register the hook in; the hook's command, written for a POSIX shell, may not run there at all, and if it does, the script tells Claude at session start that the check on pushes is not active.
- pushes made outside Claude's Bash commands
