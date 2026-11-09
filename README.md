# rules

A Claude Code plugin of hooks that enforce rules on how Claude uses its tools. Each rule is one script in `scripts/`, registered in `hooks/hooks.json`, with its tests in `tests/`.

## Rules

| Rule | Hook | Script |
|---|---|---|
| One command per Bash call | `PreToolUse` on `Bash` | `scripts/one_command.py` |
| Write only for new files | `PreToolUse` on `Write` | `scripts/new_files_only.py` |
| No hard-wrapped Markdown | `PreToolUse` on `Write` and `Edit` | `scripts/no_hard_wrap.py` |
| Conventional Branch names | `PreToolUse` on `Bash` | `scripts/branch_name.py` |

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

### No hard-wrapped Markdown

Blocks a Write or Edit to a `.md` or `.markdown` file that breaks a paragraph or list item across lines, with this message:

> Blocked: hard-wrapped Markdown. Write each paragraph and list item as one line; break lines only between blocks, list items and table rows, and inside code blocks.

A line continues the one before it when both hold text and the second does not start a block of its own. Allowed, because each line starts a block or is not prose:

- list items (`-`, `*`, `+`, `1.`, `1)`), headings, table rows, blockquotes (including GitHub alerts such as `> [!NOTE]`), HTML and link reference definitions
- anything inside a code block fenced with backticks or tildes, or inside the YAML front matter at the top of the file, whether its lines end in LF or CRLF. As in CommonMark, a fence closes only at a line of the same character at least as long as the one that opened it, so a code block can show another fence, such as a `~~~` fence inside a backtick one or a three-backtick fence inside a four-backtick one

MDX files (`.mdx`) are not checked, because their `import` lines and JSX are not prose.

Only line breaks the call writes are checked, so an Edit inside a paragraph someone else already wrapped is allowed. For an Edit, the hook checks the file as it will be after the edit, so a line added inside an existing code fence is allowed. With `replace_all`, only the first replacement is checked.

Markdown renders the lines of a hard-wrapped paragraph as one line anyway, so the breaks only make the source harder to edit and diff.

### Conventional Branch names

Blocks a Bash call that creates a branch, or renames one, to a name that does not follow [Conventional Branch](https://conventionalbranch.org/), with a message naming the branch, such as:

> Blocked: branch name Add_Login does not follow Conventional Branch. Use `<type>/<description>`, lowercase and hyphen-separated, with type feature, feat, bugfix, fix, hotfix, release or chore; dots are allowed only in a release version, such as release/v1.2.0. main, master and develop take no prefix.

Checked: `git checkout -b` or `-B`, `git switch -c`, `-C` or `--create`, `git worktree add -b` or `-B`, `git branch <name>`, and `git branch -m` or `-M`, including after `git -C <path>` or `git -c <setting>`.

Allowed: every other command, including `git branch -d` on a badly named branch, so it can still be deleted.

Not checked: `--orphan`, `git branch` with `-f` or `--track`, and branches created other than through Bash.

The name is checked when the branch is made, before it is pushed, while renaming it is still a local change.

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
