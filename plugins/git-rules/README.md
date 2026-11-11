# git-rules

A Claude Code plugin of rules on the commits, branches and pushes Claude makes, which git enforces through hooks each session registers. Each rule is a folder in `scripts/`, holding the rule, its tests and its README, and is registered in `hooks/hooks.json`. The rules register their git hooks through `scripts/git_hook.py`, which they share.

## Rules

| Rule | Hook |
|---|---|
| [Conventional Branch names](scripts/branch_name/README.md) | `PreToolUse` on `Bash`, plus git's `pre-push` from `SessionStart` |
| [Conventional Commits messages](scripts/commit_message/README.md) | git's `commit-msg` from `SessionStart` |
| [Work only on a branch](scripts/work_branch/README.md) | `PreToolUse` on `Edit`, `Write` and `NotebookEdit`, plus git's `pre-commit` from `SessionStart` |

When a hook blocks a call, Claude Code cancels it and shows Claude the hook's message. When a git hook rejects a commit or a push, git stops it, and its message is in the output of Claude's Bash command.

## Git hooks

When a session starts, each rule adds `GIT_CONFIG_*` variables to the session's environment, after any already there, that register the rule's script as a git hook under the name the rule's README gives. Git then runs the script in the Bash commands Claude runs. Nothing is installed in any repository or git config, so git run outside Claude's Bash commands is not checked.

None of these git hooks checks:

- a git command that turns the hook off, such as with `-c hook.<name>.enabled=false` or with `-c hook.<name>.event=`, which empties its list of events, or that runs without the session's `GIT_CONFIG_*` variables or with them changed, such as under `GIT_CONFIG_COUNT=0` or `env -i`
- a repository or user whose git config sets `hook.<name>.enabled` to `false`, which turns the hook off for every later git command there
- git older than 2.54.0, or git run by a PowerShell command, as Requirements says
- git run outside Claude's Bash commands

## Requirements

The rules run with the `python3` on the `PATH`, which must be Python 3.9 or later, and use only its standard library. The Conventional Commits rule, the Conventional Branch names rule's check on pushes and the work branch rule's check on commits need git 2.54.0 or later, the first release with hooks defined in config; with an older git, neither commits nor pushes are checked, though the branch names rule's check on Bash calls and the work branch rule's check on file changes still run. The rules register their hooks with lines in the session's `CLAUDE_ENV_FILE` that are not plain assignments, so Claude Code gives PowerShell commands none of that file's variables, from these rules or any other hook, and git run by a PowerShell command is not checked; Bash commands get every variable. On Windows without Git Bash, Claude Code has no Bash tool, only PowerShell, and runs the `SessionStart` hooks in PowerShell with no `CLAUDE_ENV_FILE` to register the git hooks in; their command, written for a POSIX shell, may not run there at all, and if it does, each rule tells Claude at session start that its check is not active. Until the workspace is trusted, Claude Code runs none of the plugin's hooks.

## Install

```sh
claude plugin marketplace add trackness/rules
claude plugin install git-rules@rules
```
