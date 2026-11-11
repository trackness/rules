import type { EngineInterface, Register } from 'claude-code'

const AGENT_REASON =
  'Every subagent must run on a model appropriately capable for its task. Retry this call with the model parameter set to that model.'
const WORKFLOW_REASON =
  'Every agent a workflow spawns must run on a model appropriately capable for its task. Set the model option of every agent() call to that model, then run the workflow again.'

/** True if value names a model for a subagent to run on: neither empty nor inherit. */
function namesAModel(value: string | undefined): boolean {
  return Boolean(value) && value !== 'inherit'
}

/** True if an environment variable is on, as Claude Code reads one: 1, true, yes or on, in any case. */
function isOn(value: string | undefined): boolean {
  return ['1', 'true', 'yes', 'on'].includes(value?.toLowerCase().trim() ?? '')
}

/** The script from its first statement on, past a hashbang line and the whitespace and comments that may come before it. */
function fromFirstStatement(script: string): string {
  // With nothing after it to match, the pattern never backtracks into a comment, so each ends where JavaScript ends it.
  return script.replace(/^(?:#!.*)?(?:\s|\/\/.*|\/\*[\s\S]*?\*\/)*/, '')
}

/** The name a saved workflow runs by: its meta's name, not its file's, if meta comes first, as Claude Code requires to load it. */
function metaName(script: string): string | undefined {
  return /^export\s+const\s+meta\s*=\s*\{[\s\S]*?\bname['"]?\s*:\s*(['"`])(.*?)\1/.exec(fromFirstStatement(script))?.[2]
}

/** The path with / for every separator, so a Windows path walks as a POSIX one does. */
function slashed(path: string): string {
  return path.replace(/\\/g, '/')
}

/** The directory above dir, or dir itself at a file system root (/ or C:/). */
function parentOf(dir: string): string {
  const parent = dir.slice(0, dir.lastIndexOf('/'))
  return parent === '' || parent.endsWith(':') ? `${parent}/` : parent
}

/** The root of the git repository holding dir: the nearest directory, dir or above, that has a .git. */
async function repoRoot($: EngineInterface, dir: string): Promise<string | undefined> {
  for (let at = dir; ; at = parentOf(at)) {
    if (await $.fs.exists(`${at.replace(/\/$/, '')}/.git`)) return at
    if (parentOf(at) === at) return undefined
  }
}

/** True if the repository at root is a worktree of the one at outer: its .git is a file pointing into outer's. */
async function isWorktreeOf($: EngineInterface, root: string, outer: string): Promise<boolean> {
  // shortcut: reads the absolute gitdir git writes by default; resolve a relative one if worktree.useRelativePaths spreads.
  return slashed(await $.fs.read(`${root}/.git`).catch(() => '')).includes(`${outer}/.git/worktrees/`)
}

/**
 * The folders Claude Code 2.1.322 loads saved workflows from, as its binary walks them: .claude/workflows in the working
 * directory and in each one above it, stopping before the home folder and after the repository root, or at the file
 * system root outside a repository and the home folder. A repository nested in the session's own, unless it is a
 * worktree of it, walks on to the session repository's root. The walk passes over, without stopping, every directory
 * whose path goes through a folder named connector-downloads. Then the personal folder: workflows in CLAUDE_CONFIG_DIR,
 * which is .claude in the home folder unless set, and the project root if set but empty.
 */
async function savedWorkflowFolders($: EngineInterface): Promise<string[]> {
  // The home folder as os.homedir() takes it: USERPROFILE on Windows, HOME elsewhere, even where USERPROFILE is set (WSL).
  const isWindows = (await $.env.get('OS')) === 'Windows_NT'
  const homeVar = isWindows ? await $.env.get('USERPROFILE') : await $.env.get('HOME')
  const home = homeVar === undefined ? undefined : slashed(homeVar)
  const cwd = slashed(await $.session.cwd())
  const projectRoot = slashed(await $.session.root())
  const sessionRepo = await repoRoot($, projectRoot)
  let repo = await repoRoot($, cwd)
  if (repo !== undefined && sessionRepo !== undefined && repo.startsWith(`${sessionRepo}/`) && !(await isWorktreeOf($, repo, sessionRepo))) {
    repo = sessionRepo
  }
  const folders: string[] = []
  for (let dir = cwd; dir !== home; dir = parentOf(dir)) {
    if (!dir.split('/').includes('connector-downloads')) folders.push(`${dir.replace(/\/$/, '')}/.claude/workflows`)
    if (dir === repo || parentOf(dir) === dir) break
  }
  // Claude Code takes an empty CLAUDE_CONFIG_DIR as a relative path, read in the directory it runs in: the project root.
  const configVar = await $.env.get('CLAUDE_CONFIG_DIR')
  const configDir = configVar === '' ? projectRoot : (configVar ?? (home === undefined ? undefined : `${home}/.claude`))
  if (configDir !== undefined) folders.push(`${slashed(configDir)}/workflows`)
  return folders
}

/** True if a workflow saved on disk, a script Claude could have written, runs by this name. */
async function isSavedWorkflow($: EngineInterface, name: string): Promise<boolean> {
  for (const folder of await savedWorkflowFolders($)) {
    for (const entry of await $.fs.list(folder).catch(() => [])) {
      if (!entry.name.endsWith('.js')) continue
      if (metaName(await $.fs.read(`${folder}/${entry.name}`).catch(() => '')) === name) return true
    }
  }
  return false
}

export const register: Register = (on) => {
  // The ids of the Workflow calls running a script Claude could have written, which its agents' spawns carry as their
  // tool_use_id. A plugin can't call Workflow (the engine refuses it), so every call seen here is Claude's.
  // No .catch, as with the rules plugin's hooks: if a hook fails, the engine skips it and the call goes through.
  const scripted = new Set<string>()
  on('tool.call', { tool: 'Workflow' }, async ($, e, next) => {
    const isScripted = e.script !== undefined || e.scriptPath !== undefined
    if (isScripted || (e.name !== undefined && (await isSavedWorkflow($, e.name)))) scripted.add(e.tool_use_id)
    return next(e)
  })
  on('agent.spawn', async ($, e, next) => {
    // A plugin's own spawn is raised under that plugin's origin, and is its business, not Claude's.
    if (next.origin.tier !== 'core') return next(e)
    // A resumed run keeps the model it started on, and a fork always runs on the caller's.
    if (e.resume || e.fork || namesAModel(e.model)) return next(e)
    // Claude can't change the script of a built-in or plugin workflow, so a block there would only break it.
    if (e.workflow && !scripted.has(e.tool_use_id)) return next(e)
    // Where the session forces every subagent's model, Claude Code ignores the call's, so there is none to ask for.
    if (isOn(await $.env.get('CLAUDE_CODE_SUBAGENT_MODEL_FORCE'))) return next(e)
    // Likewise a workflow agent's, while CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL names a model.
    const workflowModel = (await $.env.get('CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL'))?.trim()
    if (e.workflow && workflowModel && workflowModel.toLowerCase() !== 'inherit') return next(e)
    return { deny: e.workflow ? WORKFLOW_REASON : AGENT_REASON }
  })
}
