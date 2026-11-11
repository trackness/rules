import type { Register, RenderElement } from 'claude-code'

/** The time of day of a transcript timestamp, as HH:MM where the session runs. */
function timeOfDay(timestamp: string): string {
  return new Date(timestamp).toTimeString().slice(0, 5)
}

/** True if a line of the transcript records the row: a tool call by the id of the block the line holds, a reply by the line's own id. */
function recordsRow(line: string, id: string): boolean {
  return line.includes(`"id":"${id}"`) || line.includes(`"uuid":"${id}"`)
}

export const register: Register = (on) => {
  let transcript = ''
  on('classic.SessionStart', ($, e, next) => {
    transcript = e.transcript_path
    return next(e)
  })
  on('ui.render', async ($, e, next) => {
    // Read by tail: a plugin's own file read refuses a file over 4 MiB, which a transcript passes.
    const { stdout } = await $.process.run(['tail', '-n', '+1', transcript])
    const id = e.component === 'ToolGroup' ? String(e.props.calls[0]?.tool_use_id) : e.requestId
    const record = stdout.split('\n').find((line) => recordsRow(line, id))
    const { Box, Text } = $.ui.resolve(e)
    const shown = record === undefined ? '--:--' : timeOfDay(JSON.parse(record).timestamp)
    const time = h(Text, { dimColor: true }, `${shown} `)
    // Claude Code draws the blank line above a row as part of the row, so the time goes one line down to sit beside the ⏺.
    return h(Box, { flexDirection: 'row' }, h(Box, { marginTop: 1 }, time), await next(e)) as RenderElement
  })
}
