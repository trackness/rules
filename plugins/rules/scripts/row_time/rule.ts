import type { EngineInterface, Register, RenderElement } from 'claude-code'

/** What a row shows in place of its time, until the transcript holds one. */
const NOT_YET = '--:--'

/** How long the rows wait to be drawn again after the conversation gains a row, in milliseconds. */
const WRITE_WAIT_MS = 100

/** The time of day of a transcript timestamp, as HH:MM where the session runs. */
function timeOfDay(timestamp: string): string {
  return new Date(timestamp).toTimeString().slice(0, 5)
}

/** True if a line of the transcript records the row: a tool call by the id of the block the line holds, a reply by the line's own id. */
function recordsRow(line: string, id: string): boolean {
  return line.includes(`"id":"${id}"`) || line.includes(`"uuid":"${id}"`)
}

/** The file that keeps the times read from a transcript: beside the transcript, under its name. */
function timesFile(transcript: string): string {
  return transcript.replace(/jsonl$/, 'times')
}

/** The timestamp the transcript records for a row, kept in the times file once read; undefined until the transcript holds the row. */
async function recordedTimestamp($: EngineInterface, transcript: string, kept: Map<string, string>, id: string): Promise<string | undefined> {
  // Read by tail: a plugin's own file read refuses a file over 4 MiB, which a transcript passes.
  const { stdout } = await $.process.run(['tail', '-n', '+1', transcript])
  const record = stdout.split('\n').find((line) => recordsRow(line, id))
  const timestamp: string | undefined = record && JSON.parse(record).timestamp
  if (timestamp) {
    kept.set(id, timestamp)
    await $.fs.write(timesFile(transcript), [...kept].map(([row, at]) => `${row} ${at}\n`).join(''))
  }
  return timestamp
}

export const register: Register = (on) => {
  // The session's transcript file: empty until the session starts, and for a session that keeps none.
  let transcript = ''
  const kept = new Map<string, string>()
  on('classic.SessionStart', ($, e, next) => {
    transcript = e.transcript_path
    return next(e)
  })
  on('session.append', async ($, e, next) => {
    const stored = await next(e)
    // Claude Code writes a row to the transcript a moment after the row joins the conversation, so the redraw waits.
    $.clock.after(WRITE_WAIT_MS, () => $.ui.invalidate('ui.render'))
    return stored
  })
  on('ui.render', async ($, e, next) => {
    if (transcript === '') return next(e)
    // A folded run is timed by its first call.
    const id = e.component === 'ToolGroup' ? String(e.props.calls[0]?.tool_use_id) : e.requestId
    const timestamp = await recordedTimestamp($, transcript, kept, id)
    const { Box, Text } = $.ui.resolve(e)
    const time = h(Text, { dimColor: true }, `${timestamp ? timeOfDay(timestamp) : NOT_YET} `)
    // Claude Code draws the blank line above a row as part of the row, so the time goes one line down to sit beside the ⏺.
    return h(Box, { flexDirection: 'row' }, h(Box, { marginTop: 1 }, time), await next(e)) as RenderElement
  })
}
