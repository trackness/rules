# Conventional Branch names

Blocks a Bash call that gives a branch a name that does not follow [Conventional Branch](https://conventionalbranch.org/), by creating it, renaming it or pushing to it, with a message naming the branch, such as:

> Blocked: branch name Add_Login does not follow Conventional Branch. Use `<type>/<description>`, lowercase and hyphen-separated, with type feature, feat, bugfix, fix, hotfix, release or chore; dots are allowed only in a release version, such as release/v1.2.0. main, master and develop take no prefix.

Checked:

- the new branch of `git checkout -b` or `-B`, `git switch -c`, `-C` or `--create`, and `git worktree add -b` or `-B`
- the new name of `git branch <name>` with no options, and of `git branch -m` or `-M`
- the `<dst>` of a `git push` refspec `<src>:<dst>`, the remote branch it creates or updates, with `refs/heads/` stripped; a `<dst>` that does not start with `refs/` is taken as a branch
- the `<name>` of `gh pr checkout <number> -b <name>` or `--branch <name>`, the local branch it creates
- each of these after `sudo`, `env` or an environment assignment such as `GIT_TRACE=1`, with git or gh run by full path, such as `/usr/bin/git`, and, for git, after git options such as `-C <path>` or `-c <setting>`

Allowed:

- `git branch -d`, and a `git push` deletion with an empty `<src>`, such as `git push origin :<name>`, so a badly named branch can still be deleted
- a `git push` without a colon, such as `git push -u origin <name>`, because the local name was checked when the branch was made
- a `git push` to a ref outside `refs/heads/`, such as a tag `refs/tags/v1.0.0`, or with a pattern refspec whose `<dst>` contains `*`, such as `refs/heads/*:refs/heads/*`, which stands for many existing names
- the repository of a `git push`, even a URL with a colon such as `git@github.com:<owner>/<repo>.git`, options such as `--force-with-lease=<ref>:<expect>`, and the value of an option given as the next word, such as `-o ci.skip`, `--push-option`, `--recurse-submodules`, `--receive-pack` or `--exec`: none is read as a refspec, though the refspecs after them are still checked
- a plain `gh pr checkout <number>`, which names the local branch after the pull request's own branch, not Claude's choice
- every other command

Not checked:

- `--orphan`, and `git branch` with `-f` or `--track`
- a value joined to its option, such as `--create=<name>`, `-b<name>` or `--branch=<name>`
- the alias `gh pr co`
- git or gh after options to `sudo` or `env`, such as `sudo -u root git`, or run by another command, such as `bash -c` or `xargs`
- a command with an unbalanced quote, such as an apostrophe in a heredoc body, which cannot be split into words
- branches created other than through Bash

The name is checked when the branch is made, before it is pushed, while renaming it is still a local change. A push refspec is checked too, because it can give the remote branch a name that was never checked locally.
