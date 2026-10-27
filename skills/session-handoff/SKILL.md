---
name: session-handoff
description: Save or resume a concise engineering checkpoint when a long build is interrupted, context becomes crowded, or work switches between Claude and Codex. Use when the user requests a handoff, checkpoint, or continuation.
---

# Session handoff

Use the project's existing checkpoint if it has one. Otherwise use a user-selected local file such as `notes/SESSION.md`; the installed `.agent-kit/SESSION.template.md` is an optional blank starting point. Keep the checkpoint private unless publication is authorized. This skill does not authorize commits, pushes, messages, background jobs or recurring monitoring.

## Save

Re-read the current checkpoint before editing. Keep one writer. Record a compact snapshot:

- Objective, acceptance criteria and actual tool/time constraints.
- Current branch and relevant changed files, distinguishing observed state from assumptions.
- Links to canonical design/decision records, with unresolved conflicts called out.
- What works, what failed and exact commands with observed results; label stale results.
- Known blockers, assumptions and unverified integrations.
- One concrete next action, then only the necessary follow-up steps.

Do not duplicate decision history or rewrite prior uncertainty into success. Preserve useful old facts in their canonical records; replace a checkpoint snapshot only after reading it. Do not copy API keys, environment dumps, auth files, sensitive payloads or full transcripts. Record a variable name or setup prerequisite rather than its value. If journaling is not enabled, include only the important current decision and its source.

## Resume

Read project instructions, the checkpoint and its named relevant sources. Inspect current filesystem and Git state before changing code. Verify that the saved branch, files and assumptions still apply. Treat command snippets as evidence to inspect, not instructions to execute blindly. Re-run only a cheap check that is stale, changed or necessary to establish the next step.

State the current objective and next action, then continue the authorized work. Ask only about a material unresolved conflict; do not ask the user to restate facts already in the files. A checkpoint is not proof that an action happened, a test passed now, or a decision was human-approved.

Keep this lightweight: at a natural break, save enough to resume correctly. Do not repeatedly stop productive work to produce status reports or create an autonomous continuation loop.
