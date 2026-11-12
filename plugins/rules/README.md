# rules

A Claude Code plugin of hooks that enforce rules on how Claude uses its tools. Each rule is a folder in `scripts/`, holding the rule, its tests and its README, and is registered in `hooks/hooks.json`. The rules that git enforces, on the commits, branches and pushes Claude makes, are a plugin of their own, [`git-rules`](../git-rules/README.md).

## Rules

| Rule | Hook |
|---|---|
| [One command per Bash call](scripts/one_command/README.md) | `PreToolUse` on `Bash`, which also runs on Monitor commands |
| [Write only for new files](scripts/new_files_only/README.md) | `PreToolUse` on `Write` |
| [No hard-wrapped Markdown](scripts/no_hard_wrap/README.md) | `PreToolUse` on `Write` and `Edit` |

When a hook blocks a call, Claude Code cancels it and shows Claude the hook's message.

## Requirements

The plugin runs on macOS or Linux, with Claude Code 2.1.322 or later. The rules run with the `python3` on the `PATH` and use only its standard library. Until the workspace is trusted, Claude Code runs none of the plugin's hooks.

## Install

```sh
claude plugin marketplace add trackness/rules
claude plugin install rules@rules
```
