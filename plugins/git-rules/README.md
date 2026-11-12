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
- git run outside Claude's Bash commands

## Requirements

The plugin requires macOS or Linux, Claude Code 2.1.322 or later, Python 3.15 or later as the `python3` on the `PATH`, and git 2.54.0 or later, the first release with hooks defined in config, which is how the rules register their git hooks. The rules use only Python's standard library. When a session starts, each rule checks the Python and the git it finds, and with an older one registers no git hook and tells Claude that its check is not active, naming the version it found. Until the workspace is trusted, Claude Code runs none of the plugin's hooks.

## Install

```sh
claude plugin marketplace add trackness/rules
claude plugin install git-rules@rules
```
