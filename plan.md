# Portable kit execution

- [x] Inventory installed skills and configurations privately; record coverage and exclusions.
- [x] Review current primary sources and choose a small portable core.
- [x] Create original workflow skills and a sanitized Build Journal bundle.
- [x] Implement dry-run installer, doctor and packaging tests.
- [x] Run independent privacy and method review plus fresh-install checks.
- [x] Publish reviewed files on a public feature branch and attach a draft PR.

Published: https://github.com/DerekW00/agent-build-kit

Initial review (merged October 27, 2026): https://github.com/DerekW00/agent-build-kit/pull/1

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
- [x] Publish README clarification and update the existing draft PR.

Changed paths for this clarification: README.md and plan.md.

October 27 evidence: credential-free public clone at 00e94bec passed 68 tests, compilation and whitespace checks. Both installed Build Journal copies ran help, init, decision, log and present after deleting the downloaded checkout. The checker correctly reported unresolved template placeholders; no separate Build Journal checkout was used.

## Main-branch setup correction — October 29, 2026

- [x] Verify the initial PR is merged and `main` contains the complete kit.
- [x] Use `main` in current clone and update instructions; retain dated historical evidence.
- [x] Run repository checks and a fresh long-session installation for both providers.
- [x] Publish the correction for review: https://github.com/DerekW00/agent-build-kit/pull/2 (draft; merge pending).

Changed paths: README.md and plan.md. The existing installer and skills are unchanged.

October 29 evidence: the correction starts from `main` at `6c2909d`. All 68 tests passed; compilation and whitespace checks passed. A fresh temporary project was unchanged by the dry run, then received all seven skills for both providers; both installed journal helpers ran successfully. The previous feature branch appears only in the dated historical clone record in docs/verification.md.
