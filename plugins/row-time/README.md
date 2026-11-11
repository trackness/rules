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

Claude Code draws a resumed session's rows before it tells a mod where the transcript is. The mod draws them again as soon as it knows, so they carry their times from the start.

## The times file

The time of each row drawn is kept in a file beside the transcript, under the transcript's name with `.times` in place of `.jsonl`. It holds one line per row: the row's id, then the timestamp exactly as the transcript records it. The mod reads the file when the session starts, and a row whose time is in it is drawn without reading the transcript. The file is written whole, one write at a time, because Claude Code carries out writes made at once in no set order.

## What is left as Claude Code draws it

- Every row of a session that keeps no transcript.
- What stands outside the transcript: the spinner, the band above the prompt, the lines under it, and the status lines under the logo.
- A slash command's output, which stands under the command's own line, a line Claude Code gives no mod to draw.
- A shell command typed at the prompt with `!`, and its output: Claude Code gives a mod neither to draw.
- A subagent's closing `SubagentHandback` call, for which Claude Code draws no row.
- The reply Claude Code itself adds to a session it forks, `No response requested.`, for which it draws no row either.

## How it reads the transcript

The mod hooks `classic.SessionStart` for the transcript's path, `session.append` to draw the rows again, and `ui.render` to draw each row. It reads a transcript with `tail`, because a mod's own file read refuses a file over 4 MiB, which a transcript passes; so it needs `tail` on the `PATH`. A subagent's transcript is looked for in the `subagents` folder that Claude Code keeps beside the session's transcript, under the session's id.

In one run of Claude Code, each line of a transcript is read once, however long the transcript grows:

- Claude Code hands a mod only the first 4 MiB of what a command writes, so a longer transcript is read in stretches of whole lines, one after another.
- A single line longer than 4 MiB cannot be read whole, so it is passed over: the row it records shows `--:--`, and the rows after it are read as usual.
- Each read starts at the byte where the last one ended, which `tail` goes straight to; told a line to start at, it would count through every line before it.
- A read notes the time of every row in its lines, not only of the row it was made for, so a row recorded in lines already read is drawn without another read.
- Rows drawn while a read is under way wait for it. A row that another row's read leaves without a time then reads on itself: that read may have ended at an earlier transcript, or been aborted when Claude Code dropped the other row's drawing.

## Future improvements

Built and run against Claude Code 2.1.322. What the mod does not yet do right:

- **A reply in the ctrl+o view.** Claude Code draws its own time and model on a line above each reply there, in place of the blank line it draws in the normal view, and tells a mod nothing of it, so the reply's time lands one line below its `⏺`. Claude Code's code draws the same line above a reply in the normal view while its `showMessageTimestamps` setting is on. A fullscreen session without `--verbose` shows it.
- **A run of tool calls drawn unfolded.** Under `--verbose`, and in the ctrl+o view of the non-fullscreen screen, Claude Code draws a run's calls as rows of their own inside the run. The run and its first call then each carry a time, two on one line. A fullscreen session without `--verbose` does not show it.
- **The row for agents launched in one message.** When Claude launches two or more agents in one message, Claude Code draws them as one row of their own, such as `⏺ 4 background agents launched`, or `Running 2 agents…` and then `2 agents finished` for agents that run in the foreground. That row shows no time because Claude Code hands it to no mod: it draws the row with the Agent tool's own renderer for a group and raises `ui.render` for neither the row nor the calls in it. The transcript does record the time, on the line of each call, so what a mod is missing is a `ui.render` component for the row. Under `--verbose` and in the ctrl+o view Claude Code draws each call as a tool-call row of its own, which shows its time.

## Requirements

The mod is a TypeScript hooks module that Claude Code runs itself, built and tested against Claude Code 2.1.322; mods are early access, and their API can change between releases. Claude Code doesn't load the module while its rollout flag for installed plugins' hooks modules is off; until the workspace is trusted, it runs none of the plugin's hooks.

## Install

```sh
claude plugin marketplace add trackness/rules
claude plugin install row-time@rules
```
