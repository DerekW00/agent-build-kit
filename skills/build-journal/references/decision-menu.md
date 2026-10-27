# Review prompts

## Option search aid

Use only the rows relevant to the current problem. This is a search aid, not a list of decisions the user considered, a required checklist, or a claim of completeness. Add an option to the record as considered only after it was actually discussed or evaluated. Mark an untouched suggestion unexplored; identify an AI suggestion and who, if anyone, accepted it. Keep the status quo or simplest workable option in view when meaningful.

| Area | Credible directions to compare | Constraint that can decide |
| --- | --- | --- |
| Storage | No persistence; file; embedded database; existing managed database | Durability, queries, concurrent writers, data ownership, backup and operating cost |
| Execution | Synchronous work; bounded local background work; durable queue and worker | Response deadline, work duration, restart recovery, cancellation and ordering |
| API | Function or CLI; one endpoint; polling; webhook or stream | Actual caller, integration cost, compatibility, delivery guarantees and debugging |
| Errors and retries | Fail visibly; caller retry; bounded retry with backoff; manual recovery | Transient versus permanent failures, deadline, retry budget and observability |
| Idempotency | No retryable side effect; unique request key; database uniqueness or transaction; deduplication record | Duplicate delivery, side effect boundaries, retention and replay behavior |
| Security | Local-only access; existing authentication; least-privilege credentials; isolation | Data sensitivity, trust boundary, access policy, secret handling and audit needs |
| Agents and tools | Deterministic code; human step; one constrained agent; multiple agents | Whether judgment is needed, tool authority, recovery, review cost and failure isolation |
| Model use | No model; one available model; smaller/faster model; staged model and human review | Accuracy on representative cases, latency, cost, privacy and permitted access |
| Tests | Example check; focused unit test; integration test; end-to-end test | Most consequential failure, boundary behavior, test environment and maintenance cost |
| Deploy and operate | Run locally; existing service; scheduled job; separate service | User access, deployment deadline, rollback, monitoring and operational ownership |

Ask: Which requirement rules this option in or out? What evidence would change that judgment? What is the cheapest reversible way to learn? Never invent a measurement, a user preference, or a rejection reason to complete the comparison.

## Presentation questions

Choose the questions that expose the important reasoning; do not force every answer into a short presentation.

1. What problem did you receive, and how would success be observed?
2. Which actual constraint shaped the design most? Which constraints were only assumptions?
3. What credible alternatives did you consider, including the simplest one? Why did the chosen option fit better than each rejected or deferred alternative?
4. What did the human decide? What did AI suggest or draft? What reasoning was recorded at the time versus reconstructed later?
5. What was implemented, what was actually checked, and what remains a plan or unverified assertion? Where is the supporting evidence?
6. Which hypothesis failed, what evidence contradicted it, and how did the design or next step change?
7. What tradeoff did you accept? How would you reverse the choice, and what would trigger that work?
8. With more time or a changed requirement, what would you investigate next without claiming it is already necessary?

Keep answers tied to the records. A good explanation can say “we do not know yet.” It need not make an unfinished build sound complete.

## Short speaking outline

Create a separate, editable outline from the evidence packet. Choose a duration with the audience; do not read the full packet aloud.

1. Problem and success criterion: one sentence each.
2. Request trace: walk one actual request through the implementation.
3. One or two consequential decisions: constraint, credible alternatives, choice, accepted downside, and evidence. State whose choice it was.
4. One failure or correction: what you expected, what happened, what changed, and what remains unknown.
5. Demonstrate observed behavior; end with limits and the next discriminating check.

Challenge each selected decision: what is the strongest credible alternative, under what changed requirement would it win, and what observation would disprove your current assumption? Separate a new adversarial suggestion from options considered at the time. If the reason is undocumented, say so. A targeted review compares options under actual constraints; an exhaustive technology list adds work without proving judgment.
