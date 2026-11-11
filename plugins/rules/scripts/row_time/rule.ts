import type { Register, RenderElement } from 'claude-code'

export const register: Register = (on) => {
  let transcript = ''
  on('classic.SessionStart', ($, e, next) => {
    transcript = e.transcript_path
    return next(e)
  })
  on('ui.render', async ($, e) => {
    const { stdout } = await $.process.run(['tail', '-n', '+1', transcript])
    const record = stdout.split('\n').find((line) => line.includes(`"id":"${e.requestId}"`))
    const { Text } = $.ui.resolve(e)
    return h(Text, null, `${new Date(JSON.parse(record as string).timestamp).toTimeString().slice(0, 5)} `) as RenderElement
  })
}
