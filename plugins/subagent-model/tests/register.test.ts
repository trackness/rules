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

type Session = { files?: Record<string, string>; links?: Record<string, string>; env?: Record<string, string>; cwd?: string; root?: string }

// The engine beneath the plugin: every tool call it runs succeeds and every spawn it gets starts. It returns the spawns
// it got, as the plugin passed them on. By default the session's project root is the repository /srv/work, it runs in
// /srv/work/pkg, and the user's home is /home/me. links maps each symbolic link's path to the file it leads to.
function engine(on: On, { files = {}, links = {}, env = { HOME: '/home/me' }, cwd = '/srv/work/pkg', root = '/srv/work' }: Session = {}) {
  const disk: Record<string, string> = { '/srv/work/.git/HEAD': 'ref: refs/heads/main\n', ...files }
  const paths = [...Object.keys(disk), ...Object.keys(links)]
  const spawns: unknown[] = []
  on('tool.call', () => ({ result: {} }))
  on('agent.spawn', ($, e) => {
    spawns.push(e)
    return STARTED
  })
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: cwd }))
  on('session.root', () => ({ value: root }))
  on('env.get', ($, e) => ({ value: env[e.name] }))
  on('fs.exists', ($, e) => ({ value: paths.some((path) => path === e.path || path.startsWith(`${e.path}/`)) }))
  on('fs.list', ($, e) => {
    const dir = e.path
    const inside = paths.filter((path) => path.startsWith(`${dir}/`))
    if (inside.length === 0) throw new Error(`ENOENT: ${e.path}`)
    const names = inside.map((path) => path.slice(dir.length + 1)).filter((name) => !name.includes('/'))
    // A listing describes each entry itself, a link not followed: a link is no file, and nothing looks up its target's size.
    const entry = (name: string) => {
      const path = `${dir}/${name}`
      return path in links
        ? { name, kind: 'other' as const, size: 0, mtimeMs: 0, isLink: true }
        : { name, kind: 'file' as const, size: new TextEncoder().encode(disk[path]).length, mtimeMs: 0, isLink: false }
    }
    return { value: names.map(entry) }
  })
  on('fs.read', ($, e) => {
    const text = disk[links[e.path] ?? e.path]
    if (text === undefined) throw new Error(`ENOENT: ${e.path}`)
    return { value: text }
  })
  return spawns
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
// One byte larger than 512 KiB, the script padded by a line comment of slashes after it.
const OVERSIZED_RESEARCH = RESEARCH.padEnd(512 * 1024 + 1, '/')
const WORKFLOW_AGENT = {
  ...SPAWN,
  tool_use_id: 'toolu_workflow',
  subagentType: 'workflow-subagent',
  prompt: 'List the TODO comments',
  workflow: { runId: 'wf_1', agentIndex: 1 },
}
// An agent of a second run in the same session, started by the Workflow call toolu_research.
const RESEARCH_AGENT = { ...WORKFLOW_AGENT, tool_use_id: 'toolu_research', workflow: { runId: 'wf_2', agentIndex: 1 } }

test('an agent spawned without a model by a workflow Claude scripted is denied, with how to fix the script', async ($, on) => {
  engine(on)
  // The Workflow call itself runs: only its agents are checked.
  expect(await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', script: SCRIPT })).toEqual({ result: {} })
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
  expect(await $.agent.spawn(RESEARCH_AGENT)).toEqual(STARTED)
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

test('with CLAUDE_CONFIG_DIR set but empty, the personal folder is workflows in the project root, where Claude Code runs', async ($, on) => {
  engine(on, { files: { '/srv/work/workflows/scan.js': SCRIPT }, env: { HOME: '/home/me', CLAUDE_CONFIG_DIR: '' } })
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

test('a home folder written with a trailing slash still stops the walk before it', async ($, on) => {
  const env = { HOME: '/home/me/', CLAUDE_CONFIG_DIR: '/config' }
  engine(on, { files: { '/home/me/.claude/workflows/deep-research.js': RESEARCH }, env, cwd: '/home/me/notes', root: '/home/me/notes' })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
})

test('a home folder of / stops the walk before the file system root', async ($, on) => {
  const env = { HOME: '/', CLAUDE_CONFIG_DIR: '/config' }
  engine(on, { files: { '/.claude/workflows/deep-research.js': RESEARCH }, env, cwd: '/srv/scratch/notes', root: '/srv/scratch/notes' })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
})

test('outside the home folder and any repository, the walk reaches the file system root', async ($, on) => {
  engine(on, { files: { '/.claude/workflows/scan.js': SCRIPT }, cwd: '/srv/scratch/notes', root: '/srv/scratch/notes' })
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

test('a script larger than 512 KiB is not a saved workflow, since Claude Code skips one so large', async ($, on) => {
  engine(on, { files: { '/srv/work/.claude/workflows/deep-research.js': OVERSIZED_RESEARCH } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
})

test('a saved workflow of exactly 512 KiB is found, since Claude Code skips only a larger one', async ($, on) => {
  engine(on, { files: { '/srv/work/.claude/workflows/todo-scan.js': SCRIPT.padEnd(512 * 1024, '/') } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a link to a script larger than 512 KiB is not a saved workflow, while a link to a smaller one is', async ($, on) => {
  // The user's own scripts kept in a dotfiles repository and linked into the personal folder.
  const files = {
    '/home/me/dotfiles/workflows/deep-research.js': OVERSIZED_RESEARCH,
    '/home/me/dotfiles/workflows/todo-scan.js': SCRIPT,
  }
  const links = {
    '/home/me/.claude/workflows/deep-research.js': '/home/me/dotfiles/workflows/deep-research.js',
    '/home/me/.claude/workflows/todo-scan.js': '/home/me/dotfiles/workflows/todo-scan.js',
  }
  engine(on, { files, links })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_research', name: 'deep-research', args: 'What changed?' })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(RESEARCH_AGENT)).toEqual(STARTED)
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a saved workflow whose meta name is in double quotes is found', async ($, on) => {
  const quoted = 'export const meta = {"name": "scan", "description": "Scan the repo"}\nawait agent("List the TODO comments")\n'
  engine(on, { files: { '/srv/work/.claude/workflows/todo-scan.js': quoted } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a script with an import before its meta is not a saved workflow, since Claude Code loads one only if meta comes first', async ($, on) => {
  const script = `import { readFile } from 'node:fs/promises'\n${RESEARCH}`
  engine(on, { files: { '/srv/work/.claude/workflows/deep-research.js': script } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
})

test('a saved workflow whose meta follows a line comment is found', async ($, on) => {
  const script = `// Lists the TODO comments for triage.\n\n${SCRIPT}`
  engine(on, { files: { '/srv/work/.claude/workflows/todo-scan.js': script } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a script commented out is not a saved workflow, though its comments hold a meta', async ($, on) => {
  const script = "// export const meta = {name: 'deep-research', description: 'Research'}\n// await agent('Search the web')\n"
  engine(on, { files: { '/srv/work/.claude/workflows/deep-research.js': script } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
})

test('a saved workflow whose meta follows a block comment is found', async ($, on) => {
  const script = `/**\n * Lists the TODO comments for triage.\n */\n${SCRIPT}`
  engine(on, { files: { '/srv/work/.claude/workflows/todo-scan.js': script } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a script with an import between two doc comments before its meta is not a saved workflow', async ($, on) => {
  const script = `/** Reads the notes the agents write. */\nimport { readFile } from 'node:fs/promises'\n\n/** The run. */\n${RESEARCH}`
  engine(on, { files: { '/srv/work/.claude/workflows/deep-research.js': script } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
})

test('a saved workflow that starts with a hashbang line is found', async ($, on) => {
  engine(on, { files: { '/srv/work/.claude/workflows/todo-scan.js': `#!/usr/bin/env node\n${SCRIPT}` } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a saved workflow whose meta holds a comment naming it otherwise, before its name, is found by its name', async ($, on) => {
  const script = "export const meta = {\n  // was name: 'todo-scan'\n  name: 'scan',\n  description: 'Scan the repo',\n}\nawait agent('List the TODO comments')\n"
  engine(on, { files: { '/srv/work/.claude/workflows/todo-scan.js': script } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a saved workflow whose meta description holds a name is found by the meta\'s own name', async ($, on) => {
  const script = "export const meta = {description: \"Finds files by name: 'TODO'\", name: 'scan'}\nawait agent('List the TODO files')\n"
  engine(on, { files: { '/srv/work/.claude/workflows/todo-scan.js': script } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a saved workflow with a comment between its meta\'s = and { is found', async ($, on) => {
  const script = "export const meta = /* the run */ {name: 'scan', description: 'Scan the repo'}\nawait agent('List the TODO comments')\n"
  engine(on, { files: { '/srv/work/.claude/workflows/todo-scan.js': script } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a saved workflow whose meta object is in parentheses is found', async ($, on) => {
  const script = "export const meta = ({name: 'scan', description: 'Scan the repo'})\nawait agent('List the TODO comments')\n"
  engine(on, { files: { '/srv/work/.claude/workflows/todo-scan.js': script } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a saved workflow whose meta names it twice runs by the last name, as Claude Code keeps it, not by one nested deeper', async ($, on) => {
  const meta = "export const meta = {name: 'todo-scan', description: 'Scan the repo', name: 'scan', phases: [{name: 'collect'}]}"
  engine(on, { files: { '/srv/work/.claude/workflows/todo-scan.js': `${meta}\nawait agent('List the TODO comments')\n` } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a script whose meta is not an object is not a saved workflow, since Claude Code loads one only if it is', async ($, on) => {
  const script = "export const meta = defineMeta({name: 'deep-research', description: 'Research'})\nawait agent('Search the web')\n"
  engine(on, { files: { '/srv/work/.claude/workflows/deep-research.js': script } })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
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

test('CLAUDE_CODE_SUBAGENT_MODEL_FORCE is on in any case and with blanks around it, as Claude Code reads it', async ($, on) => {
  engine(on, { env: { HOME: '/home/me', CLAUDE_CODE_SUBAGENT_MODEL_FORCE: 'TRUE ' } })
  expect(await $.agent.spawn(SPAWN)).toEqual(STARTED)
})

// Coordinator mode, with its workers forced onto the session's model: Claude Code clears an Agent call's model.
const COORDINATOR = { HOME: '/home/me', CLAUDE_CODE_COORDINATOR_MODE: '1', CLAUDE_CODE_COORDINATOR_FORCE_WORKER_INHERIT_MODEL: '1' }

test('in coordinator mode with workers forced to inherit, an agent starts without a model, while a workflow\'s is still checked', async ($, on) => {
  engine(on, { env: COORDINATOR })
  await $.session.start({ cwd: '/srv/work/pkg', surface: null, isInteractive: false })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', script: SCRIPT })
  expect(await $.agent.spawn(SPAWN)).toEqual(STARTED)
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('in an interactive local session, Claude Code keeps coordinator mode off, so an agent without a model is denied', async ($, on) => {
  engine(on, { env: COORDINATOR })
  await $.session.start({ cwd: '/srv/work/pkg', surface: 'terminal', isInteractive: true })
  expect(await $.agent.spawn(SPAWN)).toEqual({ deny: AGENT_REASON })
})

test('in an interactive session with CLAUDE_CODE_REMOTE on, coordinator mode is on, so an agent starts without a model', async ($, on) => {
  engine(on, { env: { ...COORDINATOR, CLAUDE_CODE_REMOTE: 'true' } })
  await $.session.start({ cwd: '/srv/work/pkg', surface: 'terminal', isInteractive: true })
  expect(await $.agent.spawn(SPAWN)).toEqual(STARTED)
})

test('a repository nested in the session\'s own walks on to the session repository\'s root', async ($, on) => {
  const files = { '/srv/work/vendor/lib/.git/HEAD': 'ref: refs/heads/main\n', '/srv/work/.claude/workflows/todo-scan.js': SCRIPT }
  engine(on, { files, cwd: '/srv/work/vendor/lib/src' })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
})

test('a repository outside the session\'s own stops at its own root', async ($, on) => {
  const files = { '/other/repo/.git/HEAD': 'ref: refs/heads/main\n', '/other/.claude/workflows/deep-research.js': RESEARCH }
  engine(on, { files, cwd: '/other/repo/pkg' })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'deep-research', args: 'What changed?' })
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual(STARTED)
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

test('inside a connector-downloads folder, the scripts saved there are not saved workflows, while the repository\'s still are', async ($, on) => {
  const files = {
    '/srv/work/connector-downloads/drive/.claude/workflows/deep-research.js': RESEARCH,
    '/srv/work/.claude/workflows/todo-scan.js': SCRIPT,
  }
  engine(on, { files, cwd: '/srv/work/connector-downloads/drive' })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_research', name: 'deep-research', args: 'What changed?' })
  await $.tool.call({ tool: 'Workflow', tool_use_id: 'toolu_workflow', name: 'scan' })
  expect(await $.agent.spawn(RESEARCH_AGENT)).toEqual(STARTED)
  expect(await $.agent.spawn(WORKFLOW_AGENT)).toEqual({ deny: WORKFLOW_REASON })
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

test('an agent spawned with a model starts, as Claude asked for it', async ($, on) => {
  const spawns = engine(on)
  expect(await $.agent.spawn({ ...SPAWN, model: 'sonnet' })).toEqual(STARTED)
  expect(spawns).toEqual([{ ...SPAWN, model: 'sonnet' }])
})
