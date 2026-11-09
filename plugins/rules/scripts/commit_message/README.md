# Conventional Commits messages

Makes git reject a commit Claude makes with `git commit` or `git merge` whose message does not follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), with this message:

> Rejected: the commit message does not follow Conventional Commits. Start it with `<type>[optional scope][!]: <description>`, with type feat, fix, docs, style, refactor, perf, test, build, ci or chore, and leave a blank line before any body.

When a session starts, the script adds `GIT_CONFIG_*` variables to the session's environment that register it as git's `commit-msg` hook. Git then checks the final message of every commit that `git commit` or `git merge` makes through Claude's Bash commands, however the message was given (`-m`, `-F`, a heredoc or `--amend`), and still runs the repository's own `commit-msg` hook after it. Nothing is installed in any repository or git config, so commits made outside Claude are not checked. The type must be one of the ten above, in lowercase. A `git commit --fixup`, `--squash` or `--fixup=amend:` message, which puts `fixup! `, `squash! ` or `amend! ` before the target commit's subject, is accepted when what follows the prefixes is a conventional header.

Not checked: `git commit --no-verify`, which skips commit hooks; commits that other git commands make, such as `git revert`, `git cherry-pick` or `git commit-tree`, which run no `commit-msg` hook; commits made with a git older than 2.54.0, the first release with hooks defined in config; and commits in a session whose `SessionStart` hook got no `CLAUDE_ENV_FILE`, such as one run in PowerShell, in which case the script says at session start that the check is not active.

Git checks the message it is about to record, so however a `git commit` or `git merge` gives the message, the check sees it, unless the command skips the hook, as `--no-verify` does, or sets `GIT_CONFIG_COUNT=0`, which drops the session's registration of it. The check stays inside Claude's sessions.
