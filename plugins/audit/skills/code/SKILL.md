---
name: code
description: Exhaustive read-only code audit for bugs, security, tests, performance, and unnecessary code. Reads every line in scope, independently verifies findings, and checks for omissions. Use when explicitly asked for exhaustive coverage, rather than an architecture-focused review.
disable-model-invocation: true
---

## Required capabilities

Before starting the review or delegating work:

- Locate and load the installed `ponytail:ponytail-audit` skill. If it is unavailable or cannot be read, report the exact missing skill and stop. Do not reconstruct or substitute its instructions.
- Confirm that this session provides subagent tools usable for independent auditors and finding verifiers. If unavailable, report that the prescribed workflow cannot run and stop. Do not silently substitute a single-agent review.
- Pass the relevant Ponytail skill and these requirements to each delegated reviewer or auditor; require them to report any dependency failure rather than proceed without it.

Audience: Claude Code. Invoke with `/audit:code` and state the files or repository in scope.

Load and follow the installed `ponytail:ponytail-audit` skill. The exhaustive coverage and verification requirements below override its sampling and report limits.

Do not look up old session files.
Read every line of every file in scope, file by file: no sampling, ignore "go deep where it costs most".
Report every finding: no limit of 20.

Use the `Agent` tool to create subagents for this workflow:

- first, split the files in scope into areas small enough for one auditor to read in full, and show me the split
- one auditor per area, each reading its area in full and returning every file and line range it read
- one verifier per finding, told to refute it, which opens the cited lines and quotes them, reproduces the case against the real code, tests the proposed fix in its own copy in the scratchpad folder and corrects it, gives a verdict (confirmed, partly, not confirmed) and a severity, and names any other problem it saw as a lead; drop any finding it cannot confirm, and report the verifier's fix, not the auditor's
- one fresh auditor that gets the reading lists, the findings and the leads the verifiers raised, and looks only for what they missed; each finding it adds gets its own verifier

Name a model on every spawn, chosen by how hard its task is: verifiers and the gap auditor can run on a cheaper one than yours. Run at most 20 agents at once, launching the next as one finishes. Put what you pass to every agent in one brief file in the scratchpad folder, so each prompt carries only its area or finding, and add these rules to it: never print the environment; never run a test suite with `GIT_DIR` set; start no live interactive session; read no old session files; write scratch files only in the scratchpad folder; a block from an installed hook is evidence, not something to work around.

After each launch and each report, give me a short status with a table of every agent's state: ✅ done, 🚧 running, 📬 finished but report pending, 🔁 sent back, ⚠️ problem. Say plainly what went wrong, what you decided for me and why, what was left out, and the risk to know.

Not checked must list every line range nobody read.

End the report with one table of every finding, the dropped ones too: #, Sev, Where, Problem and Fix in short. Sev is 🔴 must fix, 🟠 should fix or 🟡 nice to have; a finding a verifier refuted has ❌ there, and one that is true but not counted ➖.
