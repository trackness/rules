# Contributing

## Workflow

- Branch from `main`, naming the branch `<type>/<description>` per [Conventional Branch](https://conventionalbranch.org/): `feature/` (or `feat/`), `bugfix/` (or `fix/`), `hotfix/`, `release/` or `chore/`, lowercase and hyphen-separated.
- Write commit messages and the pull request title per [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), such as `feat: add …` or `fix: …`.
- To try a change in a Claude Code session, start it from the repo root with `claude --plugin-dir plugins/rules`.
- Run both suites from the repo root, `uv run pytest` and `claude plugin test plugins/rules`, then open a pull request to `main`.

## Adding or changing a rule

The plugin is `plugins/rules/`, and each rule is a folder in its `scripts/` holding everything about the rule: its script, its tests and its README. A rule needs:

1. A folder `plugins/rules/scripts/<name>/`, named in snake_case after the rule, holding its script `rule.py`, with its logic in functions and its input (stdin, arguments or environment) read only under `if __name__ == "__main__":`, so its tests can import it. It must be executable, start with `#!/usr/bin/env python3`, and use only the standard library. For a `PreToolUse` rule, Claude Code passes it the tool call as JSON on stdin; to block the call, it writes the reason to stderr and exits 2, otherwise it exits 0. A rule that git enforces, such as Conventional Commits messages, instead registers the script as a git hook from a `SessionStart` hook, through `$CLAUDE_ENV_FILE`; git then runs the command it registered, with that hook's arguments added after it, and to reject the git operation it writes the reason to stderr and exits non-zero. Its export lines must use the composable form of the Conventional Commits rule's `register`, which numbers each `GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>` from `${GIT_CONFIG_COUNT:-0}` and then increments `GIT_CONFIG_COUNT`, never setting it to a fixed number, so that rules don't replace each other's or the user's `GIT_CONFIG_*` entries, and which counts a hook's command before its event, because git aborts on an event with no command, which a shell that stops partway through the lines would leave.
2. An entry in `plugins/rules/hooks/hooks.json`, under the event and matcher it applies to (such as `PreToolUse` on `Bash`, or `SessionStart`), that runs it as `"${CLAUDE_PLUGIN_ROOT}"/scripts/<name>/rule.py`.
3. Tests in `test_rule.py` beside the script, built by test-driven development, one realistic case per cycle. The tests import the script's functions, as `from .rule import …`, and call them directly; pytest's importlib import mode, set in `pyproject.toml`, keeps every rule's same-named files apart. The file starts with the docstring `"""Tests for "<the title of the rule's README>". Run from the repo root: uv run pytest"""`.
   - Red: write one test and run it. It must fail, and fail because the behaviour is missing, not with an error. A test that passes on its first run proves nothing until you have seen it fail against a deliberately broken version of the code.
   - Green: write the least code that makes it pass.
   - Refactor: with the test passing, improve the code and the tests without changing their behaviour; anything new starts its own cycle with a failing test. Re-run the tests for the code you changed after each change.
4. A `README.md` in the rule's folder, titled with the rule's name, saying what the rule blocks, what it allows, and why, and a row in the rules table of the plugin's README, `plugins/rules/README.md`, linking to it.

A rule that needs a mod hook, such as one that checks each subagent as it starts, is instead a TypeScript hooks module, `plugins/rules/scripts/<name>/rule.ts`, exporting `register` typed as `Register` from `'claude-code'`. `plugins/rules/hooks/hooks.json` names it under `modules`, by a path relative to that file (`../scripts/<name>/rule.ts`); a plugin has one hooks module, so a second mod rule is imported into the first module rather than listed beside it. Its tests are `plugins/rules/scripts/<name>/rule.test.ts`, built by the same cycle and run with `claude plugin test plugins/rules`: each test raises events through the plugin with the kit's `$`, and the test's own `on` hooks stand for the engine beneath it. To type-check it, which needs TypeScript 5.5 or newer (`tsc`) installed, start an interactive session from the repo root with `claude --plugin-dir plugins/rules` once, which lays Claude Code's types in `plugins/rules/.claude-plugin/types/`, then run `tsc -p plugins/rules`. Run `claude plugin validate plugins/rules` after changing it.

Name things so the code explains itself, and comment only on why, where the code cannot show it.
