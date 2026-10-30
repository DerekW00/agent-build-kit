# Lightweight research and design

These are optional, original skills. They need ordinary project-file access and whatever documentation tools the host already provides. They do not require a plugin, a particular model, another agent, an API key or a background process. Use AI only when allowed by the actual task.

## Setup

For a fresh existing project directory, choose `--profile long-session` to install all seven skills. For an existing build kit or an older long-session kit without these three skills, choose `--profile design` to add them. Version 0.2 long-session already contains them; do not apply the add-on again. Follow the README's dry-run and `--apply` commands. The add-on creates `.agent-kit/design/` and leaves base files unchanged.

Claude Code loads `.claude/skills/<name>/SKILL.md`; Codex loads `.agents/skills/<name>/SKILL.md`. Open the target project and check the skill list. Restart if newly installed skills do not appear. If a same-name global/plugin skill exists, inspect the selected path. You can explicitly ask the assistant to read the desired project `SKILL.md` as a fallback; this does not prove native discovery.

## Pick the step you need

| Step | Concrete output | Stop when |
| --- | --- | --- |
| Technical research | Question/version, source-linked facts, credible alternatives, recommendation, unknowns, smallest probe | The current decision has enough evidence, or the remaining gap is clear |
| System design | Components/request flow, data ownership, contracts, failure handling, consequential tradeoffs, first working slice | The mechanism and its important uncertainties can be explained |
| Design review | A few concrete failure scenarios, evidence status, impact, minimal repair and recommended disposition | Material concerns are reported; a quota of findings is not required |

The current build-session skill already handles acceptance criteria and scope. Research adds evidence retrieval; system-design adds mechanism detail; design-review challenges architecture before code exists. None requires running the others. A quick API question should not become three documents.

## Example prompts

Enter these inside the coding assistant, not a terminal. The examples name output files explicitly; omit the save request when a chat answer is enough. If files already exist, have the assistant read and update them rather than overwrite unrelated notes.

| Claude Code prefix | Codex prefix |
| --- | --- |
| `/technical-research` | `$technical-research` |
| `/system-design` | `$system-design` |
| `/design-review` | `$design-review` |

Append the same prompt text after either provider's prefix:

**Technical research**

> Determine how to make repeated job-submission requests safe in this project's installed database/library versions. Inspect the project first. Compare the simplest credible options using official sources. Separate documented guarantees from inference. Save a short note to notes/RESEARCH.md with sources, unknowns and one minimal verification proposal. Documentation browsing is allowed. Do not install dependencies or invoke application/service APIs as part of a probe.

**System design**

> Design the service described in TASK.md, using notes/RESEARCH.md where applicable. Save a compact design to notes/DESIGN.md: request flow, records and keys, API/tool contracts, authorization, meaningful failure states, important alternatives and the first working slice. Label assumptions and unverified claims. Do not implement code.

**Design review**

> Review notes/DESIGN.md against TASK.md. Find the most consequential concrete failure scenarios. Separate contradictions from plausible risks and missing information. For each finding, give a minimal repair and a check that would settle it. Save notes/DESIGN-REVIEW.md. Do not edit the design or code, and do not manufacture findings to fill a quota.

## Keep the record honest

A proposal is not a human-approved decision; a possible downside is not an accepted tradeoff; a planned probe is not a passing test. Link research/design/review notes from the journal when journaling is requested, rather than duplicating decision history. Use one recorder for shared notes.

For short builds, focus on one blocking uncertainty, one compact design and one review pass if needed. For longer work, preserve evidence links and resume from the checkpoint; revisit assumptions when requirements or versions change. Use exact local/library versions and current primary sources when browsing is allowed. If offline, use supplied material and explicitly state the coverage limit.

For book-backed research, version 0.3 includes a complete bibliography and local PDF helper inside technical-research. [Library setup](library-setup.md) explains private source access, bounded page reading and citations. The books themselves are not included. The [topic map](../skills/technical-research/references/library-workflow.md) connects likely engineering questions to candidate chapters; it does not claim that every chapter has been read.

There is no exhaustive-options guarantee. Compare the options that can change the actual decision. A skill should help you explain the mechanism yourself; it does not establish correctness or replace independent checks of implementation.
