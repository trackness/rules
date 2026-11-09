# rules

This repo holds the Claude Code plugin `rules`, in `plugins/rules/`. See [the plugin's README](plugins/rules/README.md) for the rules it enforces and how to install it.

`claude plugin install` copies only `plugins/rules/` into Claude Code's plugin cache. The marketplace manifest, `.claude-plugin/marketplace.json`, sits at the repo root with the plugin's source set to `./plugins/rules`, and so does the tooling that runs the Python tests: `pyproject.toml`, `uv.lock` and `.python-version`. `claude plugin marketplace add` clones the whole repo, so these root files reach the marketplace's copy but not the installed plugin.

## Test

The Python rules' tests use pytest, managed by [uv](https://docs.astral.sh/uv/) and pinned to Python 3.15. The mod's tests run in Claude Code's own plugin test kit. From the repo root:

```sh
uv run pytest
claude plugin test plugins/rules
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
