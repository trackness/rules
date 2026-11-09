# rules

A Claude Code plugin of hooks that enforce rules on how Claude uses its tools. Each rule is one script in `scripts/`, registered in `hooks/hooks.json`, with its tests in `tests/`.

## Rules

| Rule | Hook | Script |
|---|---|---|
| One command per Bash call | `PreToolUse` on `Bash` | `scripts/one_command.py` |
| Write only for new files | `PreToolUse` on `Write` | `scripts/new_files_only.py` |

When a hook blocks a call, Claude Code cancels it and shows Claude the hook's message.

### One command per Bash call

Blocks a Bash call that chains commands with `;`, `&&`, `||`, `|`, `&` or a newline, with this message:

> Blocked: one command per Bash call. Find a single command or tool that does the whole job. Only if there isn't one, send the commands as separate calls.

Allowed, because it is not chaining:

- a separator inside quotes or after a backslash, which is an argument: `git commit -m "fix: a; b"`, `rg 'foo|bar' src`, `find . -name x -exec rm {} \;`
- a heredoc body, which is input: `git commit -m "$(cat <<'EOF' … EOF)"`
- `&` in a redirection (`2>&1`, `&>`), or a trailing `&` that runs one command in the background

Checked even though quoted, because it runs as commands:

- the argument to any shell's `-c` (including combined flags such as `-lc`), to `eval` or to `ssh`
- a `$(…)` or backticks inside double quotes
- a heredoc fed to a shell or to `ssh`

### Write only for new files

Blocks a Write to a file that already exists, with this message:

> Blocked: Write is only for new files, and this one already exists. Change it with Edit, or NotebookEdit for a notebook.

Allowed: a Write that creates a new file.

Write replaces the whole file, so anything left out of the new content is lost, while Edit changes only the text it names. Claude Code's own check on Write only requires the file to have been Read first. An empty file is blocked too, because Edit with an empty `old_string` fills it.

## Requirements

The hooks run with the `python3` on the `PATH` and use only its standard library.

## Install

```sh
claude plugin marketplace add trackness/rules
claude plugin install rules@rules
```

## Test

The tests use pytest, managed by [uv](https://docs.astral.sh/uv/) and pinned to Python 3.15, the same Python the hooks run under here. From the repo root:

```sh
uv run pytest
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
