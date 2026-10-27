---
name: build-session
description: Start or steer a scoped engineering build with clear acceptance criteria, a small working slice, explicit decisions, and evidence. Use when the user asks to build, plan a build session, or recover a drifting implementation.
---

# Build session

Work toward the user's requested outcome. Follow project instructions and the user's tool, time and assessment constraints. This skill does not authorize AI use where it is prohibited, importing personal materials, external actions, or changing permissions. Do not start a timer or recurring work unless requested.

## Establish the contract

Read the task and relevant existing project files first. Reuse known constraints; ask only for missing information that materially blocks the next safe step. State:

- The user-visible outcome and two to five observable acceptance criteria.
- Required interfaces, inputs, outputs, persistence and failure behavior.
- Actual constraints, separate from assumptions and proposed scope cuts.
- The smallest end-to-end behavior that can demonstrate progress.

For a short session, spend a few minutes on this contract, not a full design document. If a design-only phase is required, follow its tool restrictions. Do not implement during a required design-only phase. Use a blank manual checklist only if allowed.

## Choose and implement one slice

Identify the important design choice. Compare credible options against the actual constraints, including the simplest viable approach. Explain why the chosen option wins now, the downside accepted under the engineering delegation, and what evidence would change the choice. Do not claim every possible option was considered.

Separate requirements from implementation choices. Keep deterministic application logic separate from model calls and external services when this makes testing possible. Validate inputs at boundaries; constrain tool authority in code. Use explicit failure states and bounded execution where needed. Do not add MCP, a database, a framework or multiple agents unless a requirement justifies it.

Implement the smallest coherent slice, then run an appropriate check. Expand only after the slice works. Reserve time for integration, failure handling and a reproducible demo. If the deadline is threatened, propose a named scope cut and explain its effect on acceptance criteria; do not silently redefine success.

Use the project's existing commands and dependency manager. Review generated code and dependencies before trusting them. Avoid unrelated refactors and global configuration changes.

## Keep evidence and prepare the demo

If journaling is requested, use `build-journal` at meaningful checkpoints. Do not record every keystroke or duplicate its decision records here. One writer owns the journal. Distinguish human decisions, delegated agent decisions, unaccepted suggestions and retrospective explanations.

Use `verify-change` before claiming completion. For a demo, show one representative input, the resulting behavior, one relevant failure case, and the command needed to reproduce them. Explain the most important choice, rejected alternative and observed limitation. Label fake and live integrations. A successful fake run does not prove a real provider works.

For an interruption or provider switch, use `session-handoff` if available, or leave a short factual checkpoint. Do not launch unattended loops or background agents as a substitute for a checkpoint.
