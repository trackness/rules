---
name: architecture
description: Read-only review of module responsibilities, dependencies, and recurring implementation patterns against native framework or library mechanisms. Use for architecture and structural design reviews, rather than an exhaustive defect audit.
---

## Required capabilities

Before starting the review or delegating work:

- Locate and load the installed `ponytail:ponytail` skill. If it is unavailable or cannot be read, report the exact missing skill and stop. Do not reconstruct or substitute its instructions.
- Confirm that this session provides subagent tools usable for separate reviewers for each layer. If unavailable, report that the prescribed workflow cannot run and stop. Do not silently substitute a single-agent review.
- Pass the relevant Ponytail skill and these requirements to each delegated reviewer or auditor; require them to report any dependency failure rather than proceed without it.

Audience: Claude Code. Invoke with `/audit:architecture` and a folder or layer.

Review the structure of the folder or layer supplied by the user. Read-only: change nothing.

Split it by layer, one subagent reviewer each using the `Agent` tool. Each reviewer loads `ponytail:ponytail` first and returns:

1. A map: each module's one job, its size, and what it imports.
2. Each recurring pattern (how a command, request, model, error, help text or test is built), with one cited example.
3. For each pattern: the tool's own mechanism or a house one? Cite the documented alternative from the library's source or docs, and from the upstream project when there is one. Say what the current way costs or buys: lines, duplication, start-up time, IDE and type-checker load.
4. A verdict per pattern: keep, or change. Name the change and what it would break. A proposed change is the smallest one that removes the cost; prefer deleting to adding.

Every claim cites file:line or a concrete case. Mark inference as inference. No style taste.

Then combine into one answer: the map, the patterns ranked by consequence, and the three changes with the biggest payoff. Plain English, at most 900 words.
