# rules

A Claude Code plugin of hooks that enforce rules on how Claude uses its tools. Each rule is a folder in `scripts/`, holding the rule, its tests and its README, and is registered in `hooks/hooks.json`.

## Rules

| Rule | Hook |
|---|---|
| [One command per Bash call](scripts/one_command/README.md) | `PreToolUse` on `Bash` |
| [Write only for new files](scripts/new_files_only/README.md) | `PreToolUse` on `Write` |
| [No hard-wrapped Markdown](scripts/no_hard_wrap/README.md) | `PreToolUse` on `Write` and `Edit` |
| [Conventional Branch names](scripts/branch_name/README.md) | `PreToolUse` on `Bash`, plus git's `pre-push` from `SessionStart` |
| [Conventional Commits messages](scripts/commit_message/README.md) | `SessionStart`, then git's `commit-msg` |
| [Work only on a branch](scripts/work_branch/README.md) | `PreToolUse` on `Edit`, `Write` and `NotebookEdit`, plus git's `pre-commit` from `SessionStart` |

When a hook blocks a call, Claude Code cancels it and shows Claude the hook's message. When a git hook rejects a commit or a push, git stops it, and its message is in the output of Claude's Bash command.

## Requirements

The Python rules run with the `python3` on the `PATH` and use only its standard library. The Conventional Commits rule, the Conventional Branch names rule's check on pushes and the work branch rule's check on commits need git 2.54.0 or later, the first release with hooks defined in config; with an older git, neither commits nor pushes are checked, though the branch names rule's check on Bash calls and the work branch rule's check on file changes still run. The three git rules register their hooks with lines in the session's `CLAUDE_ENV_FILE` that are not plain assignments, so Claude Code gives PowerShell commands none of that file's variables, from these rules or any other hook, and git run by a PowerShell command is not checked; Bash commands get every variable. Until the workspace is trusted, Claude Code runs none of the plugin's hooks.

## Install

```sh
claude plugin marketplace add trackness/rules
claude plugin install rules@rules
```
