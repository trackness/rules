# Explicit subagent model

Requires every subagent Claude spawns to have a model named on its call. The rule checks each agent as it starts, through the `agent.spawn` mod hook, so it sees Agent calls and every agent a workflow spawns, however the script calls `agent()`. It refuses a spawn whose call names no model and tells Claude to name one appropriately capable for its task; it doesn't judge whether the model named is. For an Agent call, Claude reads:

> Subagent spawn denied by a plugin: Every subagent must run on a model appropriately capable for its task. Retry this call with the model parameter set to that model.

In a workflow, the `agent()` call throws this error:

> Workflow agent spawn denied by a plugin: Every agent a workflow spawns must run on a model appropriately capable for its task. Set the model option of every agent() call to that model, then run the workflow again.

The engine reports it to Claude in the run's result, possibly wrapped: left uncaught, it fails the run, and Claude reads it after an error type and before a stack trace; inside `parallel()` or `pipeline()`, it fails only that item, which becomes `null`.

`inherit` doesn't count as a model, nor does an empty one. Allowed without one:

- a fork, whose model parameter Claude Code ignores because a fork always runs on the caller's model
- a resumed subagent, which keeps the model it started on
- an agent of a built-in or plugin workflow run by name, since Claude can't change that script; run again by the `scriptPath` that Claude Code returns for each run, a copy Claude can edit, it is checked like Claude's own script
- an agent another plugin spawns through its own hooks, since the rule checks only the spawns of Claude's own Agent and Workflow calls
- any agent while `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is on, since Claude Code then ignores the model a call names
- an Agent call's agent in coordinator mode while `CLAUDE_CODE_COORDINATOR_FORCE_WORKER_INHERIT_MODEL` is on, since Claude Code then clears the model the call names; coordinator mode is on while `CLAUDE_CODE_COORDINATOR_MODE` is, in any session but an interactive one without `CLAUDE_CODE_REMOTE`
- any workflow agent while `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL` names a model, since Claude Code then ignores the model a script names

A workflow run by name is checked like a script Claude wrote when a script saved on disk runs by that name, since Claude could have saved it there; a saved script that Claude Code loads overrides a built-in or plugin workflow of its name. Claude Code 2.1.322 runs a saved workflow by the `name` in its `meta`, and loads the script only if it is no larger than 512 KiB (524288 bytes) and that `meta` is its first statement, with nothing before it but a hashbang line at the very start, whitespace and comments. The rule reads the name only from a `meta` placed so, in a script no larger than that, and looks for the script where Claude Code's binary does, in the `.js` files directly in these folders:

- `.claude/workflows/` in the working directory and in each directory above it, up to and including the repository root, stopping before the home folder if the walk reaches it. Outside a repository, the walk goes on to the file system root unless it reaches the home folder first. A repository nested in the repository of the session's project root walks on to that outer repository's root, unless it is a worktree of it. The walk passes over, without stopping, any directory whose path goes through a folder named `connector-downloads`, since Claude Code loads no project workflows from anywhere inside one.
- the personal folder: `workflows/` in `CLAUDE_CONFIG_DIR`, which is `.claude` in the home folder unless set, the home folder being `HOME`, as Node's `os.homedir()` reads it while `HOME` is set and not empty; set but empty, `CLAUDE_CONFIG_DIR` stands for the directory Claude Code runs in, the session's project root, so the personal folder is then `workflows/` there

The agents of any workflow that Claude's own script runs with `workflow()`, a saved or built-in one included, are part of Claude's run and are checked with it.

The rule matches a saved script by where it is and the name in its `meta`, without loading it as Claude Code does, so in edge cases it checks a run that Claude Code serves from a built-in workflow and refuses that run's agents. Such cases include a script saved under the built-in's name that Claude Code skips, because it doesn't parse or its `meta` is invalid; settings that keep Claude Code from loading saved scripts, such as `--setting-sources` without the source whose folder holds the script, or `CLAUDE_WORKFLOW_NAME_ONLY`; and a worktree whose `.git` file gives a relative path, which the rule doesn't follow.

In these rarer cases the lookup can differ from Claude Code's either way, so the rule can check a run that Claude Code serves from a built-in workflow, or let through the agents of a saved script that Claude Code runs:

- Claude Code keeps the list of saved workflows it read until `/reload-skills`, while the rule reads the folders at each Workflow call, so for a script saved, changed or removed during the session the rule goes by what is on disk, not by what Claude Code runs.
- A session started with `--project-config-root`, as a host may start one in a worktree, makes Claude Code walk from that folder rather than from the working directory, where the rule's walk starts.
- In a session that keeps the user's files in a storage backend rather than on disk, Claude Code reads the personal folder from that backend, which the rule's file reads may not reach.
- Claude Code compares the home folder in Unicode's composed form, while the rule compares it as the environment spells it, so where the home folder and the working directory spell an accented letter in different forms, the rule's walk can go past the home folder where Claude Code's stops before it.
- Claude Code matches the name `connector-downloads` loosely, in any letter case and ignoring invisible characters, a stream name after a colon, and trailing dots and spaces, splits a path at backslashes as well as slashes, and also checks where a folder's symbolic links lead; the rule passes over only a folder spelled exactly so between slashes on the path it walks, so it can count a script in a folder that Claude Code skips.
- Claude Code reads a saved script only if it is a regular file, or a symbolic link that it has vetted and that leads to a regular file outside `/proc`, `/sys` and `/dev/fd`, and it accepts a `.git` only if it leads to a file or a folder; the rule reads whatever a `.js` entry or a `.git` leads to, so it can count a script that Claude Code won't read, or end its walk at a `.git` that Claude Code passes over.
- A folder's listing describes a symbolic link itself, not the script it leads to, so the rule measures a linked script by the text it reads from it, encoded as UTF-8. For a script whose text doesn't read back byte for byte, such as one that isn't valid UTF-8, that can differ from the script's size in bytes, so near 512 KiB the rule can count a linked script that Claude Code skips as too large, or skip one that Claude Code loads.
- Claude Code decodes the escape sequences in the `name` of a `meta`, such as `\x2d` for a hyphen, while the rule compares the name as it is written, so it lets through the agents of a saved script whose name spells a character so.
- In a diskless session, which a host starts with a launch option that no mod call or environment variable reports, Claude Code walks no project folders and finds no repository, while the rule walks them as usual, so it can count a project script that Claude Code doesn't load.
- With `HOME` unset or empty, Claude Code takes the home folder from the user's account entry, which no mod call can read. The rule then doesn't stop its walk at the home folder and, without `CLAUDE_CONFIG_DIR`, looks for the personal folder in `/.claude/workflows` if `HOME` is empty and nowhere if it is unset, so it can count scripts that Claude Code doesn't load, and miss personal ones that it does.
- Claude Code reads a relative `CLAUDE_CONFIG_DIR` other than an empty one in the directory it runs in, the project root, while the rule's file reads resolve it against the working directory, so in a working directory other than the project root the rule looks for the personal folder in the wrong place.

The rule ties a workflow's agents to the Workflow call that started the run, and keeps which calls it checks in memory. So an agent whose spawn carries no such call, as Claude Code allows on a resumed or server-launched run, is not checked, and nor is an agent that a run started before the plugin's hooks reloaded spawns after the reload.

Like the rules plugin's hooks, the rule's hooks have no fallback: if one fails, Claude Code skips it and the call goes through unchecked.

An agent whose definition pins a model still needs one on the call, because the spawn doesn't show what a definition pins. After one refusal Claude names a model, and the call's model then replaces the definition's.

A subagent spawned without a model runs on whatever the session's settings and the agent's definition resolve to, falling back to the parent's model, rather than on a model chosen for its task.

## Requirements

The rule needs Claude Code 2.1.322 or later, the version it is built and tested against, on macOS or Linux. It is a mod, a TypeScript hooks module that Claude Code runs itself; mods are early access, and their API can change between releases. Claude Code doesn't load the module while its rollout flag for installed plugins' hooks modules is off; until the workspace is trusted, it runs none of the plugin's hooks.

## Install

```sh
claude plugin marketplace add trackness/rules
claude plugin install subagent-model@rules
```
