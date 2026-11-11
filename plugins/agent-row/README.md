# Agent rows

Claude Code's panel of background agents gives each running agent a row: its type, a live activity that changes as it works, and its running time and token count at the right. Several agents of one type look alike there, because the description each was spawned with shows only until the first progress summary replaces it, and the model each runs on is not shown at all. This plugin sets Claude Code's `subagentStatusLine` to a script that keeps each running agent's model and spawn description in its row, as fixed columns between its type and its activity, for as long as it runs, with its time and tokens still at the right edge as Claude Code writes them.

## The row

From the left: the agent's type, or its name if it has one, as Claude Code's own row shows it; its model; its spawn description; and its latest progress summary. Its running time and token count stand at the right edge. Claude Code still draws its own `○`, selection pointer and tree connector before the row, and dims it.

```text
general-purpose  opus-5.5    Review the auth module            Reading src/auth/session.py        1m 6s · ↓ 12.3k tokens
Explore          haiku-4.5   Find config loading                                                       5s · ↓ 850 tokens
payments-ci      sonnet-4.5  Investigate why the integration…  Running pytest -k payment agai…  1h 2m 5s · ↓ 1.2m tokens
Plan                         Plan the schema migration                                                                1s
```

- The model is its id without the provider's prefix, `claude-`, the snapshot's date or Bedrock's version, with the version's numbers joined by a dot: `claude-opus-5-5` is `opus-5.5`, and `us.anthropic.claude-sonnet-4-5-20250929-v1:0` is `sonnet-4.5`. Until Claude Code has resolved an agent's model, its cell is blank.
- The type, model and description columns are each as wide as their widest cell among the rows drawn, so they line up down the panel. East Asian wide and fullwidth characters count as the two columns a terminal draws them across.
- A description longer than 32 columns is cut, ending in `…`, so that it never crowds out the activity. The Agent tool asks for a description of 3 to 5 words, which 32 columns holds whole.
- Until an agent has a progress summary, Claude Code sends its description as its activity too, and the row leaves the activity blank rather than show the description twice.
- The time and tokens are written as Claude Code writes them in its own row: whole seconds under a minute, then minutes and seconds, with hours once there are any, and days with hours and minutes; the tokens plainly under a thousand, in thousands with `k`, in millions with `m`, and not at all while there are none.
- A row too wide for the panel is cut from the right of its left part, the activity first, so the time and tokens stay whole. A panel too narrow for even the time and tokens leaves that agent Claude Code's own row.

## Limits

- Claude Code runs the script every 5 seconds, and 300 ms after the number of rows changes, so the time in a row moves in steps rather than second by second.
- Claude Code's count of an agent's queued messages, the row's link and the suffix it adds for a nested agent are not drawn.
- The token count is always marked `↓`.
- An agent that is waiting still shows its running time.
- The rows of teammates and of workflows keep Claude Code's own drawing, because Claude Code passes the script only local agents.
- A stopped agent keeps Claude Code's own row: Claude Code sends no end time, so the script could not write how long the agent ran.
- A `subagentStatusLine` in the user's own settings replaces the plugin's, and when several plugins set one, only one plugin's applies.
- The script does not run while `disableAllHooks` or `allowManagedHooksOnly` is set, or before the workspace is trusted.

## Requirements

Built against Claude Code 2.1.322. The script runs with the `python3` on the `PATH`, which must be Python 3.9 or later, and uses only its standard library.

## Install

```sh
claude plugin marketplace add trackness/rules
claude plugin install agent-row@rules
```
