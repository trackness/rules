# rules

This repo is the Claude Code plugin marketplace `rules`, holding three plugins, each a folder in `plugins/`. Each plugin's README says what it does and how to install it.

| Plugin | What it is |
|---|---|
| [`rules`](plugins/rules/README.md) | Six Python hook rules on how Claude uses its tools |
| [`subagent-model`](plugins/subagent-model/README.md) | A mod: the explicit subagent model rule |
| [`row-time`](plugins/row-time/README.md) | A mod: row times |

Each `claude plugin install` copies only that plugin's folder, such as `plugins/rules/`, into Claude Code's plugin cache. The marketplace manifest, `.claude-plugin/marketplace.json`, sits at the repo root with each plugin's source set to its folder, such as `./plugins/rules`, and so does the tooling that runs the Python tests: `pyproject.toml`, `uv.lock` and `.python-version`. `claude plugin marketplace add` clones the whole repo, so these root files reach the marketplace's copy but not an installed plugin.

## Test

The Python rules' tests use pytest, managed by [uv](https://docs.astral.sh/uv/) and pinned to Python 3.15. The mods' tests run in Claude Code's own plugin test kit, which tests one plugin at a time. From the repo root:

```sh
uv run pytest
claude plugin test plugins/subagent-model
claude plugin test plugins/row-time
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
