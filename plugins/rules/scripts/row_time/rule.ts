import type { Register, RenderElement } from 'claude-code'

/** The time of day of a transcript timestamp, as HH:MM where the session runs. */
function timeOfDay(timestamp: string): string {
  return new Date(timestamp).toTimeString().slice(0, 5)
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
    const record = stdout.split('\n').find((line) => line.includes(`"id":"${e.requestId}"`))
    const { Box, Text } = $.ui.resolve(e)
    const time = h(Text, { dimColor: true }, `${timeOfDay(JSON.parse(record as string).timestamp)} `)
    return h(Box, { flexDirection: 'row' }, time, await next(e)) as RenderElement
  })
}
