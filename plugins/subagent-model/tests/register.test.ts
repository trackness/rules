import type { On } from 'claude-code'
import { expect, test, type Plugin } from 'claude-code/testing'

const AGENT_REASON =
  'Every subagent must run on a model appropriately capable for its task. Retry this call with the model parameter set to that model.'
const WORKFLOW_REASON =
  'Every agent a workflow spawns must run on a model appropriately capable for its task. Set the model option of every agent() call to that model, then run the workflow again.'

const SPAWN = {
  tool_use_id: 'toolu_agent',
  prompt: 'Find the callers of main',
  description: 'Find callers',
  subagentType: 'general-purpose',
  provider: { plugin: 'engine', tier: 'core' },
  parentModel: 'claude-opus-5-5',
  background: false,
  fork: false,
} as const

const STARTED = { model: 'claude-opus-5-5', agentId: 'agent_1' }

type Session = { files?: Record<string, string>; env?: Record<string, string>; cwd?: string; root?: string }

// The engine beneath the plugin: every tool call it runs succeeds and every spawn it gets starts. By default the
// session's project root is the repository /srv/work, it runs in /srv/work/pkg, and the user's home is /home/me.
function engine(on: On, { files = {}, env = { HOME: '/home/me' }, cwd = '/srv/work/pkg', root = '/srv/work' }: Session = {}) {
  const disk: Record<string, string> = { '/srv/work/.git/HEAD': 'ref: refs/heads/main\n', ...files }
  const paths = Object.keys(disk)
  on('tool.call', () => ({ result: {} }))
  on('agent.spawn', () => STARTED)
  on('session.cwd', () => ({ value: cwd }))
  on('session.root', () => ({ value: root }))
  on('env.get', ($, e) => ({ value: env[e.name] }))
  // The kit runs on POSIX and resolves a Windows path against the plugin's folder: take it back to its drive.
  const at = (path: string) => path.replace(/^.*(?=[A-Z]:\/)/, '')
  on('fs.exists', ($, e) => ({ value: paths.some((path) => path === at(e.path) || path.startsWith(`${at(e.path)}/`)) }))
  on('fs.list', ($, e) => {
    const inside = paths.filter((path) => path.startsWith(`${at(e.path)}/`))
    if (inside.length === 0) throw new Error(`ENOENT: ${e.path}`)
    const names = inside.map((path) => path.slice(at(e.path).length + 1)).filter((name) => !name.includes('/'))
    return { value: names.map((name) => ({ name, kind: 'file' as const, size: 0, mtimeMs: 0, isLink: false })) }
  })
  on('fs.read', ($, e) => {
    const text = disk[at(e.path)]
    if (text === undefined) throw new Error(`ENOENT: ${e.path}`)
    return { value: text }
  })
}

test('an agent spawned without a model is denied, and told to name one', async ($, on) => {
  engine(on)
  expect(await $.agent.spawn(SPAWN)).toEqual({ deny: AGENT_REASON })
})

test('an agent spawned with the model inherit is denied', async ($, on) => {
  engine(on)
  expect(await $.agent.spawn({ ...SPAWN, model: 'inherit' })).toEqual({ deny: AGENT_REASON })
})

test('an agent spawned with an empty model is denied', async ($, on) => {
  engine(on)
  expect(await $.agent.spawn({ ...SPAWN, model: '' })).toEqual({ deny: AGENT_REASON })
})

test('a fork starts without a model, since it always runs on the caller\'s', async ($, on) => {
  engine(on)
  expect(await $.agent.spawn({ ...SPAWN, subagentType: 'fork', fork: true })).toEqual(STARTED)
})

test('a resumed agent starts again, since its model was settled when it first started', async ($, on) => {
  engine(on)
  expect(await $.agent.spawn({ ...SPAWN, resume: { agentId: 'agent_1' } })).toEqual(STARTED)
})

const SCRIPT = "export const meta = {name: 'scan', description: 'Scan the repo'}\nawait agent('List the TODO comments')\n"
const RESEARCH = "export const meta = {name: 'deep-research', description: 'Research'}\nawait agent('Search the web')\n"
const WORKFLOW_AGENT = {
  ...SPAWN,
  tool_use_id: 'toolu_workflow',
  subagentType: 'workflow-subagent',
  prompt: 'List the TODO comments',
  workflow: { runId: 'wf_1', agentIndex: 1 },
}

test('an agent spawned without a model by a workflow Claude scripted is denied, with how to fix the script', async ($, on) => {
  engine(on)
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', script: SCRIPT })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('an agent spawned without a model by a workflow Claude runs from a script file is denied', async ($, on) => {
  engine(on)
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', scriptPath: '/srv/work/.claude/workflows/scripts/scan.js' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('an agent spawned with a model by a workflow Claude scripted starts', async ($, on) => {
  engine(on)
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', script: SCRIPT })
  expect(await $.agent.spawn({ ...WORKFLOW_AGENT, model: 'haiku' })).toEqual(STARTED)
})

test('an agent spawned without a model by a built-in workflow run by name starts, since no script of that name is on disk', async ($, on) => {
  engine(on)
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
})

test('each workflow call is judged on its own: a built-in run\'s agent starts while a scripted run\'s is denied', async ($, on) => {
  engine(on)
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', script: SCRIPT })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_research', name: 'deep-research', args: 'What changed?' })
  const researchAgent = { ...WORKFLOW_AGENT, tool_use_id: 'toolu_research', workflow: { runId: 'wf_2', agentIndex: 1 } }
  expect(await $.agent.spawn(researchAgent)).toEqual(STARTED)
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('an agent spawned without a model by a workflow saved in the project and run by name is denied', async ($, on) => {
  // Saved under another file name in a folder above the working directory: a saved workflow runs by its meta name.
  engine(on, { files: { '/srv/work/.claude/workflows/todo-scan.js': SCRIPT } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('an agent spawned without a model by a workflow saved in the user\'s own folder and run by name is denied', async ($, on) => {
  engine(on, { files: { '/home/me/.claude/workflows/scan.js': SCRIPT } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('an agent spawned without a model by a workflow saved under CLAUDE_CONFIG_DIR and run by name is denied', async ($, on) => {
  engine(on, { files: { '/config/workflows/scan.js': SCRIPT }, env: { HOME: '/home/me', CLAUDE_CONFIG_DIR: '/config' } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a script above the repository is not a saved workflow, since Claude Code stops looking at the repository root', async ($, on) => {
  engine(on, { files: { '/srv/.claude/workflows/deep-research.js': RESEARCH } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
})

test('a script in the home folder\'s own .claude is not a project workflow, so a built-in of its name runs unchecked', async ($, on) => {
  // The personal folder is elsewhere, and outside a repository the walk stops before the home folder.
  const env = { HOME: '/home/me', CLAUDE_CONFIG_DIR: '/config' }
  engine(on, { files: { '/home/me/.claude/workflows/deep-research.js': RESEARCH }, env, cwd: '/home/me/notes', root: '/home/me/notes' })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
})

test('a script above the home folder is not a saved workflow', async ($, on) => {
  engine(on, { files: { '/home/.claude/workflows/deep-research.js': RESEARCH }, cwd: '/home/me/notes', root: '/home/me/notes' })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
})

test('outside the home folder and any repository, the walk reaches the file system root', async ($, on) => {
  engine(on, { files: { '/.claude/workflows/scan.js': SCRIPT }, cwd: '/srv/scratch/notes', root: '/srv/scratch/notes' })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a Windows working directory walks up its own folders to the repository root', async ($, on) => {
  const files = { 'C:/work/.git/HEAD': 'ref: refs/heads/main\n', 'C:/work/.claude/workflows/todo-scan.js': SCRIPT }
  engine(on, { files, env: { OS: 'Windows_NT', USERPROFILE: 'C:\\Users\\me' }, cwd: 'C:\\work\\pkg', root: 'C:\\work' })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('on Windows, without HOME, the personal folder is under USERPROFILE', async ($, on) => {
  const env = { OS: 'Windows_NT', USERPROFILE: 'C:\\Users\\me' }
  engine(on, { files: { 'C:/Users/me/.claude/workflows/scan.js': SCRIPT }, env })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('on Windows, with USERPROFILE and HOME both set, the home folder is USERPROFILE, as os.homedir() takes it', async ($, on) => {
  const env = { OS: 'Windows_NT', HOME: 'C:\\msys\\home\\me', USERPROFILE: 'C:\\Users\\me' }
  engine(on, { files: { 'C:/Users/me/.claude/workflows/scan.js': SCRIPT }, env })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('elsewhere, with USERPROFILE and HOME both set, as under WSL, the home folder is HOME, as os.homedir() takes it', async ($, on) => {
  const env = { HOME: '/home/me', USERPROFILE: '/mnt/c/Users/me' }
  engine(on, { files: { '/home/me/.claude/workflows/scan.js': SCRIPT }, env })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a script saved as .mjs, .cjs or .ts is not a saved workflow, since Claude Code loads only .js', async ($, on) => {
  const files = {
    '/srv/work/.claude/workflows/research.mjs': RESEARCH,
    '/srv/work/.claude/workflows/research.cjs': RESEARCH,
    '/srv/work/.claude/workflows/research.ts': RESEARCH,
  }
  engine(on, { files })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
})

test('a saved workflow whose meta name is in double quotes is found', async ($, on) => {
  const quoted = 'export const meta = {"name": "scan", "description": "Scan the repo"}\nawait agent("List the TODO comments")\n'
  engine(on, { files: { '/srv/work/.claude/workflows/todo-scan.js': quoted } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('where the session forces every subagent\'s model, agents start without one, since Claude Code ignores the call\'s', async ($, on) => {
  engine(on, { env: { HOME: '/home/me', CLAUDE_CODE_SUBAGENT_MODEL_FORCE: '1' } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', script: SCRIPT })
  expect(await $.agent.spawn(SPAWN)).toEqual(STARTED)
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
})

test('while CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL names a model, workflow agents start without one, since Claude Code ignores the script\'s', async ($, on) => {
  engine(on, { env: { HOME: '/home/me', CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL: 'haiku' } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', script: SCRIPT })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
  expect(await $.agent.spawn(SPAWN)).toEqual({ deny: AGENT_REASON })
})

test('CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL set to inherit, in any case, leaves workflow agents checked', async ($, on) => {
  engine(on, { env: { HOME: '/home/me', CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL: 'Inherit' } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', script: SCRIPT })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL set to blanks leaves workflow agents checked', async ($, on) => {
  engine(on, { env: { HOME: '/home/me', CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL: '  ' } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', script: SCRIPT })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('CLAUDE_CODE_SUBAGENT_MODEL_FORCE set to a value Claude Code reads as off leaves the rule on', async ($, on) => {
  engine(on, { env: { HOME: '/home/me', CLAUDE_CODE_SUBAGENT_MODEL_FORCE: '0' } })
  expect(await $.agent.spawn(SPAWN)).toEqual({ deny: AGENT_REASON })
})

test('a repository nested in the session\'s own walks on to the session repository\'s root', async ($, on) => {
  const files = { '/srv/work/vendor/lib/.git/HEAD': 'ref: refs/heads/main\n', '/srv/work/.claude/workflows/todo-scan.js': SCRIPT }
  engine(on, { files, cwd: '/srv/work/vendor/lib/src' })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a worktree of the session\'s repository stops at its own root', async ($, on) => {
  const files = {
    '/srv/work/.claude/worktrees/fix/.git': 'gitdir: /srv/work/.git/worktrees/fix\n',
    '/srv/work/.claude/workflows/deep-research.js': RESEARCH,
  }
  engine(on, { files, cwd: '/srv/work/.claude/worktrees/fix/pkg' })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
})

// The other plugin's tool, declared so its name type-checks whichever MCP tools were connected when Claude Code laid the types.
declare module 'claude-code' {
  interface McpToolInputs {
    mcp__spawner__summarise: {}
  }
}

// Another plugin, which spawns an agent of its own without a model when its tool runs, and says whether it was denied.
const SPAWNER = {
  name: 'spawner',
  register(on) {
    on('tool.call', { tool: 'mcp__spawner__summarise' }, async ($) => {
      const spawned = await $.agent.spawn({ prompt: 'Summarise the diff' })
      return { result: { denied: spawned.deny !== undefined } }
    })
  },
} satisfies Plugin

test('an agent another plugin spawns without a model starts, since only Claude\'s own spawns are checked', { plugins: [SPAWNER] }, async ($, on) => {
  engine(on)
  expect(await $.tool.call({ tool: 'mcp__spawner__summarise', tool_use_id: 'toolu_summarise' })).toEqual({ result: { denied: false } })
})

test('an agent spawned with a model starts', async ($, on) => {
  engine(on)
  expect(await $.agent.spawn({ ...SPAWN, model: 'sonnet' })).toEqual(STARTED)
})
