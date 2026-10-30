# Library extension review — October 29, 2026

Version 0.3 extends the existing technical-research skill. It adds no new skill name, profile, MCP server, model configuration or background process. The existing installer copies the complete research bundle into both provider directories.

## Observed checks

- All **87 repository tests passed**: the previous 68 plus 19 library tests.
- Compilation and `git diff --check` passed.
- Both-provider long-session installs include the helper. Tests ran each installed helper after deleting the copied kit checkout.
- Real `pdftotext` extraction worked on a synthetic PDF; a malformed PDF was rejected. Tests cover missing executables, subprocess timeouts, bounded output, empty PDFs, spaces/Unicode, traversal, symlinks and incomplete scan coverage.
- A read-only scan of the source library reported **262 visible PDFs: 251 nonempty/unverified and 11 empty**. The public catalog has exactly those 262 unique relative paths and states the exclusions. Hidden exports and non-PDF artifacts are outside this inventory.
- A live filename search found the expected Transactions chapter. Reading its first PDF page returned text without truncation; this checks extraction, not the chapter's full content or a design conclusion. No book text was saved in this repository.
- An independent adversarial reviewer found a case-sensitivity gap in the initial ignore patterns. The corrected patterns match lowercase, uppercase and mixed-case PDF/EPUB suffixes, verified with `core.ignorecase=false`. The reviewer reported no remaining confirmed defects.
- Local links in the new documentation resolved. The review found no book bodies, personal absolute paths, credentials or interview records in the new public artifacts.
- In an independent read-only forward-use trial, the skill received a retry-design question, an empty PDF and a synthetic PDF containing no relevant contract. The agent reported the missing evidence, avoided fabricating citations, separated its inference from source claims and proposed a test without claiming to execute it. This is one observed trial, not a general behavior guarantee.
- A credential-free public clone at `12f238e` passed all 87 tests, compilation and whitespace checks. Its dry run left an empty target unchanged; installation verified all 35 manifest payload hashes and seven skills per provider. Both installed research helpers searched and extracted a synthetic PDF, and both journal helpers ran, after the downloaded checkout was removed. Later edits in this review update publication evidence only.

The optional skill-creator validation script could not run because its PyYAML dependency was absent from both available Python runtimes tried. No dependency was installed. The repository's own skill-format/packaging tests passed; this is not a claim that the optional validator passed.

## Limits

The public bibliography contains filenames, relative paths and availability metadata, not source text or redistribution rights. Nonempty does not mean readable, complete or content-reviewed. Its ten chapter-based collections are not the entire list of distinct books; standalone and unidentified files are also included.

Filename search is deliberately not full-text or semantic retrieval. PDF extraction requests up to five pages and may truncate returned text. PDF indices can differ from printed book pages. Image-only documents may need a viewer or separate OCR. The helper invokes the trusted `pdftotext` on PATH and is a local convenience tool, not a sandbox for hostile PDFs or a filesystem changing concurrently.

Both-provider file installation and standalone helper execution are verified. This release does not claim a new end-to-end model session in each native host, flawless citation behavior, permission to import materials into an assessment, or an upgrade of previously installed project copies. The installer continues to refuse conflicting destinations.

## Changed paths

- `.gitignore`
- `PROVENANCE.md`
- `README.md`
- `VERSION`
- `docs/installation.md`
- `docs/library-review.md`
- `docs/library-setup.md`
- `docs/research-design.md`
- `plan.md`
- `skills/technical-research/SKILL.md`
- `skills/technical-research/references/library-catalog.md`
- `skills/technical-research/references/library-workflow.md`
- `skills/technical-research/scripts/library.py`
- `templates/LOCAL-SETUP.md`
- `tests/test_library.py`
