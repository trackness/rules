# rules

This repo is the Claude Code plugin marketplace `rules`, holding six plugins, each a folder in `plugins/`. Each plugin's README says what it does and how to install it.

| Plugin | What it is |
|---|---|
| [`rules`](plugins/rules/README.md) | Three Python hook rules on how Claude uses its tools |
| [`git-rules`](plugins/git-rules/README.md) | Three Python rules that git enforces on the commits, branches and pushes Claude makes |
| [`subagent-model`](plugins/subagent-model/README.md) | A mod: the explicit subagent model rule |
| [`row-time`](plugins/row-time/README.md) | A mod: row times |
| [`agent-row`](plugins/agent-row/README.md) | A Python `subagentStatusLine`: each background agent's model and description in its row |
| [`audit`](plugins/audit/README.md) | Three skills, each run by subagents: an exhaustive code audit, a fix run for its findings, and an architecture review |

Each `claude plugin install` copies only that plugin's folder, such as `plugins/rules/`, into Claude Code's plugin cache. The marketplace manifest, `.claude-plugin/marketplace.json`, sits at the repo root with each plugin's source set to its folder, such as `./plugins/rules`, and so does the tooling that runs the Python tests: `pyproject.toml`, `uv.lock` and `.python-version`. `claude plugin marketplace add` clones the whole repo, so these root files reach the marketplace's copy but not an installed plugin.

## Requirements

macOS or Linux, Claude Code 2.1.322 or later, and Python 3.9 or later as the `python3` on the `PATH`. The `git-rules` plugin also needs git 2.54.0 or later.

## Test

The Python tests use pytest, managed by [uv](https://docs.astral.sh/uv/) and pinned to Python 3.15. The mods' tests run in Claude Code's own plugin test kit, which tests one plugin at a time. From the repo root:

```sh
uv run pytest
claude plugin test plugins/subagent-model
claude plugin test plugins/row-time
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
