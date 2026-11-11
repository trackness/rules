# Row times

Shows a dim `HH:MM` at the left of the line directly above each row's `⏺` in the terminal transcript, under a blank line that sets the row and its time apart from what is drawn before them:

```text
⏺ I'll load the skill.

09:30
⏺ Skill(plugin-authoring)
```

It is a mod: it changes what Claude Code draws, and blocks nothing.

## What gets a time

- A prompt, a reply and a tool call.
- A run of tool calls that the transcript folds into one line, which shows the time of its first call.
- The other rows the transcript records, such as the line that closes a turn and the notices about a background agent.
- A subagent's rows, in the subagent's own view, read from the subagent's own transcript.

A tool call's result carries no time of its own: it stands under its call, which carries the time.

## Where the time stands

Claude Code draws a blank line above each row, as part of the row, directly above the row's `⏺`, and the time stands at the left of that line. It is drawn over the row, after it, so it takes none of the row's columns. That matters because Claude Code sizes what it draws in a row from the terminal's width, not from the room the row has: a time drawn beside a row would leave the row a few columns short, and a wide Markdown table in a reply would then wrap every one of its lines.

Above the time the mod adds a blank line of its own, so a row and its time stand apart from whatever is drawn before them. Each timed row therefore takes one line more than Claude Code draws for it; a tool call's result, and every row left as Claude Code draws it, takes no more.

Above a subagent's prompt from main, Claude Code draws its "From main" label in place of the blank line, where the time would cover the label's start. That prompt's time has a line of its own instead, above the label, at its left, under the blank line the mod adds, so the label and the time are both whole; that row takes two lines more than Claude Code draws for it.

## Where the time comes from

The time is the timestamp Claude Code records for the row in the session's transcript, shown as the time of day where the session runs. The mod never reads the clock.

Claude Code draws a row a moment before it writes the row to the transcript. Until the transcript has the row's time, the row shows `--:--`. The mod draws the rows again 300 ms after each row joins the conversation, which fills the time in where the row stands, since Claude Code writes what it has queued for the transcript every 100 ms; a row the transcript still lacks then is filled in at a later redraw.

Claude Code draws a resumed session's rows before it tells a mod where the transcript is. The mod draws them again as soon as it knows, so they carry their times from the start.

Claude Code tells a mod where the transcript is only when the session starts, so the mod holds the path in the session: a reload of the mod takes it up again and goes on timing rows. A mod first enabled in the middle of a session has no path to take up, so its times start with the next session.

## The times file

The time of each row drawn is kept in a file beside the transcript, under the transcript's name with `.times` in place of `.jsonl`. It holds one line per row: the row's id, then the timestamp exactly as the transcript records it. The mod reads the file when the session starts, and a row whose time is in it is drawn without reading the transcript. The file is written whole, one write at a time, because Claude Code carries out writes made at once in no set order. At most one write waits behind the one under way, and every time kept while it waits goes into it, so rows drawn at once share a write. A refused write, such as on a full disk, still leaves the row its time, and the next write that is made holds it.

## What is left as Claude Code draws it

- Every row of a session that keeps no transcript, or whose transcript's name does not end in `.jsonl`, the ending the times file's name replaces, so the mod never writes over the transcript.
- Everything drawn on a surface other than the terminal, such as the desktop app or VS Code.
- What stands outside the transcript: the spinner, the band above the prompt, the lines under it, the status lines under the logo, a pane or a row a plugin places, a plugin's backdrop, and the dialog the AskUserQuestion tool opens.
- A tool call's result, and the run-in-background hint under a running call, which stand under the call.
- A slash command's output, which stands under the command's own line, a line Claude Code gives no mod to draw.
- A shell command typed at the prompt with `!`, and its output: Claude Code gives a mod neither to draw.
- A subagent's closing `SubagentHandback` call, for which Claude Code draws no row.
- The reply Claude Code itself adds to a session it forks, `No response requested.`, for which it draws no row either.

## How it reads the transcript

The mod hooks `classic.SessionStart` for the transcript's path, which it holds in the session's state, `session.start` to take that path up again after a reload, `session.append` to draw the rows again, and `ui.render` to draw each row. It reads a transcript with `tail`, piped through `head` by `sh`, because a mod's own file read refuses a file over 4 MiB, which a transcript passes; so it needs `sh`, `tail` and `head` on the `PATH`. A subagent's transcript is looked for in the `subagents` folder that Claude Code keeps beside the session's transcript, under the session's id, and read on only once the folder's listing shows it has grown past what was read of it.

In one load of the mod, each line of a transcript is read once, however long the transcript grows; a reload of the mod reads it again from the start:

- Claude Code hands a mod only the first 4 MiB of what a command writes, so a longer transcript is read in stretches of whole lines, one after another. `head` ends each stretch one byte past those 4 MiB, the byte that tells Claude Code there is more, so `tail` never writes out the rest of the file for a stretch.
- A single line longer than 4 MiB cannot be read whole, so it is passed over: the row it records shows `--:--`, and the rows after it are read as usual.
- Each read starts at the byte where the last one ended, which `tail` goes straight to; told a line to start at, it would count through every line before it.
- A read notes the time of every row in its lines, not only of the row it was made for, so a row recorded in lines already read is drawn without another read.
- Rows drawn while a read is under way wait for it. A row that another row's read leaves without a time then reads on itself: that read may have ended at an earlier transcript, or been aborted when Claude Code dropped the other row's drawing.

## Future improvements

Built and run against Claude Code 2.1.322. What the mod does not yet do right:

- **A reply in the ctrl+o view.** Claude Code draws its own time and model on a line above each reply there, in place of the blank line it draws in the normal view, and tells a mod nothing of it, so the mod's time is painted over the start of that line, hiding as many of its columns as the time and the space after it take. Claude Code's code draws the same line above a reply in the normal view while its `showMessageTimestamps` setting is on. A fullscreen session without `--verbose` shows it.
- **A run of tool calls drawn unfolded.** Under `--verbose`, and in the ctrl+o view of the non-fullscreen screen, Claude Code draws a run's calls as rows of their own inside the run. The run and its first call then each carry the same time, each at the left of its own top line, so the time shows twice, and each call in the run takes a line more than Claude Code draws, for the blank line the mod adds above it. A fullscreen session without `--verbose` does not show it.
- **What Claude Code draws on the line above a row's `⏺`.** The time is painted over the start of that line, whatever Claude Code draws there. Above most rows that line is blank. The mod tells one other line apart, the "From main" label above a subagent's prompt from main, and gives that row's time a line of its own; any other line Claude Code draws there, such as its own time and model above a reply in the ctrl+o view, loses its start to the time.
- **A row whose time has scrolled out of view.** In a fullscreen session, a row scrolled so that the line its time stands on is above the view shows no time, though the rest of the row is still in view.
- **The row for agents launched in one message.** When Claude launches two or more agents in one message, Claude Code draws them as one row of their own, such as `⏺ 4 background agents launched`, or `Running 2 agents…` and then `2 agents finished` for agents that run in the foreground. That row shows no time because Claude Code hands it to no mod: it draws the row with the Agent tool's own renderer for a group and raises `ui.render` for neither the row nor the calls in it. The transcript does record the time, on the line of each call, so what a mod is missing is a `ui.render` component for the row. Under `--verbose` and in the ctrl+o view Claude Code draws each call as a tool-call row of its own, which shows its time.

## Requirements

The mod is a TypeScript hooks module that Claude Code runs itself, built and tested against Claude Code 2.1.322; mods are early access, and their API can change between releases. Claude Code doesn't load the module while its rollout flag for installed plugins' hooks modules is off; until the workspace is trusted, it runs none of the plugin's hooks.

## Install

```sh
claude plugin marketplace add trackness/rules
claude plugin install row-time@rules
```
