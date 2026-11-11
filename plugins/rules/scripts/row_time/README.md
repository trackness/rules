# Row times

Shows a dim `HH:MM` to the left of each row of the terminal transcript, on the line of the row's `⏺`:

    09:30 ⏺ Skill(plugin-authoring)

It is a mod: it changes what Claude Code draws, and blocks nothing.

## What gets a time

- A prompt, a reply and a tool call, each on its own first line.
- A run of tool calls that the transcript folds into one line, which shows the time of its first call.
- The other rows the transcript records, such as the line that closes a turn and the notices about a background agent.
- A subagent's rows, in the subagent's own view, read from the subagent's own transcript.

A tool call's result carries no time of its own: it moves right with its call, so it stays under it.

## Where the time comes from

The time is the timestamp Claude Code records for the row in the session's transcript, shown as the time of day where the session runs. The mod never reads the clock.

Claude Code draws a row a moment before it writes the row to the transcript. Until the transcript has the row's time, the row shows `--:--`. The mod draws the rows again 100 ms after each row joins the conversation, which fills the time in where the row stands; a row the transcript still lacks then is filled in at a later redraw.

## The times file

Each time read is kept in a file beside the transcript, under the transcript's name with `.times` in place of `.jsonl`. It holds one line per row: the row's id, then the timestamp exactly as the transcript records it. The mod reads the file when the session starts, and a row whose time is in it is drawn without reading the transcript.

## What is left as Claude Code draws it

- Every row of a session that keeps no transcript.
- What stands outside the transcript: the spinner, the band above the prompt and the lines under it.
- A slash command's output, which stands under the command's own line, a line Claude Code gives no mod to draw.
- A subagent's closing `SubagentHandback` call, for which Claude Code draws no row.

## How it reads the transcript

The mod hooks `classic.SessionStart` for the transcript's path, `session.append` to draw the rows again, and `ui.render` to draw each row. It reads a transcript with `tail`, because a mod's own file read refuses a file over 4 MiB, which a transcript passes; so it needs `tail` on the `PATH`. A subagent's transcript is looked for in the `subagents` folder that Claude Code keeps beside the session's transcript, under the session's id.

## Known limits

Built and run against Claude Code 2.1.322.

- In the ctrl+o view, Claude Code draws its own time and model on a line above each reply, in place of the blank line it draws there in the normal view, and tells a mod nothing of it. The reply's time then lands one line below its `⏺`.
