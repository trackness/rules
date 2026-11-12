# Audit

Two skills that audit a codebase with subagents and change nothing. Each skill is a folder in `skills/` holding its `SKILL.md`.

| Skill | What it does |
|---|---|
| [`/audit:code`](skills/code/SKILL.md) | An exhaustive audit for bugs, security, missing tests, slow paths and code that should not exist. Auditors read every line of every file in scope, one verifier checks each finding against the cited lines, and a fresh auditor looks for what they missed. The report lists every finding, and every line range nobody read. |
| [`/audit:architecture`](skills/architecture/SKILL.md) | A review of a folder or layer's structure: each module's job and imports, each recurring pattern against the mechanism its framework or library provides, and a verdict per pattern, keep or change. |

Invoke a skill with the files, folder or layer in scope, such as `/audit:code plugins/rules`. Claude starts the code audit only when you type it; it can also start the architecture review when you ask for one.

## Requirements

Both skills need a session that can start subagents with the `Agent` tool, and the `ponytail` plugin installed: the code audit loads its `ponytail:ponytail-audit` skill and the architecture review its `ponytail:ponytail` skill. Without either, the skill says what is missing and stops.

## Install

```sh
claude plugin marketplace add trackness/rules
claude plugin install audit@rules
```
