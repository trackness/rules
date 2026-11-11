import type { EngineInterface, Register, RenderElement } from 'claude-code'

/** What a row shows in place of its time, until the transcript holds one. */
const NOT_YET = '--:--'

/** As wide as a time and the space after it: what stands left of a part of a row that carries no time. */
const NO_TIME = '      '

/** What Claude Code draws outside the transcript: the spinner, the band above the prompt and the lines under it. */
const OUTSIDE_THE_TRANSCRIPT = ['Spinner', 'AbovePrompt', 'PromptHint', 'SessionMode']

/** How long the rows wait to be drawn again after the conversation gains a row, in milliseconds. */
const WRITE_WAIT_MS = 100

/** The time of day of a transcript timestamp, as HH:MM where the session runs. */
function timeOfDay(timestamp: string): string {
  return new Date(timestamp).toTimeString().slice(0, 5)
}

/** Where a line of the transcript names a row it records: a tool call by the id of the block the line holds, a reply by the line's own id. */
const ROW_ID = /"(?:id|uuid)":"([^"]*)"/g

/** Notes the time a line of the transcript records, under each row the line names that no earlier line has timed. */
function noteTimes(line: string, recorded: Map<string, string>): void {
  const { timestamp } = JSON.parse(line)
  // Some lines carry no time, such as the copy Claude Code keeps of a request, which repeats the ids of its tool calls.
  if (!timestamp) return
  for (const [, id] of line.matchAll(ROW_ID)) if (!recorded.has(id)) recorded.set(id, timestamp)
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
 * The transcripts a session's rows are recorded in: the session's own, then those of its subagents, which Claude Code
 * keeps in the session's folder beside it.
 */
async function transcriptsOf($: EngineInterface, transcript: string): Promise<string[]> {
  const subagents = transcript.replace(/\.jsonl$/, '/subagents')
  const theirs = await $.fs.list(subagents).catch(() => [])
  return [transcript, ...theirs.map((entry) => `${subagents}/${entry.name}`)]
}

/** What has been read of a session's transcripts so far. */
type Reading = {
  /** How many lines of each transcript file have been read, by the file: its next read starts at the line after them. */
  linesRead: Map<string, number>
  /** The time of every row in the lines read, by the id of the row: the rows drawn, and those not yet drawn. */
  recorded: Map<string, string>
  /** The read now under way, which a row drawn during it waits for and does not start again. */
  underWay?: Promise<void>
}

/**
 * Reads on in a transcript file, from the line after the last one read to its end: the time of every row in those
 * lines is noted, and the lines are counted as read.
 */
async function readOn($: EngineInterface, file: string, { linesRead, recorded }: Reading): Promise<void> {
  // Read by tail: a plugin's own file read refuses a file over 4 MiB, which a transcript passes. Claude Code hands
  // back only the first 4 MiB of what tail writes, so the file is read a stretch at a time, each from the line after
  // the last. Claude Code aborts the read under way for a drawing it drops, which is a read of nothing: the lines are
  // read when a row is next looked for.
  for (;;) {
    const read = linesRead.get(file) ?? 0
    const { stdout, isStdoutTruncated } = await $.process.run(['tail', '-n', `+${read + 1}`, file]).catch(() => ({ stdout: '', isStdoutTruncated: false }))
    // What follows the last line break is a line cut short, or nothing.
    const lines = stdout.split('\n').slice(0, -1)
    for (const line of lines) noteTimes(line, recorded)
    linesRead.set(file, read + lines.length)
    // There is no more to read: the stretch was handed back whole, or held no whole line, being cut inside a first
    // line longer than Claude Code hands back.
    if (!isStdoutTruncated || lines.length === 0) return
  }
}

/** Reads on in a session's transcripts, one after another, as far as the one that records a row. */
async function lookFor($: EngineInterface, transcript: string, reading: Reading, id: string): Promise<void> {
  for (const file of await transcriptsOf($, transcript)) {
    await readOn($, file, reading)
    if (reading.recorded.has(id)) break
  }
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
async function recordedTimestamp($: EngineInterface, transcript: string, kept: Map<string, string>, written: { last: Promise<void> }, reading: Reading, id: string): Promise<string | undefined> {
  if (kept.has(id)) return kept.get(id)
  const isAnotherRowsRead = reading.underWay !== undefined
  if (!reading.recorded.has(id)) await readUnderWay($, transcript, reading, id)
  // Another row's read ends at the transcript that records that row, and is cut short if Claude Code drops that
  // row's drawing: a row it leaves untimed reads on itself.
  if (isAnotherRowsRead && !reading.recorded.has(id)) await readUnderWay($, transcript, reading, id)
  const timestamp = reading.recorded.get(id)
  if (timestamp) {
    kept.set(id, timestamp)
    const write = () => $.fs.write(timesFile(transcript), timesText(kept))
    await (written.last = written.last.then(write, write))
  }
  return timestamp
}

export const register: Register = (on) => {
  // The session's transcript file: empty until the session starts, and for a session that keeps none.
  let transcript = ''
  // The times read so far, as the transcript records them, by the id of their row: what the times file holds.
  let kept = new Map<string, string>()
  const written = { last: Promise.resolve() }
  const reading: Reading = { linesRead: new Map(), recorded: new Map() }
  on('classic.SessionStart', async ($, e, next) => {
    transcript = e.transcript_path
    kept = keptTimes(await $.fs.read(timesFile(transcript)).catch(() => ''))
    return next(e)
  })
  on('session.append', async ($, e, next) => {
    const stored = await next(e)
    // Claude Code writes a row to the transcript a moment after the row joins the conversation, so the redraw waits.
    $.clock.after(WRITE_WAIT_MS, () => $.ui.invalidate('ui.render'))
    return stored
  })
  on('ui.render', async ($, e, next) => {
    if (transcript === '' || OUTSIDE_THE_TRANSCRIPT.includes(e.component)) return next(e)
    // A subagent ends with a SubagentHandback call, for which Claude Code draws no row.
    if (e.component === 'ToolUse' && e.props.tool === 'SubagentHandback') return next(e)
    // A slash command's output stands under the command's own line, which Claude Code hands no plugin to draw.
    if (e.component === 'CommandOutput') return next(e)
    const { Box, Text } = $.ui.resolve(e)
    // A result is part of its call's row: it moves right with the call, and the call carries the time.
    if (e.component === 'ToolResult') return h(Box, { flexDirection: 'row' }, h(Text, null, NO_TIME), await next(e)) as RenderElement
    // A folded run is timed by its first call.
    const id = e.component === 'ToolGroup' ? String(e.props.calls[0]?.tool_use_id) : e.requestId
    const timestamp = await recordedTimestamp($, transcript, kept, written, reading, id)
    const time = h(Text, { dimColor: true }, `${timestamp ? timeOfDay(timestamp) : NOT_YET} `)
    // Claude Code draws the blank line above a row as part of the row, so the time goes one line down to sit beside
    // the ⏺. Above a subagent's prompt from main it draws its "From main" label in place of the blank line.
    const isFromMain = e.component === 'UserMessage' && e.props.origin.kind === 'coordinator'
    return h(Box, { flexDirection: 'row' }, h(Box, { marginTop: isFromMain ? 0 : 1 }, time), await next(e)) as RenderElement
  })
}
