import type { EngineInterface, Register, RenderElement } from 'claude-code'

/** What a row shows in place of its time, until the transcript holds one. */
const NOT_YET = '--:--'

/**
 * The rows of the terminal transcript that Claude Code records a time for: a prompt, a notice and a reply, a tool call,
 * a folded run of calls, and the line that closes a turn. Everything else it draws is left alone, such as what stands
 * outside the transcript, a call's result under its call, and a slash command's output under the command's own line.
 */
const TIMED = ['UserMessage', 'AssistantMessage', 'ToolUse', 'ToolGroup', 'TurnDuration']

/** The text of the reply Claude Code 2.1.322 adds to a session it forks, in the model's place. */
const ADDED_REPLY = 'No response requested.'

/** How long the rows wait to be drawn again after the conversation gains a row, in milliseconds. */
const WRITE_WAIT_MS = 100

/** The time of day of a transcript timestamp, as HH:MM where the session runs. */
function timeOfDay(timestamp: string): string {
  return new Date(timestamp).toTimeString().slice(0, 5)
}

/** Where a line of the transcript names a row it records: a tool call by the id of the block the line holds, a reply by the line's own id. */
const ROW_ID = /"(?:id|uuid)":"([^"]*)"/g

/**
 * The time a line of the transcript records. Undefined for a line that records none, and for the end of a line too
 * long to be read whole, which is no record.
 */
function timestampOf(line: string): string | undefined {
  try {
    return JSON.parse(line).timestamp
  } catch {
    return undefined
  }
}

/** Notes the time a line of the transcript records, under each row the line names that no earlier line has timed. */
function noteTimes(line: string, recorded: Map<string, string>): void {
  const timestamp = timestampOf(line)
  // Some lines carry no time, such as the copy Claude Code keeps of a request, which repeats the ids of its tool calls.
  if (!timestamp) return
  for (const [, id = ''] of line.matchAll(ROW_ID)) if (!recorded.has(id)) recorded.set(id, timestamp)
}

/** The file that keeps the times read from a transcript: beside the transcript, under its name. */
function timesFile(transcript: string): string {
  return transcript.replace(/jsonl$/, 'times')
}

/** The text of a times file: a line for each time kept, the id of its row, then the time as the transcript records it. */
function timesText(kept: Map<string, string>): string {
  return [...kept].map(([id, timestamp]) => `${id} ${timestamp}\n`).join('')
}

/** The times a times file's text keeps, by the id of their row. */
function keptTimes(text: string): Map<string, string> {
  return new Map(text.split('\n').filter(Boolean).map((line) => line.split(' ') as [string, string]))
}

/**
 * The transcripts a session's rows are recorded in that may hold lines not yet read: the session's own, then those of
 * its subagents that have grown since they were last read, which Claude Code keeps in the session's folder beside it.
 */
async function transcriptsOf($: EngineInterface, transcript: string, { bytesRead }: Reading): Promise<string[]> {
  const subagents = transcript.replace(/\.jsonl$/, '/subagents')
  const theirs = await $.fs.list(subagents).catch(() => [])
  // A listing gives a link the size 0, whatever it leads to, so a link is read on each time.
  const grown = theirs.filter((entry) => entry.name.endsWith('.jsonl') && (entry.isLink || entry.size > (bytesRead.get(`${subagents}/${entry.name}`) ?? 0)))
  return [transcript, ...grown.map((entry) => `${subagents}/${entry.name}`)]
}

/** What has been read of a session's transcripts so far. */
type Reading = {
  /** How many bytes of each transcript file have been read, by the file: its next read starts at the byte after them. */
  bytesRead: Map<string, number>
  /** The time of every row in the lines read, by the id of the row: the rows drawn, and those not yet drawn. */
  recorded: Map<string, string>
  /** The read now under way, which a row drawn during it waits for and does not start again. */
  underWay?: Promise<void>
}

/**
 * Reads on in a transcript file, from the byte after the last one read to its end: the time of every row in the
 * lines there is noted, and their bytes are counted as read.
 */
async function readOn($: EngineInterface, file: string, { bytesRead, recorded }: Reading): Promise<void> {
  // Read by tail: a plugin's own file read refuses a file over 4 MiB, which a transcript passes. Claude Code hands
  // back only the first 4 MiB of what a command writes, so the file is read a stretch at a time, each from the byte
  // after the last. tail goes straight to a byte it is told to start at, where it would count through every line
  // before a line. head stops each stretch one byte past those 4 MiB, the byte that tells Claude Code there is more,
  // so tail does not write out the rest of the file for every stretch. Claude Code aborts the read under way for a
  // drawing it drops, which is a read of nothing: the lines are read when a row is next looked for.
  for (;;) {
    const read = bytesRead.get(file) ?? 0
    const stretch = ['sh', '-c', 'tail -c "+$1" "$2" | head -c 4194305', 'sh', String(read + 1), file]
    const { stdout, isStdoutTruncated } = await $.process.run(stretch).catch(() => ({ stdout: '', isStdoutTruncated: false }))
    // What follows the last line break is a line cut short, or nothing.
    const wholeLines = stdout.slice(0, stdout.lastIndexOf('\n') + 1)
    for (const line of wholeLines.split('\n').slice(0, -1)) noteTimes(line, recorded)
    // A stretch cut before any line break is part of one line longer than Claude Code hands back. It is passed over
    // whole, and the end of that line, which opens a later stretch, records nothing.
    const passedOver = isStdoutTruncated && wholeLines === '' ? stdout : wholeLines
    bytesRead.set(file, read + new TextEncoder().encode(passedOver).length)
    if (!isStdoutTruncated) return
  }
}

/** Reads on in a session's transcripts, one after another, as far as the one that records a row. */
async function lookFor($: EngineInterface, transcript: string, reading: Reading, id: string): Promise<void> {
  for (const file of await transcriptsOf($, transcript, reading)) {
    await readOn($, file, reading)
    if (reading.recorded.has(id)) break
  }
}

/** The times kept for a session's rows. */
type Kept = {
  /** The times of the rows drawn so far, as the transcript records them, by the id of their row: what the times file holds. */
  times: Map<string, string>
  /** The last write of the times file, which the next one follows. */
  written: Promise<void>
  /** The write that waits for the one under way and has not yet started: it writes every time kept by when it starts. */
  waiting?: Promise<void>
}

/** Keeps a row's time, in the times file too. */
async function keep($: EngineInterface, transcript: string, kept: Kept, id: string, timestamp: string): Promise<void> {
  kept.times.set(id, timestamp)
  const write = () => {
    delete kept.waiting
    return $.fs.write(timesFile(transcript), timesText(kept.times))
  }
  // The file is written whole, and Claude Code carries out the writes under way at once in no set order: each write
  // follows the last, made or refused, so the one that lands last holds every time. A time kept while a write waits
  // goes in that write, so a write per row cannot queue up and eat the hook's time.
  await (kept.waiting ??= kept.written = kept.written.then(write, write))
}

/** The read now under way of a session's transcripts, or else one started to look for a row. */
function readUnderWay($: EngineInterface, transcript: string, reading: Reading, id: string): Promise<void> {
  return (reading.underWay ??= lookFor($, transcript, reading, id).finally(() => delete reading.underWay))
}

/**
 * The timestamp the transcript records for a row: the one kept, or else the one noted in a read of the transcript,
 * which is then kept, in the times file too. A row no read has yet timed waits for the read under way, or starts one.
 * Undefined until the transcript holds the row.
 */
async function recordedTimestamp($: EngineInterface, transcript: string, kept: Kept, reading: Reading, id: string): Promise<string | undefined> {
  if (kept.times.has(id)) return kept.times.get(id)
  const isAnotherRowsRead = reading.underWay !== undefined
  if (!reading.recorded.has(id)) await readUnderWay($, transcript, reading, id)
  // Another row's read ends at the transcript that records that row, and is cut short if Claude Code drops that
  // row's drawing: a row it leaves untimed reads on itself.
  if (isAnotherRowsRead && !reading.recorded.has(id)) await readUnderWay($, transcript, reading, id)
  const timestamp = reading.recorded.get(id)
  // A refused write, such as on a full disk, loses the file the time, not the row: a later write holds it.
  if (timestamp) await keep($, transcript, kept, id, timestamp).catch(() => {})
  return timestamp
}

export const register: Register = (on) => {
  // The session's transcript file: empty until the session starts, and for a session that keeps none.
  let transcript = ''
  const kept: Kept = { times: new Map(), written: Promise.resolve() }
  const reading: Reading = { bytesRead: new Map(), recorded: new Map() }
  // No .catch: Claude Code skips a hook that fails, and the session goes on as it would without the mod.
  on('classic.SessionStart', async ($, e, next) => {
    transcript = e.transcript_path
    kept.times = keptTimes(await $.fs.read(timesFile(transcript)).catch(() => ''))
    // Claude Code draws a resumed session's rows before it starts the session, while the transcript is not yet
    // known: they are drawn again now that it is.
    $.ui.invalidate('ui.render')
    return next(e)
  })
  on('session.append', async ($, e, next) => {
    const stored = await next(e)
    // Claude Code writes a row to the transcript a moment after the row joins the conversation, so the redraw waits.
    $.clock.after(WRITE_WAIT_MS, () => $.ui.invalidate('ui.render'))
    return stored
  })
  on('ui.render', async ($, e, next) => {
    if (transcript === '' || e.surface !== 'terminal' || !TIMED.includes(e.component)) return next(e)
    // A subagent ends with a SubagentHandback call, for which Claude Code draws no row.
    if (e.component === 'ToolUse' && e.props.tool === 'SubagentHandback') return next(e)
    // Nor does it draw one for the reply it adds to a forked session itself, which only its text tells apart.
    if (e.component === 'AssistantMessage' && e.props.text === ADDED_REPLY) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    // A folded run is timed by its first call.
    const id = e.component === 'ToolGroup' ? String(e.props.calls[0]?.tool_use_id) : e.requestId
    const timestamp = await recordedTimestamp($, transcript, kept, reading, id)
    const time = h(Text, { dimColor: true }, `${timestamp ? timeOfDay(timestamp) : NOT_YET} `)
    const row = await next(e)
    // Claude Code sizes what it draws in a row from the terminal's width, not from the room the row has, so the time
    // takes none of the row's columns: drawn after the row, it is painted over it, on the blank line Claude Code draws
    // directly above the row's ⏺. Above a subagent's prompt from main it draws its "From main" label in place of that
    // blank line, so that time has a line of its own, above the label.
    const isFromMain = e.component === 'UserMessage' && e.props.origin.kind === 'coordinator'
    const parts = isFromMain ? [time, row] : [row, h(Box, { position: 'absolute', top: 0, left: 0 }, time)]
    // A blank line of the mod's own keeps the row and its time apart from what is drawn before them.
    return h(Box, { flexDirection: 'column', marginTop: 1 }, ...parts) as RenderElement
  })
}
