# Agent rows

Claude Code's panel of background agents gives each agent a row, with its type, its activity, and its time and token count at the right, while it runs and for about 30 seconds after it stops, sometimes longer. Several agents of one type look alike there, because the description each was spawned with shows only until the first progress summary replaces it, and the model each runs on is not shown at all. This plugin sets Claude Code's `subagentStatusLine` to a script that keeps each agent's model and spawn description in its row, as fixed columns between its type and its activity, for as long as the row is in the panel, running or stopped, with its time and tokens still at the right edge.

## The row

From the left: the agent's type, or its name if it has one, as Claude Code's own row shows it; its model; its spawn description; and its activity. At the right edge stand its running time while it runs, or its status once it has stopped, then its token count. Claude Code still draws its own `○`, selection pointer and tree connector before the row, and dims it.

```text
general-purpose  opus-5.5    Review the auth module            Reading src/auth/session.py        1m 6s · ↓ 12.3k tokens
Explore          haiku-4.5   Find config loading               no summary yet                          5s · ↓ 850 tokens
payments-ci      sonnet-4.5  Investigate why the integration…  Running pytest -k payment agai…  1h 2m 5s · ↓ 1.2m tokens
Plan             opus-5.5    Plan the schema migration         no summary                     completed · ↓ 31.0k tokens
Explore          haiku-4.5   Count files by extension          Counting files under plugins/  completed · ↓ 29.4k tokens
```

- The model is its id without the provider's prefix, `claude-`, the snapshot's date (`-20250929` or Vertex's `@20250929`) or Bedrock's version (`-v1` or `-v1:0`), with the version's numbers joined by a dot: `claude-opus-5-5` is `opus-5.5`, and `us.anthropic.claude-sonnet-4-5-20250929-v1:0` is `sonnet-4.5`. Claude Code sends every agent's model from the start; only a task it restored from disk comes without one, and that cell is blank.
- The type, model and description columns are each as wide as their widest cell among all the agents the script is sent, running and stopped, so they line up down the panel. East Asian wide and fullwidth characters count as the two columns a terminal draws them across.
- A description longer than 32 columns is cut, ending in `…`, so that it never crowds out the activity. The Agent tool asks for a description of 3 to 5 words, which 32 columns holds whole. A name is cut the same way at 24 columns and a model at 16, so that no one long id empties every row's activity.
- The name, description and summary are cleaned as Claude Code cleans them for its own row: control characters are dropped, and line breaks and runs of whitespace become one space.
- The activity is the agent's latest progress summary, a line of at most 100 characters that a background model writes for it: the first about 30 seconds after the agent starts, then a new one at most once every 30 seconds. Each shows in the row at the script's next run, within about 5 seconds. Until the first, the activity reads `no summary yet`, and an agent that runs for less than about 30 seconds never gets one. Claude Code sends the description in place of a summary until there is one, and the row does not show it twice.
- Once an agent has stopped, its status, `completed`, `failed` or `killed`, stands where its running time was: Claude Code sends no end time, so a time counted from the agent's start would go on growing past its end. Its model and description stay, and so does its last summary, or `no summary` if it never had one, until Claude Code removes the row.
- A stopped agent that is resumed shows a running time again, counted from when it first started and so including the time it was stopped, because Claude Code sends it with the same start time.
- The time and tokens are written as Claude Code writes them in its own row: whole seconds under a minute, then minutes and seconds, with hours once there are any, and days with hours and minutes; the tokens plainly under a thousand, in thousands with `k`, in millions with `m`, and not at all while there are none.
- A row too wide for the panel is cut from the right of its left part, the activity first, so the time and tokens stay whole. A panel too narrow for even one row's time and tokens leaves every row to Claude Code's own drawing, so that the rows still line up.

## Limits

- Claude Code runs the script every 5 seconds, and 300 ms after the number of agents it is sent changes or the terminal is resized, but not when an agent stops, is resumed or gets a new summary. So the time in a row moves in 5-second steps, and a stop, a resume or a new summary shows in the row up to 5 seconds after it happens.
- An agent just launched has Claude Code's own row, without its model and out of line with the others, for the 300 ms or so until the script next runs. A run that fails, takes more than 5 seconds or prints nothing leaves every row to Claude Code's own drawing until the next run that succeeds.
- A nested agent, one that another agent launched, has less room for its row than a top-level agent, by the width of its tree connector, and nothing Claude Code sends says which agents are nested, so the script draws its row as wide as the others. Its columns therefore stand that much to the right of the others', and Claude Code cuts the end of its row, where its time and tokens stand, with `…`.
- Claude Code's count of an agent's queued messages, the row's link and the suffix it adds for a nested agent are not drawn.
- The token count is always marked `↓`: Claude Code's own row marks it `↑` until the agent has had some activity, and Claude Code does not send which it is.
- The running time counts from the agent's start, including any time it spent waiting on a permission prompt, which Claude Code's own row leaves out; Claude Code does not send that time.
- The rows of teammates and of workflows keep Claude Code's own drawing, and so do not line up with the plugin's rows, because Claude Code passes the script only local agents.
- A `subagentStatusLine` in the user's own settings replaces the plugin's, and when several plugins set one, only one plugin's applies.
- The script does not run while `disableAllHooks` or `allowManagedHooksOnly` is set, or before the workspace is trusted.

## Requirements

Claude Code 2.1.322 or later, on macOS or Linux. The script runs with the `python3` on the `PATH` and uses only its standard library.

## Install

```sh
claude plugin marketplace add trackness/rules
claude plugin install agent-row@rules
```
