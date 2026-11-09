# rules

A Claude Code plugin of hooks that enforce rules on how Claude uses its tools. Each rule is one script in `scripts/`, registered in `hooks/hooks.json`, with its tests in `tests/`; the explicit subagent model rule is a TypeScript module that `hooks/hooks.json` names under `modules`.

## Rules

| Rule | Hook | Script |
|---|---|---|
| One command per Bash call | `PreToolUse` on `Bash` | `scripts/one_command.py` |
| Write only for new files | `PreToolUse` on `Write` | `scripts/new_files_only.py` |
| No hard-wrapped Markdown | `PreToolUse` on `Write` and `Edit` | `scripts/no_hard_wrap.py` |
| Conventional Branch names | `PreToolUse` on `Bash` | `scripts/branch_name.py` |
| Conventional Commits messages | `SessionStart`, then git's `commit-msg` | `scripts/commit_message.py` |
| Explicit subagent model | `agent.spawn`, and `tool.call` on `Workflow`: mod hooks | `scripts/subagent_model.ts` |

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

Blocks a Bash call that gives a branch a name that does not follow [Conventional Branch](https://conventionalbranch.org/), by creating it, renaming it or pushing to it, with a message naming the branch, such as:

> Blocked: branch name Add_Login does not follow Conventional Branch. Use `<type>/<description>`, lowercase and hyphen-separated, with type feature, feat, bugfix, fix, hotfix, release or chore; dots are allowed only in a release version, such as release/v1.2.0. main, master and develop take no prefix.

Checked:

- the new branch of `git checkout -b` or `-B`, `git switch -c`, `-C` or `--create`, and `git worktree add -b` or `-B`
- the new name of `git branch <name>` with no options, and of `git branch -m` or `-M`
- the `<dst>` of a `git push` refspec `<src>:<dst>`, the remote branch it creates or updates, with `refs/heads/` stripped; a `<dst>` that does not start with `refs/` is taken as a branch
- the `<name>` of `gh pr checkout <number> -b <name>` or `--branch <name>`, the local branch it creates
- each of these after `sudo`, `env` or an environment assignment such as `GIT_TRACE=1`, with git or gh run by full path, such as `/usr/bin/git`, and, for git, after git options such as `-C <path>` or `-c <setting>`

Allowed:

- `git branch -d`, and a `git push` deletion with an empty `<src>`, such as `git push origin :<name>`, so a badly named branch can still be deleted
- a `git push` without a colon, such as `git push -u origin <name>`, because the local name was checked when the branch was made
- a `git push` to a ref outside `refs/heads/`, such as a tag `refs/tags/v1.0.0`, or with a pattern refspec whose `<dst>` contains `*`, such as `refs/heads/*:refs/heads/*`, which stands for many existing names
- the repository of a `git push`, even a URL with a colon such as `git@github.com:<owner>/<repo>.git`, options such as `--force-with-lease=<ref>:<expect>`, and the value of an option given as the next word, such as `-o ci.skip`, `--push-option`, `--recurse-submodules`, `--receive-pack` or `--exec`: none is read as a refspec, though the refspecs after them are still checked
- a plain `gh pr checkout <number>`, which names the local branch after the pull request's own branch, not Claude's choice
- every other command

Not checked:

- `--orphan`, and `git branch` with `-f` or `--track`
- a value joined to its option, such as `--create=<name>`, `-b<name>` or `--branch=<name>`
- the alias `gh pr co`
- git or gh after options to `sudo` or `env`, such as `sudo -u root git`, or run by another command, such as `bash -c` or `xargs`
- a command with an unbalanced quote, such as an apostrophe in a heredoc body, which cannot be split into words
- branches created other than through Bash

The name is checked when the branch is made, before it is pushed, while renaming it is still a local change. A push refspec is checked too, because it can give the remote branch a name that was never checked locally.

### Conventional Commits messages

Makes git reject a commit Claude makes whose message does not follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), with this message:

> Rejected: the commit message does not follow Conventional Commits. Start it with `<type>[optional scope][!]: <description>`, with type feat, fix, docs, style, refactor, perf, test, build, ci or chore, and leave a blank line before any body.

When a session starts, the script adds `GIT_CONFIG_*` variables to the session's environment that register it as git's `commit-msg` hook. Git then checks the final message of every commit, merges included, made through Claude's Bash commands, however the message was given (`-m`, `-F`, a heredoc or `--amend`), and still runs the repository's own `commit-msg` hook after it. Nothing is installed in any repository or git config, so commits made outside Claude are not checked. The type must be one of the ten above, in lowercase. A `git commit --fixup`, `--squash` or `--fixup=amend:` message, which puts `fixup! `, `squash! ` or `amend! ` before the target commit's subject, is accepted when what follows the prefixes is a conventional header.

Not checked: `git commit --no-verify`, which skips commit hooks; commits made with a git older than 2.54.0, the first release with hooks defined in config; and commits in a session whose `SessionStart` hook got no `CLAUDE_ENV_FILE`, such as one run in PowerShell, in which case the script says at session start that the check is not active.

Git checks the message it is about to record, so no way of writing the command gets around it, and the check stays inside Claude's sessions.

### Explicit subagent model

Requires every subagent Claude spawns to have a model named on its call. The rule checks each agent as it starts, through the `agent.spawn` mod hook, so it sees Agent calls and every agent a workflow spawns, however the script calls `agent()`. It refuses a spawn whose call names no model and tells Claude to name one appropriately capable for its task; it doesn't judge whether the model named is. For an Agent call, Claude reads:

> Subagent spawn denied by a plugin: Every subagent must run on a model appropriately capable for its task. Retry this call with the model parameter set to that model.

In a workflow, the `agent()` call throws this error:

> Workflow agent spawn denied by a plugin: Every agent a workflow spawns must run on a model appropriately capable for its task. Set the model option of every agent() call to that model, then run the workflow again.

The engine reports it to Claude in the run's result, possibly wrapped: left uncaught, it fails the run, and Claude reads it after an error type and before a stack trace; inside `parallel()` or `pipeline()`, it fails only that item, which becomes `null`.

`inherit` doesn't count as a model, nor does an empty one. Allowed without one:

- a fork, whose model parameter Claude Code ignores because a fork always runs on the caller's model
- a resumed subagent, which keeps the model it started on
- an agent of a built-in or plugin workflow run by name, since Claude can't change that script
- an agent another plugin spawns through its own hooks, since the rule checks only the spawns of Claude's own Agent and Workflow calls
- any agent while `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is on, since Claude Code then ignores the model a call names
- any workflow agent while `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL` names a model, since Claude Code then ignores the model a script names

A workflow run by name is checked like a script Claude wrote when a script saved on disk runs by that name, since Claude could have saved it there; a saved script that parses overrides a built-in or plugin workflow of its name. Claude Code 2.1.319 runs a saved workflow by the `name` in its `meta`, and the rule looks for one where Claude Code's binary does, in the `.js` files directly in these folders:

- `.claude/workflows/` in the working directory and in each directory above it, up to and including the repository root, stopping before the home folder if the walk reaches it. Outside a repository, the walk goes on to the file system root unless it reaches the home folder first. A repository nested in the repository of the session's project root walks on to that outer repository's root, unless it is a worktree of it.
- the personal folder: `workflows/` in `CLAUDE_CONFIG_DIR`, which is `.claude` in the home folder unless set, the home folder being `USERPROFILE` on Windows and `HOME` elsewhere, as Node's `os.homedir()` reads it

Windows paths are walked by both `/` and `\`. The agents of any workflow that Claude's own script runs with `workflow()`, a saved or built-in one included, are part of Claude's run and are checked with it.

The rule matches a saved script by where it is and the name in its `meta`, without loading it as Claude Code does, so in edge cases it checks a run that Claude Code serves from a built-in workflow and refuses that run's agents. Such cases include a script saved under the built-in's name that Claude Code skips, because it doesn't parse, its `meta` is invalid or it is too large; settings that keep Claude Code from loading saved scripts, such as `--setting-sources` without the source whose folder holds the script, or `CLAUDE_WORKFLOW_NAME_ONLY`; and a worktree whose `.git` file gives a relative path, which the rule doesn't follow.

In these rarer cases the lookup can differ from Claude Code's either way, so the rule can check a run that Claude Code serves from a built-in workflow, or let through the agents of a saved script that Claude Code runs:

- Claude Code keeps the list of saved workflows it read until `/reload-skills`, while the rule reads the folders at each Workflow call, so for a script saved, changed or removed during the session the rule goes by what is on disk, not by what Claude Code runs.
- A session started with `--project-config-root`, as a host may start one in a worktree, makes Claude Code walk from that folder rather than from the working directory, where the rule's walk starts.
- In a session that keeps the user's files in a storage backend rather than on disk, Claude Code reads the personal folder from that backend, which the rule's file reads may not reach.
- On Windows, Claude Code compares paths without regard to letter case, while the rule compares them exactly, so a home folder or project root spelled in another case than the working directory can make the rule's walk stop or go on where Claude Code's doesn't.

The rule ties a workflow's agents to the Workflow call that started the run, and keeps which calls it checks in memory. So an agent whose spawn carries no such call, as Claude Code allows on a resumed or server-launched run, is not checked, and nor is an agent that a run started before the plugin's hooks reloaded spawns after the reload.

Like the other rules, the hooks have no fallback: if one fails, Claude Code skips it and the call goes through unchecked.

An agent whose definition pins a model still needs one on the call, because the spawn doesn't show what a definition pins. After one refusal Claude names a model, and the call's model then replaces the definition's.

A subagent spawned without a model runs on whatever the session's settings and the agent's definition resolve to, falling back to the parent's model, rather than on a model chosen for its task.

## Requirements

The Python rules run with the `python3` on the `PATH` and use only its standard library. The explicit subagent model rule is a mod, a TypeScript hooks module that Claude Code runs itself, built and tested against Claude Code 2.1.319; mods are early access, and their API can change between releases. Claude Code doesn't load the module while its rollout flag for installed plugins' hooks modules is off, and the Python rules then run without it; until the workspace is trusted, it runs none of the plugin's hooks.

## Install

```sh
claude plugin marketplace add trackness/rules
claude plugin install rules@rules
```

## Test

The Python rules' tests use pytest, managed by [uv](https://docs.astral.sh/uv/) and pinned to Python 3.15, the same Python the hooks run under here. The mod's tests run in Claude Code's own plugin test kit. From the repo root:

```sh
uv run pytest
claude plugin test .
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
