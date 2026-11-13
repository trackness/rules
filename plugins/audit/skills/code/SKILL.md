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
- one verifier per finding, which opens the cited lines and quotes them; drop any finding it cannot confirm
- one fresh auditor that gets the reading lists and the findings and looks only for what they missed

Not checked must list every line range nobody read.
