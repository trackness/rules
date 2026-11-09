# Contributing

## Workflow

- Branch from `main`, naming the branch `<type>/<description>` per [Conventional Branch](https://conventionalbranch.org/): `feature/` (or `feat/`), `bugfix/` (or `fix/`), `hotfix/`, `release/` or `chore/`, lowercase and hyphen-separated.
- Write commit messages and the pull request title per [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), such as `feat: add …` or `fix: …`.
- Run both suites from the repo root, `uv run pytest` and `claude plugin test .`, then open a pull request to `main`.

## Adding or changing a rule

A rule needs:

1. A script in `scripts/`, named in snake_case, with its logic in functions and its input (stdin, arguments or environment) read only under `if __name__ == "__main__":`, so its tests can import it. It must be executable, start with `#!/usr/bin/env python3`, and use only the standard library. For a `PreToolUse` rule, Claude Code passes it the tool call as JSON on stdin; to block the call, it writes the reason to stderr and exits 2, otherwise it exits 0. A rule that git enforces, such as Conventional Commits messages, instead registers the script as a git hook from a `SessionStart` hook, through `$CLAUDE_ENV_FILE`; git then runs it with that hook's arguments, and to reject the git operation it writes the reason to stderr and exits non-zero.
2. An entry in `hooks/hooks.json`, under the event and matcher it applies to (such as `PreToolUse` on `Bash`, or `SessionStart`), that runs it as `"${CLAUDE_PLUGIN_ROOT}"/scripts/<name>.py`.
3. Tests in `tests/`, built by test-driven development, one realistic case per cycle. The tests import the script's functions and call them directly.
   - Red: write one test and run it. It must fail, and fail because the behaviour is missing, not with an error. A test that passes on its first run proves nothing until you have seen it fail against a deliberately broken version of the code.
   - Green: write the least code that makes it pass.
   - Refactor: with the test passing, improve the code and the tests without changing their behaviour; anything new starts its own cycle with a failing test. Re-run the tests for the code you changed after each change.
4. A row in the README's rules table, and a section saying what the rule blocks, what it allows, and why.

A rule that needs a mod hook, such as one that checks each subagent as it starts, is instead a TypeScript hooks module, `scripts/<name>.ts`, exporting `register` typed as `Register` from `'claude-code'`. `hooks/hooks.json` names it under `modules`, by a path relative to that file (`../scripts/<name>.ts`); a plugin has one hooks module, so a second mod rule is imported into the first module rather than listed beside it. Its tests are `tests/<name>.test.ts`, built by the same cycle and run with `claude plugin test .`: each test raises events through the plugin with the kit's `$`, and the test's own `on` hooks stand for the engine beneath it. To type-check it, which needs TypeScript 5.5 or newer (`tsc`) installed, start an interactive session from the repo root with `claude --plugin-dir .` once, which lays Claude Code's types in `.claude-plugin/types/`, then run `tsc -p .`. Run `claude plugin validate .` after changing it.

Name things so the code explains itself, and comment only on why, where the code cannot show it.
