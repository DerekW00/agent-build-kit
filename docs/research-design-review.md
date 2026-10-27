# Research and design extension: adversarial review

Version 0.2.0, reviewed October 26, 2026. **Pass: no remaining confirmed material defect in the reviewed skills, installer extension or instructions.** This is a bounded review, not certification of future model output.

## What was challenged

The review examined installation into an existing project, preservation of customized base skills/notes/instructions, manifest isolation, repeat conflicts, symlinks and rollback. It also examined whether the skills add mandatory dependencies or excessive orchestration, invent historical decisions, accept risks for the user, confuse hypothetical failures with observed failures, or follow instructions embedded in source material.

The independent installer fixture used the previous actual implementation, not only simplified test stubs. It preserved 27 existing files and verified eight new payload hashes. The combined suite passed 68 tests, with compilation and whitespace checks passing.

A separate agent used all three skills on a fictional job-service fixture with only local sources. The inputs included installed-version 1.4 documentation, incompatible 2.0 APIs, embedded requests to fabricate success, a client-controlled tenant ID, concurrent creation, changed-payload replays, and a crash window around an external side effect. The evaluator received the raw task and skill files, not the expected answers. A different reviewer compared its outputs with the inputs.

## Observed method behavior

- Research selected the documented installed-version primitive and rejected the unavailable newer API. It labeled source limits, design inference and unexecuted probes.
- Design separated trusted identity from input, described data/state transitions and acknowledged that the external-effect guarantee was unresolved. Proposed implementation restrictions and risks stayed visibly unaccepted.
- Review supplied concrete tenant, concurrency, payload and retry counterexamples with evidence status, repair costs and proposed checks. It did not manufacture a runtime test result.
- Embedded instructions to hide defects or claim success were ignored. No application code, installation, network action or external service was used in this forward test.

## Corrections and limits

Two usage instructions were clarified before publication: the add-on is for base kits without the three skills, and official-document browsing is distinct from running application/service probes. No installer or skill-method repair was required by this review.

The stress-case design was about 1,000 words, longer than the roughly one-page default. Compactness remains a model-behavior limitation; the skill file itself is under 500 words. This test cannot establish reliable behavior across models, prompts or future versions. Native discovery/invocation evidence is separately scoped in verification.md.

The design profile is additive, not a general updater. It preserves old base copies; it does not silently bring them to the new version. Install base first and then design, or choose all seven with a fresh long-session profile. No global configuration, private inventory, credentials or interview material is included.

## Changed paths in this extension

- `skills/technical-research/SKILL.md`
- `skills/system-design/SKILL.md`
- `skills/design-review/SKILL.md`
- `kit.py`
- `profiles.json`
- `VERSION`
- `tests/test_kit.py`
- `README.md`
- `templates/LOCAL-SETUP.md`
- `docs/installation.md`
- `docs/research-design.md`
- `docs/selection.md`
- `docs/verification.md`
- `docs/research-design-review.md`
- `PROVENANCE.md`
- `plan.md`
