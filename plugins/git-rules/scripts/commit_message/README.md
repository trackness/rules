# Conventional Commits messages

Makes git reject a commit Claude makes with `git commit` or `git merge` whose message does not follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), with this message:

> Rejected: the commit message does not follow Conventional Commits. Start it with `<type>[optional scope][!]: <description>`, with type feat, fix, docs, style, refactor, perf, test, build, ci or chore, and leave a blank line before any body.

When a session starts, the script registers itself as git's `commit-msg` hook under the name `conventional-commits`, as the plugin's [git hooks](../../README.md#git-hooks) are registered. Git then checks the final message of every commit that `git commit` or `git merge` makes through Claude's Bash commands, however the message was given (`-m`, `-F`, a heredoc or `--amend`), and still runs the repository's own `commit-msg` hook after it. The type must be one of the ten above, in lowercase. A `git commit --fixup`, `--squash` or `--fixup=amend:` message, which puts `fixup! `, `squash! ` or `amend! ` before the target commit's subject, is accepted when what follows the prefixes is a conventional header.

Not checked: `git commit --no-verify` and `git merge --no-verify`, which skip the `commit-msg` hook; commits that other git commands make, such as `git commit-tree`, or `git revert` and `git cherry-pick` unless they stop at a conflict, which run no `commit-msg` hook; and what none of the plugin's [git hooks](../../README.md#git-hooks) checks, such as a git command run with `-c hook.conventional-commits.enabled=false`, a git older than 2.54.0 or git run by a PowerShell command.

Git checks the message it is about to record, so however a `git commit` or `git merge` gives the message, the check sees it, unless the hook is skipped or turned off in one of the ways listed above. The check stays inside Claude's sessions.
