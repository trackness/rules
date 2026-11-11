import type { On } from 'claude-code'
import { expect, mock, test, type Engine } from 'claude-code/testing'

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

// How much of what a command writes Claude Code 2.1.322 hands a plugin: the first 4 MiB, the rest dropped.
const STDOUT_LIMIT = 4 * 1024 * 1024

// The host beneath the plugin: a session that starts, and its files. A plugin's own file read refuses a file over
// 4 MiB, which a transcript passes, so the files are read from a line on by tail. A write replaces a file whole.
// Answers with the commands the plugin ran.
function host(on: On, files: Record<string, string>) {
  const ran: (readonly string[])[] = []
  on('classic.SessionStart', () => ({}))
  on('fs.read', ($, e) => {
    const text = files[e.path]
    if (text === undefined) throw new Error(`ENOENT: no such file or directory, open '${e.path}'`)
    return { value: text }
  })
  on('fs.write', ($, e) => {
    files[e.path] = e.text
    return { value: undefined }
  })
  on('fs.list', ($, e) => {
    const names = Object.keys(files).filter((path) => path.startsWith(`${e.path}/`)).map((path) => path.slice(e.path.length + 1))
    if (names.length === 0) throw new Error(`ENOENT: no such file or directory, scandir '${e.path}'`)
    return { value: names.filter((name) => !name.includes('/')).map((name) => ({ name, kind: 'file' as const, size: 0, mtimeMs: 0, isLink: false })) }
  })
  on('process.run', ($, e) => {
    ran.push(e.argv)
    const [command, flag, from, path] = e.argv
    const text = path === undefined ? undefined : files[path]
    if (command !== 'tail' || flag !== '-n' || text === undefined) {
      return { value: { exitCode: 1, stdout: '', stderr: `${String(command)}: ${String(path)}: No such file or directory\n`, isStdoutTruncated: false, isStderrTruncated: false } }
    }
    const stdout = text.split('\n').slice(Number(from) - 1).join('\n')
    return { value: { exitCode: 0, stdout: stdout.slice(0, STDOUT_LIMIT), stderr: '', isStdoutTruncated: stdout.length > STDOUT_LIMIT, isStderrTruncated: false } }
  })
  return ran
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

// The Skill call's row as the terminal draws it.
function drawSkillRow($: Engine) {
  return $.ui.mount({ plugin: 'rules', surface: 'terminal', component: 'ToolUse', requestId: SKILL_CALL.tool_use_id, props: SKILL_CALL })
}

// The Skill call's row as the terminal draws it, in a session whose transcript holds SKILL_SESSION.
async function skillRow($: Engine, on: On) {
  host(on, { [TRANSCRIPT]: SKILL_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  return drawSkillRow($)
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

const REPLY_ID = '8d4d70ff-4e29-4404-bc72-1641876dc44a'
const REPLY = { text: 'The plugin-authoring skill is loaded.', isFirstOfReply: true }

// The Skill session gone on: two minutes after the call, Claude replied.
const REPLY_SESSION = SKILL_SESSION + transcript(assistant(REPLY_ID, '2026-11-10T09:32:41.970Z', { type: 'text', text: REPLY.text }))

// The reply's row as the terminal draws it.
function drawReplyRow($: Engine) {
  return $.ui.mount({ plugin: 'rules', surface: 'terminal', component: 'AssistantMessage', requestId: REPLY_ID, props: REPLY })
}

test('a reply row shows the time the transcript records for its text', async ($, on) => {
  host(on, { [TRANSCRIPT]: REPLY_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const ui = await drawReplyRow($)
  expect((await ui.find({ type: 'Text' }))?.text).toBe(`${timeOfDay('2026-11-10T09:32:41.970Z')} `)
})

// One call of a run of reads, as a folded run's row carries it.
function read(toolUseId: string, path: string) {
  return { tool_use_id: toolUseId, tool: 'Read', input: { file_path: path }, isRunning: false, isErrored: false, isInterrupted: false }
}

test('a run of tool calls folded into one line shows the time of its first call', async ($, on) => {
  const readme = read('toolu_01X3dkg4hJLyTckexfy9gDxu', '/srv/work/README.md')
  const contributing = read('toolu_01XTEN2VL3Mhc1dMcMLt29rz', '/srv/work/CONTRIBUTING.md')
  // A session in which Claude read two files, a minute apart.
  const session = transcript(
    user('9ede0371-94f3-4870-99bf-a7c678837b16', '2026-11-10T09:40:52.249Z', 'Read the README and the contributing guide'),
    assistant('293589d0-56e7-4054-97df-b0b2665696e7', '2026-11-10T09:41:07.346Z', { type: 'tool_use', id: readme.tool_use_id, name: 'Read', input: readme.input }),
    user('ef33aa01-5c82-44ac-b682-64d7d7ff8d71', '2026-11-10T09:41:07.568Z', [{ type: 'tool_result', tool_use_id: readme.tool_use_id, content: '# rules' }]),
    assistant('e3915a8d-e053-4bfd-8d18-364e8d171342', '2026-11-10T09:42:30.521Z', { type: 'tool_use', id: contributing.tool_use_id, name: 'Read', input: contributing.input }),
    user('ae507d63-d538-413e-b2ca-34432746deac', '2026-11-10T09:42:30.746Z', [{ type: 'tool_result', tool_use_id: contributing.tool_use_id, content: '# Contributing' }]),
  )
  host(on, { [TRANSCRIPT]: session })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const run = { calls: [readme, contributing], isActive: false, isExpanded: false, isCallsOnly: true }
  const ui = await $.ui.mount({ plugin: 'rules', surface: 'terminal', component: 'ToolGroup', requestId: 'collapsed-293589d0-56e7-4054-97df-b0b2665696e7', props: run })
  expect((await ui.find({ type: 'Text' }))?.text).toBe(`${timeOfDay('2026-11-10T09:41:07.346Z')} `)
})

// The Skill session's transcript as it stands when the call's row is first drawn: Claude Code has yet to write the call.
const BEFORE_THE_CALL = transcript(
  user('e0a040a6-aec9-4274-97fb-1f81430a0f1a', '2026-11-10T09:28:40.249Z', 'Load the plugin-authoring skill'),
  assistant('90d8109b-6574-4132-9ae5-a58647538c3a', '2026-11-10T09:29:59.956Z', { type: 'thinking', thinking: '', signature: 'EqQBCkYI' }),
)

test('a row shows --:-- until the transcript has its time', async ($, on) => {
  host(on, { [TRANSCRIPT]: BEFORE_THE_CALL })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const ui = await drawSkillRow($)
  expect((await ui.find({ type: 'Text' }))?.text).toBe('--:-- ')
})

test('once the transcript has the time, the row is redrawn in place with it', async ($, on) => {
  const clock = mock.clock(on)
  const files = { [TRANSCRIPT]: BEFORE_THE_CALL }
  host(on, files)
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const ui = await drawSkillRow($)
  // Claude Code adds the call to the conversation, and writes it to the transcript a moment later.
  const call = { type: 'tool_use', id: SKILL_CALL.tool_use_id, name: 'Skill', input: SKILL_CALL.input } as const
  await $.session.append({
    message: { type: 'assistant', role: 'assistant', content: [call] },
    door: 'response',
    origin: { kind: 'model', model: 'claude-opus-5-5' },
    uuid: 'a2dc512c-f195-45f6-9351-8da543c2d09b',
  })
  files[TRANSCRIPT] += transcript(assistant('a2dc512c-f195-45f6-9351-8da543c2d09b', '2026-11-10T09:30:16.161Z', call))
  await clock.advance(1000)
  expect((await ui.find({ type: 'Text' }))?.text).toBe(`${timeOfDay('2026-11-10T09:30:16.161Z')} `)
})

test('a row in a session that has no transcript is left exactly as Claude Code draws it', async ($, on) => {
  host(on, {})
  // A session that keeps no transcript starts with an empty transcript path.
  await $.classic.SessionStart({ source: 'startup', transcript_path: '' })
  const ui = await drawSkillRow($)
  expect(await ui.drawn()).toMatchObject({ type: 'engine' })
})

const TIMES = '/home/me/.claude/projects/-srv-work/5eb6757b-439c-4746-a382-87be59dab35a.times'

test('a time read from the transcript is kept in a file in the transcript directory, as the transcript records it', async ($, on) => {
  const files: Record<string, string> = { [TRANSCRIPT]: SKILL_SESSION }
  host(on, files)
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  await drawSkillRow($)
  expect(files[TIMES]).toBe(`${SKILL_CALL.tool_use_id} 2026-11-10T09:30:16.161Z\n`)
})

test('the file keeps the time of every row read so far', async ($, on) => {
  const files: Record<string, string> = { [TRANSCRIPT]: REPLY_SESSION }
  host(on, files)
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  await drawSkillRow($)
  await drawReplyRow($)
  expect(files[TIMES]).toBe(`${SKILL_CALL.tool_use_id} 2026-11-10T09:30:16.161Z\n${REPLY_ID} 2026-11-10T09:32:41.970Z\n`)
})

test('a row whose time is already in the file is drawn from it, without reading the transcript', async ($, on) => {
  // The session is resumed: the file holds what was read before.
  const ran = host(on, { [TRANSCRIPT]: SKILL_SESSION, [TIMES]: `${SKILL_CALL.tool_use_id} 2026-11-10T09:30:16.161Z\n` })
  await $.classic.SessionStart({ source: 'resume', transcript_path: TRANSCRIPT })
  const ui = await drawSkillRow($)
  expect({ shown: (await ui.find({ type: 'Text' }))?.text, ran }).toEqual({ shown: `${timeOfDay('2026-11-10T09:30:16.161Z')} `, ran: [] })
})

test('a row of a subagent shows the time the subagent\'s own transcript records for it', async ($, on) => {
  // Claude Code keeps each subagent's transcript in the session's own folder, beside the session's transcript.
  const subagent = '/home/me/.claude/projects/-srv-work/5eb6757b-439c-4746-a382-87be59dab35a/subagents/agent-aa3ba150d12cc0104.jsonl'
  const listing = { tool_use_id: 'toolu_01CzxxKQm4nTq8sVbY2LwPd7', tool: 'Bash', input: { command: 'ls' }, isRunning: false, isErrored: false, isInterrupted: false, isExpanded: false }
  const files = {
    [TRANSCRIPT]: SKILL_SESSION,
    [subagent]: transcript(
      user('e7de5353-1dba-418e-b700-e4328fbfd528', '2026-11-10T10:01:40.987Z', 'List the files'),
      assistant('56d6a0c1-6a0e-4c0e-9d53-0d7f1c9a2b11', '2026-11-10T10:02:05.310Z', { type: 'tool_use', id: listing.tool_use_id, name: 'Bash', input: listing.input }),
    ),
  }
  host(on, files)
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const ui = await $.ui.mount({ plugin: 'rules', surface: 'terminal', component: 'ToolUse', requestId: listing.tool_use_id, props: listing })
  expect((await ui.find({ type: 'Text' }))?.text).toBe(`${timeOfDay('2026-11-10T10:02:05.310Z')} `)
})

test('a row whose read of the transcript is cut short shows --:--', async ($, on) => {
  // A host with no times file and no subagents, where Claude Code drops the drawing it asked for: the read under way
  // for a dropped drawing is aborted.
  on('classic.SessionStart', () => ({}))
  on('fs.read', ($, e) => {
    throw new Error(`ENOENT: no such file or directory, open '${e.path}'`)
  })
  on('fs.list', ($, e) => {
    throw new Error(`ENOENT: no such file or directory, scandir '${e.path}'`)
  })
  on('process.run', () => {
    throw new Error('rules: $.process.run(tail) aborted')
  })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const ui = await drawSkillRow($)
  expect((await ui.find({ type: 'Text' }))?.text).toBe('--:-- ')
})

test('what Claude Code draws outside the transcript is left as it draws it: the spinner, the band above the prompt and the lines under it', async ($, on) => {
  host(on, { [TRANSCRIPT]: SKILL_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const spinner = await $.ui.mount({ plugin: 'rules', surface: 'terminal', component: 'Spinner', props: { word: 'Undulating', message: null, suffix: '…', mode: 'thinking' } })
  const bandProps = { hasSurvey: false, isCollapsed: false, isWorking: true, maxRows: 17, bodyColumns: 155, scroll: { offset: 0, bodyRows: 16 }, view: {} }
  const band = await $.ui.mount({ plugin: 'rules', surface: 'terminal', component: 'AbovePrompt', requestId: 'above-prompt', props: bandProps })
  const hint = await $.ui.mount({ plugin: 'rules', surface: 'terminal', component: 'PromptHint', requestId: 'prompt-hint', props: { isDraft: false, isWorking: true, hint: '(shift+tab to cycle)' } })
  const mode = await $.ui.mount({ plugin: 'rules', surface: 'terminal', component: 'SessionMode', requestId: 'session-mode', props: { modes: [] } })
  const drawn = [await spinner.drawn(), await band.drawn(), await hint.drawn(), await mode.drawn()]
  expect(drawn.map((tree) => tree.type)).toEqual(['engine', 'engine', 'engine', 'engine'])
})

test('a subagent\'s handback call, which Claude Code draws nothing for, shows no time', async ($, on) => {
  // A subagent ends by calling SubagentHandback, and its view draws no row for the call.
  const subagent = '/home/me/.claude/projects/-srv-work/5eb6757b-439c-4746-a382-87be59dab35a/subagents/agent-ae990d03dc2e2a409.jsonl'
  const input = { message: 'Ran `echo hi` in Bash. Output: `hi`. Reply: done.' }
  const handback = { tool_use_id: 'toolu_01NJwJzs2uPrjqkMe3XH82yR', tool: 'SubagentHandback', input, isRunning: false, isErrored: false, isInterrupted: false, isExpanded: false }
  const call = assistant('6ad49b99-b521-4ebf-8f38-fb98b8ca8a1a', '2026-11-10T10:02:09.118Z', { type: 'tool_use', id: handback.tool_use_id, name: 'SubagentHandback', input })
  host(on, { [TRANSCRIPT]: SKILL_SESSION, [subagent]: transcript(call) })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const ui = await $.ui.mount({ plugin: 'rules', surface: 'terminal', component: 'ToolUse', requestId: handback.tool_use_id, props: handback })
  expect(await ui.drawn()).toMatchObject({ type: 'engine' })
})

test('a tool call\'s result stays under its call, moved right by the width of a time, and shows no time of its own', async ($, on) => {
  host(on, { [TRANSCRIPT]: SKILL_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const result = { tool_use_id: SKILL_CALL.tool_use_id, tool: 'Skill', output: SKILL_CALL.output, isErrored: false, isExpanded: false }
  const ui = await $.ui.mount({ plugin: 'rules', surface: 'terminal', component: 'ToolResult', requestId: SKILL_CALL.tool_use_id, props: result })
  expect(await ui.drawn()).toMatchObject({ type: 'Box', props: { flexDirection: 'row' }, children: [{ type: 'Text', children: ['      '] }, { type: 'engine' }] })
})

test('the prompt a subagent has from main, which Claude Code draws under a label and not a blank line, has its time on its first line', async ($, on) => {
  const subagent = '/home/me/.claude/projects/-srv-work/5eb6757b-439c-4746-a382-87be59dab35a/subagents/agent-ae990d03dc2e2a409.jsonl'
  const prompt = user('8192dc5a-249e-49bc-b50e-74caa4f7c02d', '2026-11-10T10:01:40.987Z', 'Run the Bash command `echo hi` and then reply done.')
  host(on, { [TRANSCRIPT]: SKILL_SESSION, [subagent]: transcript(prompt) })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const props = { text: 'Run the Bash command `echo hi` and then reply done.', origin: { kind: 'coordinator' }, isExpanded: false } as const
  const ui = await $.ui.mount({ plugin: 'rules', surface: 'terminal', component: 'UserMessage', requestId: '8192dc5a-249e-49bc-b50e-74caa4f7c02d', props })
  expect(await ui.drawn()).toMatchObject({ children: [{ type: 'Box', props: { marginTop: 0 } }, {}] })
})

test('a slash command\'s output, which Claude Code draws under the command\'s own untimed line, is left as it draws it', async ($, on) => {
  host(on, { [TRANSCRIPT]: SKILL_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const output = { command: 'tasks', args: '', text: 'Viewing agent', isErrored: false }
  const ui = await $.ui.mount({ plugin: 'rules', surface: 'terminal', component: 'CommandOutput', requestId: 'b19f5b34-dba6-4810-9b4a-df2a3c88fa09', props: output })
  expect(await ui.drawn()).toMatchObject({ type: 'engine' })
})

test('a row the transcript records past its first 4 MiB shows its time', async ($, on) => {
  // A session in which Claude read a 410 KB log twelve times over, 5 MB of transcript, before it called the Skill tool.
  const log = '2026-11-10T09:00:00.000Z GET /health 200\n'.repeat(10_000)
  const reads = Array.from({ length: 12 }, (_, n) => {
    const call = read(`toolu_01${String(n).padStart(22, '0')}`, '/srv/work/server.log')
    return transcript(
      assistant(`293589d0-56e7-4054-97df-${String(n).padStart(12, '0')}`, '2026-11-10T09:20:07.346Z', { type: 'tool_use', id: call.tool_use_id, name: 'Read', input: call.input }),
      user(`ef33aa01-5c82-44ac-b682-${String(n).padStart(12, '0')}`, '2026-11-10T09:20:07.568Z', [{ type: 'tool_result', tool_use_id: call.tool_use_id, content: log }]),
    )
  })
  host(on, { [TRANSCRIPT]: reads.join('') + SKILL_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const ui = await drawSkillRow($)
  expect((await ui.find({ type: 'Text' }))?.text).toBe(`${timeOfDay('2026-11-10T09:30:16.161Z')} `)
})

test('a row recorded in lines already read for another row is drawn without reading the transcript again', async ($, on) => {
  const ran = host(on, { [TRANSCRIPT]: REPLY_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  await drawSkillRow($)
  const ui = await drawReplyRow($)
  expect({ shown: (await ui.find({ type: 'Text' }))?.text, ran }).toEqual({ shown: `${timeOfDay('2026-11-10T09:32:41.970Z')} `, ran: [['tail', '-n', '+1', TRANSCRIPT]] })
})

test('a row the transcript lacked when first drawn is looked for, when drawn again, only in the lines the transcript has gained', async ($, on) => {
  const clock = mock.clock(on)
  const files = { [TRANSCRIPT]: BEFORE_THE_CALL }
  const ran = host(on, files)
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const ui = await drawSkillRow($)
  const ranForFirstDraw = ran.length
  // Claude Code adds the call to the conversation, and a moment later writes it to the transcript, its third line.
  const call = { type: 'tool_use', id: SKILL_CALL.tool_use_id, name: 'Skill', input: SKILL_CALL.input } as const
  await $.session.append({
    message: { type: 'assistant', role: 'assistant', content: [call] },
    door: 'response',
    origin: { kind: 'model', model: 'claude-opus-5-5' },
    uuid: 'a2dc512c-f195-45f6-9351-8da543c2d09b',
  })
  files[TRANSCRIPT] += transcript(assistant('a2dc512c-f195-45f6-9351-8da543c2d09b', '2026-11-10T09:30:16.161Z', call))
  await clock.advance(1000)
  const shown = (await ui.find({ type: 'Text' }))?.text
  expect({ shown, ran: ran.slice(ranForFirstDraw) }).toEqual({ shown: `${timeOfDay('2026-11-10T09:30:16.161Z')} `, ran: [['tail', '-n', '+3', TRANSCRIPT]] })
})
