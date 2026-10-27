# Portable kit execution

- [x] Inventory installed skills and configurations privately; record coverage and exclusions.
- [x] Review current primary sources and choose a small portable core.
- [x] Create original workflow skills and a sanitized Build Journal bundle.
- [x] Implement dry-run installer, doctor and packaging tests.
- [x] Run independent privacy and method review plus fresh-install checks.
- [x] Publish reviewed files on a public feature branch and attach a draft PR.

Published: https://github.com/DerekW00/agent-build-kit/tree/feat/portable-kit

Draft review: https://github.com/DerekW00/agent-build-kit/pull/1

Initial version 0.1: fresh public clone, 60 tests, both-provider install and manual profile verified. See docs/verification.md for scope and limits.

Private audit inputs never belong in this repository. Public access was explicitly requested. Personal-material permission in assessments is separate and unconfirmed.

## Research and design extension

- [x] Define three small, original skills with a common provider-neutral format.
- [x] Add a design profile that preserves existing base installations.
- [x] Document fresh setup, add-on setup and direct usage in both providers.
- [x] Run independent adversarial review, behavioral forward tests and installer checks.
- [x] Publish the reviewed update on the existing public branch and refresh its draft PR.

Version 0.2: 68 tests, three new skill-format checks, independent adversarial/forward review, native seven-skill discovery and fresh public-download installs verified. Setup: docs/research-design.md. Review and all changed paths: docs/research-design-review.md.

## One-repository clarification — October 27, 2026

- [x] Confirm Build Journal is already bundled with its helper, templates and references.
- [x] Make the main README setup install all seven skills, including Build Journal.
- [x] Verify a fresh public download and standalone installed journal without the checkout.
- [ ] Publish README clarification and update the existing draft PR.

Changed paths for this clarification: README.md and plan.md.

October 27 evidence: credential-free public clone at 00e94bec passed 68 tests, compilation and whitespace checks. Both installed Build Journal copies ran help, init, decision, log and present after deleting the downloaded checkout. The checker correctly reported unresolved template placeholders; no separate Build Journal checkout was used.
