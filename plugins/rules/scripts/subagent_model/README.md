# Explicit subagent model

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
