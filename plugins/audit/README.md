# Audit

Skills that audit a codebase with subagents, and one that fixes what the code audit finds. Each skill is a folder in `skills/` holding its `SKILL.md`.

| Skill | What it does |
|---|---|
| [`/audit:code`](skills/code/SKILL.md) | An exhaustive audit for bugs, security, missing tests, slow paths and code that should not exist. Auditors read every line of every file in scope, one verifier checks each finding against the cited lines, and a fresh auditor looks for what they missed. The report lists every finding, and every line range nobody read. It changes no code, and leaves every finding in an untracked `AUDIT-FINDINGS.md` at the repo root. |
| [`/audit:code-fix`](skills/code-fix/SKILL.md) | Starts from the `AUDIT-FINDINGS.md` that `/audit:code` leaves. It triages the findings, has one agent per group of files fix them test first, each in its own worktree and branch, then merges the branches into one local branch and runs every suite on it. It commits on local branches only: pushing, a pull request and merging into the default branch wait for your word. |
| [`/audit:architecture`](skills/architecture/SKILL.md) | A review of a folder or layer's structure: each module's job and imports, each recurring pattern against the mechanism its framework or library provides, and a verdict per pattern, keep or change. |

Invoke a skill with the files, folder or layer in scope, such as `/audit:code plugins/rules`, and `/audit:code-fix` in the repo holding the findings file. Claude starts the code audit and the fix run only when you type them; it can also start the architecture review when you ask for one.

## Requirements

All three skills need a session that can start subagents with the `Agent` tool. The code audit and the architecture review also need the `ponytail` plugin installed: the code audit loads its `ponytail:ponytail-audit` skill and the architecture review its `ponytail:ponytail` skill. Without either, they say what is missing and stop.

## Install

```sh
claude plugin marketplace add trackness/rules
claude plugin install audit@rules
```
