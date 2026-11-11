import type { On } from 'claude-code'
import { expect, test, type Engine } from 'claude-code/testing'

const TRANSCRIPT = '/home/me/.claude/projects/-srv-work/5eb6757b-439c-4746-a382-87be59dab35a.jsonl'

// A transcript file as Claude Code 2.1.322 writes one: a line of JSON per record.
function transcript(...records: Record<string, unknown>[]): string {
  return records.map((record) => `${JSON.stringify(record)}\n`).join('')
}

// The record of one block of an assistant's response: its own id, and the time the engine recorded for it.
function assistant(uuid: string, timestamp: string, block: Record<string, unknown>): Record<string, unknown> {
  const message = { id: 'msg_011Cgv9Q81JJs9vJdyRg2Cx2', type: 'message', role: 'assistant', model: 'claude-opus-5-5', content: [block] }
  return { parentUuid: null, isSidechain: false, message, type: 'assistant', uuid, timestamp }
}

// The record of a user-side row: a prompt, whose content is its text, or a tool's result, whose content is blocks.
function user(uuid: string, timestamp: string, content: string | Record<string, unknown>[]): Record<string, unknown> {
  return { parentUuid: null, isSidechain: false, message: { role: 'user', content }, type: 'user', uuid, timestamp }
}

// The time of day of a transcript timestamp where the test runs, as HH:MM.
function timeOfDay(timestamp: string): string {
  const at = new Date(timestamp)
  return `${String(at.getHours()).padStart(2, '0')}:${String(at.getMinutes()).padStart(2, '0')}`
}

// The host beneath the plugin: a session that starts, and its files. A plugin's own file read refuses a file over
// 4 MiB, which a transcript passes, so the files are read from a line on by tail.
function host(on: On, files: Record<string, string>) {
  on('classic.SessionStart', () => ({}))
  on('process.run', ($, e) => {
    const [command, flag, from, path] = e.argv
    const text = path === undefined ? undefined : files[path]
    if (command !== 'tail' || flag !== '-n' || text === undefined) {
      return { value: { exitCode: 1, stdout: '', stderr: `${String(command)}: ${String(path)}: No such file or directory\n`, isStdoutTruncated: false, isStderrTruncated: false } }
    }
    const stdout = text.split('\n').slice(Number(from) - 1).join('\n')
    return { value: { exitCode: 0, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
}

const SKILL_CALL = {
  tool_use_id: 'toolu_01Vj2T9PhgpmmFM912jvN8vE',
  tool: 'Skill',
  input: { skill: 'plugin-authoring' },
  isRunning: false,
  isErrored: false,
  isInterrupted: false,
  isExpanded: false,
  output: { success: true, commandName: 'plugin-authoring' },
}

// A session in which Claude thought, then called the Skill tool, each a minute apart.
const SKILL_SESSION = transcript(
  { type: 'mode', mode: 'default', sessionId: '5eb6757b-439c-4746-a382-87be59dab35a' },
  user('e0a040a6-aec9-4274-97fb-1f81430a0f1a', '2026-11-10T09:28:40.249Z', 'Load the plugin-authoring skill'),
  assistant('90d8109b-6574-4132-9ae5-a58647538c3a', '2026-11-10T09:29:59.956Z', { type: 'thinking', thinking: '', signature: 'EqQBCkYI' }),
  assistant('a2dc512c-f195-45f6-9351-8da543c2d09b', '2026-11-10T09:30:16.161Z', { type: 'tool_use', id: SKILL_CALL.tool_use_id, name: 'Skill', input: SKILL_CALL.input }),
  user('73140532-9633-4a83-ba1c-d78afab74721', '2026-11-10T09:31:02.391Z', [{ type: 'tool_result', tool_use_id: SKILL_CALL.tool_use_id, content: 'Launching skill: plugin-authoring' }]),
)

// The Skill call's row as the terminal draws it, in a session whose transcript holds SKILL_SESSION.
async function skillRow($: Engine, on: On) {
  host(on, { [TRANSCRIPT]: SKILL_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  return $.ui.mount({ plugin: 'rules', surface: 'terminal', component: 'ToolUse', requestId: SKILL_CALL.tool_use_id, props: SKILL_CALL })
}

test('a tool-call row shows the time the transcript records for its call', async ($, on) => {
  const ui = await skillRow($, on)
  expect((await ui.find({ type: 'Text' }))?.text).toBe(`${timeOfDay('2026-11-10T09:30:16.161Z')} `)
})

test('the time stands to the left of the row Claude Code draws', async ($, on) => {
  const ui = await skillRow($, on)
  expect(await ui.drawn()).toMatchObject({ type: 'Box', props: { flexDirection: 'row' }, children: [{}, { type: 'engine' }] })
})

test('the time is dim', async ($, on) => {
  const ui = await skillRow($, on)
  expect(await ui.find({ type: 'Text' })).toMatchObject({ props: { dimColor: true } })
})

test('the time sits one line down, beside the ⏺ under the blank line Claude Code draws above a row', async ($, on) => {
  const ui = await skillRow($, on)
  expect(await ui.drawn()).toMatchObject({ children: [{ type: 'Box', props: { marginTop: 1 } }, {}] })
})
