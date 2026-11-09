# Contributing

## Workflow

- Branch from `main`, naming the branch `<type>/<description>` per [Conventional Branch](https://conventionalbranch.org/): `feature/`, `bugfix/`, `hotfix/`, `release/` or `chore/`, lowercase and hyphen-separated.
- Write commit messages per [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), such as `feat: add …` or `fix: …`.
- Open a pull request to `main`. Pull requests are squash-merged into a single commit on `main`, and merged branches are deleted.

## Adding or changing a rule

Each rule is one hook, made of:

1. A script in `scripts/`, named in snake_case so its tests can import it. It must be executable, start with `#!/usr/bin/env python3`, and use only the standard library. Claude Code passes it the tool call as JSON on stdin. To block the call, it writes the reason to stderr and exits 2; otherwise it exits 0.
2. An entry in `hooks/hooks.json` that runs it as `"${CLAUDE_PLUGIN_ROOT}"/scripts/<name>.py`.
3. Tests in `tests/`, written first: each behaviour gets a failing test before the code that makes it pass.
4. A row in the README's rules table, and a section saying what the rule blocks, what it allows, and why.

## Development

- Run the tests from the repo root with `uv run pytest`.
- Keep Python lines to 150 characters, as set in `.editorconfig`.
- Name things so the code explains itself, and comment only on why, where the code cannot show it.
