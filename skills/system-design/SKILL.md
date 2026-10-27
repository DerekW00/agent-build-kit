---
name: system-design
description: Design a small software system with concrete component flow, data ownership, interfaces, failure behavior and justified tradeoffs. Use before implementation or for a material architecture change; reuse existing acceptance criteria rather than repeating general task planning.
---

# System design

Read the task, existing design and relevant project constraints. Reuse acceptance criteria and research already recorded. Distinguish requirements, assumptions and proposed scope cuts. Ask only about a missing constraint that materially changes the design; do not invent traffic, reliability, compliance or scale targets.

## Describe a buildable mechanism

Default to roughly one page for a small build. Use a compact text or Mermaid diagram if it clarifies the flow. Include the parts needed to explain the design:

- Components and a representative request's path through them, including external dependencies and trust boundaries.
- Data ownership, important records/keys and state transitions. Explain what is persisted and why; distinguish authoritative state from derived or temporary data.
- API or tool inputs, outputs, validation, authorization and relevant error behavior. Identify which trusted code supplies identity and enforces access.
- A meaningful failure path and recovery behavior. Apply retries, idempotency, transaction boundaries, cancellation and resource limits only where they address a real requirement or failure mode.
- The smallest end-to-end slice, observable acceptance checks, and what remains unresolved or outside the requested scope.

For an agentic system, separate model suggestions from authorized actions. Describe how trusted application code validates tool arguments and permissions, bounds execution, and handles malformed output or tool failure. Make fake/live dependencies explicit. Do not treat prompt wording as an access-control mechanism or assume retrying a side effect is safe.

## Make the consequential choice explainable

Compare credible alternatives against the actual constraints. State the recommendation, why each relevant alternative loses here, the downside and what evidence would trigger reconsideration. One viable option is acceptable when constraints rule out others. Do not claim to enumerate every possible architecture.

Distinguish a proposed downside from a tradeoff the decision owner explicitly accepted. Label new agent analysis and delegated engineering choices; do not reconstruct undocumented human reasons. A diagram or design document does not establish that the system is implemented, tested, secure or scalable.

## Hand off a small result

Return the design in the requested format. Save only when requested, using an existing design document or the named destination. Link canonical research and decision records instead of copying them. Reuse `build-journal` if available and requested; neither it nor another skill is required.

If review is requested, a bounded `design-review` pass can challenge the mechanism before implementation. Do not automatically launch reviewers, impose an approval ceremony or expand into a large architecture document. A design-only request does not authorize code changes, dependency installation or deployment. Follow the project's actual tool and assessment rules; do not use AI during a prohibited phase.
