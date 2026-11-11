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

// The timer of the tests' own runtime, which the types Claude Code lays down for a plugin do not declare.
declare function setTimeout(callback: () => void, milliseconds: number): unknown

// How much of what a command writes Claude Code 2.1.322 hands a plugin: the first 4 MiB, the rest dropped.
const STDOUT_LIMIT = 4 * 1024 * 1024

// The host beneath the plugin: a session that starts, and its files. A plugin's own file read refuses a file over
// 4 MiB, which a transcript passes, so the files are read from a byte on by tail. A write replaces a file whole.
// Answers with the commands the plugin ran.
function host(on: On, files: Record<string, string>, commandsAborted = 0) {
  const ran: (readonly string[])[] = []
  on('classic.SessionStart', () => ({}))
  on('fs.read', ($, e) => {
    const text = files[e.path]
    if (text === undefined) throw new Error(`ENOENT: no such file or directory, open '${e.path}'`)
    return { value: text }
  })
  // Claude Code carries out the writes a plugin has under way at once in no set order: here, the latest first.
  const writesUnderWay: (() => void)[] = []
  on('fs.write', async ($, e) => {
    writesUnderWay.push(() => {
      files[e.path] = e.text
    })
    await new Promise((resolve) => setTimeout(() => resolve(undefined), 0))
    writesUnderWay.pop()?.()
    return { value: undefined }
  })
  on('fs.list', ($, e) => {
    const names = Object.keys(files).filter((path) => path.startsWith(`${e.path}/`)).map((path) => path.slice(e.path.length + 1))
    if (names.length === 0) throw new Error(`ENOENT: no such file or directory, scandir '${e.path}'`)
    return { value: names.filter((name) => !name.includes('/')).map((name) => ({ name, kind: 'file' as const, size: 0, mtimeMs: 0, isLink: false })) }
  })
  on('process.run', ($, e) => {
    ran.push(e.argv)
    // Claude Code aborts the command under way for a drawing it drops: here, the first commands the plugin runs.
    if (ran.length <= commandsAborted) throw new Error(`row-time: $.process.run(${String(e.argv[0])}) aborted`)
    const [command, flag, from, path] = e.argv
    const text = path === undefined ? undefined : files[path]
    if (command !== 'tail' || flag !== '-c' || text === undefined) {
      return { value: { exitCode: 1, stdout: '', stderr: `${String(command)}: ${String(path)}: No such file or directory\n`, isStdoutTruncated: false, isStderrTruncated: false } }
    }
    // The transcripts here are ASCII, a byte to a character.
    const stdout = text.slice(Number(from) - 1)
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
  return $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'ToolUse', requestId: SKILL_CALL.tool_use_id, props: SKILL_CALL })
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

test('the time takes no columns from the row Claude Code draws: the row stands alone in a column, and the time is drawn after it, over it', async ($, on) => {
  const ui = await skillRow($, on)
  expect(await ui.drawn()).toMatchObject({ type: 'Box', props: { flexDirection: 'column' }, children: [{ type: 'engine' }, { type: 'Box', props: { position: 'absolute' } }] })
})

test('the time is dim', async ($, on) => {
  const ui = await skillRow($, on)
  expect(await ui.find({ type: 'Text' })).toMatchObject({ props: { dimColor: true } })
})

test('the time stands at the left of the blank line Claude Code draws above a row, directly above its ⏺', async ($, on) => {
  const ui = await skillRow($, on)
  const atTheLeftOfTheTopLine = expect.objectContaining({ type: 'Box', props: expect.objectContaining({ position: 'absolute', top: 0, left: 0 }) })
  expect(await ui.drawn()).toMatchObject({ children: expect.arrayContaining([atTheLeftOfTheTopLine]) })
})

test('a blank line stands above the time, setting the row and its time apart from what is drawn before them', async ($, on) => {
  const ui = await skillRow($, on)
  expect(await ui.drawn()).toMatchObject({ type: 'Box', props: { marginTop: 1 } })
})

const REPLY_ID = '8d4d70ff-4e29-4404-bc72-1641876dc44a'
const REPLY = { text: 'The plugin-authoring skill is loaded.', isFirstOfReply: true }

// The Skill session gone on: two minutes after the call, Claude replied.
const REPLY_SESSION = SKILL_SESSION + transcript(assistant(REPLY_ID, '2026-11-10T09:32:41.970Z', { type: 'text', text: REPLY.text }))

// The reply's row as the terminal draws it.
function drawReplyRow($: Engine) {
  return $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'AssistantMessage', requestId: REPLY_ID, props: REPLY })
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
  const ui = await $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'ToolGroup', requestId: 'collapsed-293589d0-56e7-4054-97df-b0b2665696e7', props: run })
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

// Claude Code adds the Skill call to the conversation, and a moment later writes it to the transcript, as its next
// line. The rows are drawn again by then.
async function recordSkillCall($: Engine, clock: ReturnType<typeof mock.clock>, files: Record<string, string>) {
  const call = { type: 'tool_use', id: SKILL_CALL.tool_use_id, name: 'Skill', input: SKILL_CALL.input } as const
  await $.session.append({
    message: { type: 'assistant', role: 'assistant', content: [call] },
    door: 'response',
    origin: { kind: 'model', model: 'claude-opus-5-5' },
    uuid: 'a2dc512c-f195-45f6-9351-8da543c2d09b',
  })
  files[TRANSCRIPT] += transcript(assistant('a2dc512c-f195-45f6-9351-8da543c2d09b', '2026-11-10T09:30:16.161Z', call))
  await clock.advance(1000)
}

test('once the transcript has the time, the row is redrawn in place with it', async ($, on) => {
  const clock = mock.clock(on)
  const files = { [TRANSCRIPT]: BEFORE_THE_CALL }
  host(on, files)
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const ui = await drawSkillRow($)
  await recordSkillCall($, clock, files)
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
  const ui = await $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'ToolUse', requestId: listing.tool_use_id, props: listing })
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
    throw new Error('row-time: $.process.run(tail) aborted')
  })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const ui = await drawSkillRow($)
  expect((await ui.find({ type: 'Text' }))?.text).toBe('--:-- ')
})

test('what Claude Code draws outside the transcript is left as it draws it: the spinner, the band above the prompt and the lines under it', async ($, on) => {
  host(on, { [TRANSCRIPT]: SKILL_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const spinner = await $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'Spinner', props: { word: 'Undulating', message: null, suffix: '…', mode: 'thinking' } })
  const bandProps = { hasSurvey: false, isCollapsed: false, isWorking: true, maxRows: 17, bodyColumns: 155, scroll: { offset: 0, bodyRows: 16 }, view: {} }
  const band = await $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'AbovePrompt', requestId: 'above-prompt', props: bandProps })
  const hint = await $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'PromptHint', requestId: 'prompt-hint', props: { isDraft: false, isWorking: true, hint: '(shift+tab to cycle)' } })
  const mode = await $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'SessionMode', requestId: 'session-mode', props: { modes: [] } })
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
  const ui = await $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'ToolUse', requestId: handback.tool_use_id, props: handback })
  expect(await ui.drawn()).toMatchObject({ type: 'engine' })
})

test('a tool call\'s result, which shows no time of its own, is left as Claude Code draws it, under its call', async ($, on) => {
  host(on, { [TRANSCRIPT]: SKILL_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const result = { tool_use_id: SKILL_CALL.tool_use_id, tool: 'Skill', output: SKILL_CALL.output, isErrored: false, isExpanded: false }
  const ui = await $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'ToolResult', requestId: SKILL_CALL.tool_use_id, props: result })
  expect(await ui.drawn()).toMatchObject({ type: 'engine' })
})

test('the prompt a subagent has from main, which Claude Code draws under a label and not a blank line, has its time on a line of its own above the label, under a blank line', async ($, on) => {
  const subagent = '/home/me/.claude/projects/-srv-work/5eb6757b-439c-4746-a382-87be59dab35a/subagents/agent-ae990d03dc2e2a409.jsonl'
  const prompt = user('8192dc5a-249e-49bc-b50e-74caa4f7c02d', '2026-11-10T10:01:40.987Z', 'Run the Bash command `echo hi` and then reply done.')
  host(on, { [TRANSCRIPT]: SKILL_SESSION, [subagent]: transcript(prompt) })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const props = { text: 'Run the Bash command `echo hi` and then reply done.', origin: { kind: 'coordinator' }, isExpanded: false } as const
  const ui = await $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'UserMessage', requestId: '8192dc5a-249e-49bc-b50e-74caa4f7c02d', props })
  expect(await ui.drawn()).toMatchObject({ type: 'Box', props: { flexDirection: 'column', marginTop: 1 }, children: [{ type: 'Text' }, { type: 'engine' }] })
})

test('a slash command\'s output, which Claude Code draws under the command\'s own untimed line, is left as it draws it', async ($, on) => {
  host(on, { [TRANSCRIPT]: SKILL_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const output = { command: 'tasks', args: '', text: 'Viewing agent', isErrored: false }
  const ui = await $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'CommandOutput', requestId: 'b19f5b34-dba6-4810-9b4a-df2a3c88fa09', props: output })
  expect(await ui.drawn()).toMatchObject({ type: 'engine' })
})

// One of a run of reads of one 410 KB log, as its row carries the call.
function logRead(n: number) {
  return read(`toolu_01${String(n).padStart(22, '0')}`, '/srv/work/server.log')
}

const LOG_READS = Array.from({ length: 12 }, (_, n) => logRead(n))
const LOG = '2026-11-10T09:00:00.000Z GET /health 200\n'.repeat(10_000)

// A session in which Claude made twelve of those reads, 5 MB of transcript, before it called the Skill tool.
const LONG_SESSION =
  LOG_READS.map((call, n) =>
    transcript(
      assistant(`293589d0-56e7-4054-97df-${String(n).padStart(12, '0')}`, '2026-11-10T09:20:07.346Z', { type: 'tool_use', id: call.tool_use_id, name: 'Read', input: call.input }),
      user(`ef33aa01-5c82-44ac-b682-${String(n).padStart(12, '0')}`, '2026-11-10T09:20:07.568Z', [{ type: 'tool_result', tool_use_id: call.tool_use_id, content: LOG }]),
    ),
  ).join('') + SKILL_SESSION

test('a row the transcript records past its first 4 MiB shows its time', async ($, on) => {
  host(on, { [TRANSCRIPT]: LONG_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const ui = await drawSkillRow($)
  expect((await ui.find({ type: 'Text' }))?.text).toBe(`${timeOfDay('2026-11-10T09:30:16.161Z')} `)
})

test('a row recorded in lines already read for another row is drawn without reading the transcript again', async ($, on) => {
  const ran = host(on, { [TRANSCRIPT]: REPLY_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  await drawSkillRow($)
  const ui = await drawReplyRow($)
  expect({ shown: (await ui.find({ type: 'Text' }))?.text, reads: ran.length }).toEqual({ shown: `${timeOfDay('2026-11-10T09:32:41.970Z')} `, reads: 1 })
})

test('a row the transcript lacked when first drawn is looked for, when drawn again, from the byte where the last read ended', async ($, on) => {
  const clock = mock.clock(on)
  const files = { [TRANSCRIPT]: BEFORE_THE_CALL }
  const ran = host(on, files)
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const ui = await drawSkillRow($)
  const ranForFirstDraw = ran.length
  await recordSkillCall($, clock, files)
  const shown = (await ui.find({ type: 'Text' }))?.text
  // A read that starts at a byte goes straight to it: one that starts at a line counts through every line before.
  const fromTheCall = ['tail', '-c', `+${BEFORE_THE_CALL.length + 1}`, TRANSCRIPT]
  expect({ shown, ran: ran.slice(ranForFirstDraw) }).toEqual({ shown: `${timeOfDay('2026-11-10T09:30:16.161Z')} `, ran: [fromTheCall] })
})

test('a transcript that Claude Code hands back whole is read once for a row it does not yet hold', async ($, on) => {
  const ran = host(on, { [TRANSCRIPT]: BEFORE_THE_CALL })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  await drawSkillRow($)
  expect(ran.length).toBe(1)
})

test('rows drawn at once share one read of the transcript', async ($, on) => {
  const ran = host(on, { [TRANSCRIPT]: REPLY_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const rows = await Promise.all([drawSkillRow($), drawReplyRow($)])
  const shown = await Promise.all(rows.map(async (ui) => (await ui.find({ type: 'Text' }))?.text))
  expect({ shown, reads: ran.length }).toEqual({
    shown: [`${timeOfDay('2026-11-10T09:30:16.161Z')} `, `${timeOfDay('2026-11-10T09:32:41.970Z')} `],
    reads: 1,
  })
})

test('a row drawn at once with a row recorded 4 MiB before it shows its time', async ($, on) => {
  host(on, { [TRANSCRIPT]: LONG_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  // The first read's row, recorded at the top of the transcript.
  const firstRead = $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'ToolUse', requestId: logRead(0).tool_use_id, props: { ...logRead(0), isExpanded: false } })
  const [, ui] = await Promise.all([firstRead, drawSkillRow($)])
  expect((await ui.find({ type: 'Text' }))?.text).toBe(`${timeOfDay('2026-11-10T09:30:16.161Z')} `)
})

test('a row that waited on another row\'s read, which Claude Code cut short, reads the transcript itself', async ($, on) => {
  // Claude Code drops the Skill row's drawing, and aborts the read under way for it: the first of the session.
  host(on, { [TRANSCRIPT]: REPLY_SESSION }, 1)
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const [, ui] = await Promise.all([drawSkillRow($), drawReplyRow($)])
  expect((await ui.find({ type: 'Text' }))?.text).toBe(`${timeOfDay('2026-11-10T09:32:41.970Z')} `)
})

test('a row drawn before the session starts, as a resumed session\'s rows are, is redrawn with its time once it has started', async ($, on) => {
  host(on, { [TRANSCRIPT]: SKILL_SESSION, [TIMES]: `${SKILL_CALL.tool_use_id} 2026-11-10T09:30:16.161Z\n` })
  const ui = await drawSkillRow($)
  await $.classic.SessionStart({ source: 'resume', transcript_path: TRANSCRIPT })
  expect((await ui.find({ type: 'Text' }))?.text).toBe(`${timeOfDay('2026-11-10T09:30:16.161Z')} `)
})

test('a status line under the logo, which the transcript does not record, is left as Claude Code draws it', async ($, on) => {
  host(on, { [TRANSCRIPT]: SKILL_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const notice = { text: 'Debug mode enabled · logging to /home/me/debug.log', command: null }
  const ui = await $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'InfoNotice', requestId: `notice:${notice.text}`, props: notice })
  expect(await ui.drawn()).toMatchObject({ type: 'engine' })
})

test('the reply Claude Code itself adds to a forked session, which it draws nothing for, shows no time', async ($, on) => {
  const added = assistant('2bb86f3e-d64b-41c1-903e-3d13a2707994', '2026-11-10T09:40:20.460Z', { type: 'text', text: 'No response requested.' })
  host(on, { [TRANSCRIPT]: SKILL_SESSION + transcript(added) })
  await $.classic.SessionStart({ source: 'resume', transcript_path: TRANSCRIPT })
  const props = { text: 'No response requested.', isFirstOfReply: true }
  const ui = await $.ui.mount({ plugin: 'row-time', surface: 'terminal', component: 'AssistantMessage', requestId: '2bb86f3e-d64b-41c1-903e-3d13a2707994', props })
  expect(await ui.drawn()).toMatchObject({ type: 'engine' })
})

test('a row recorded after a transcript line longer than 4 MiB shows its time', async ($, on) => {
  // A session in which Claude read a 5 MB log, whose result is one line of the transcript, before it called the Skill tool.
  const call = read('toolu_01Hq7RkZsYw3uXc9LmNpT2bV', '/srv/work/archive.log')
  const longLine = transcript(user('5c0e7d1a-3f2b-4a8e-9d6c-1b7f4e2a9c03', '2026-11-10T09:20:07.568Z', [{ type: 'tool_result', tool_use_id: call.tool_use_id, content: LOG.repeat(13) }]))
  host(on, { [TRANSCRIPT]: longLine + SKILL_SESSION })
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  const ui = await drawSkillRow($)
  expect((await ui.find({ type: 'Text' }))?.text).toBe(`${timeOfDay('2026-11-10T09:30:16.161Z')} `)
})

test('the file keeps the time of every row drawn at once', async ($, on) => {
  const files: Record<string, string> = { [TRANSCRIPT]: REPLY_SESSION }
  host(on, files)
  await $.classic.SessionStart({ source: 'startup', transcript_path: TRANSCRIPT })
  await Promise.all([drawSkillRow($), drawReplyRow($)])
  expect(files[TIMES]).toBe(`${SKILL_CALL.tool_use_id} 2026-11-10T09:30:16.161Z\n${REPLY_ID} 2026-11-10T09:32:41.970Z\n`)
})
