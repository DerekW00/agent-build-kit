# One-repository setup with your reading library

Agent Build Kit contains Build Journal, all seven skills, the complete reviewed PDF bibliography, and local research tools for **Claude Code and Codex**. Book bodies are not included. The catalog snapshot covers 262 visible PDFs, not 262 distinct books: ten chapter-based collections plus standalone books, papers and unidentified files. Eleven entries were empty when checked on October 29, 2026.

The public repository contains original instructions/tools and bibliographic metadata. Keep copyrighted PDFs, extracted chapters, private project notes and credentials outside it. The `.gitignore` excludes PDFs, EPUBs and `.local-context/`, but ignore rules do not remove already-tracked files or prevent a forced add. Sharing a bibliography does not grant redistribution rights to the books.

## 1. Install into a fresh project — about five minutes

Use the provided CLI and environment in an assessment. Import the kit or personal reading material only when the assessment permits it; permission to use AI alone does not settle that question. No-AI rounds remain no-AI.

These commands assume Python 3.9+, Git, and Claude Code or Codex are already available. The project directory must exist. Replace `/absolute/path/to/project` before running:

```sh
git clone https://github.com/DerekW00/agent-build-kit.git
cd agent-build-kit
python3 kit.py doctor
python3 kit.py install --project "/absolute/path/to/project" --provider both --profile long-session
```

The last command previews changes. After inspecting the list:

```sh
python3 kit.py install --project "/absolute/path/to/project" --provider both --profile long-session --apply
```

Choose `--provider claude` or `--provider codex` if only one host is available. `--profile long-session` includes the updated technical-research skill and its complete helper/catalog/workflow bundle. The smaller `build` profile does not include research. No new eighth skill or MCP service is required.

Open the **target project** in the coding assistant. Start a new session if needed. Check that technical-research resolves to `.claude/skills/technical-research/SKILL.md` or `.agents/skills/technical-research/SKILL.md`, respectively. A same-named personal/plugin skill can cause ambiguity. [Provider discovery and preservation rules](installation.md).

## 2. Make your books available — about five minutes

Keep the original library in its existing private location. On another laptop, obtain permitted copies through your own authorized source or an approved private transfer; preserve the folders if you want catalog paths to match. The public clone does **not** download or grant access to the books. Avoid copying your full personal configuration or account credentials to a borrowed machine.

Provide the local **real directory path** when requesting research. A fresh machine can use a different root; there is no hard-coded home directory or cloud account. If no books are available, the catalog is only a selection guide. Use accessible official documentation or the books' authorized source instead, and report the missing source access.

From the target project, confirm the actual files. The examples use the Codex copy; replace `.agents` with `.claude` for Claude Code:

```sh
python3 .agents/skills/technical-research/scripts/library.py scan --root "/absolute/path/to/Library"
python3 .agents/skills/technical-research/scripts/library.py find --root "/absolute/path/to/Library" --query "tool" --limit 5
```

This is filename search, not full-text or semantic search. Inspect the reported coverage and empty statuses. A nonempty file has not necessarily been validated as a readable PDF. The public [catalog](../skills/technical-research/references/library-catalog.md) is a snapshot; the scan describes this machine.

For PDF text, check `pdftotext -v`. If it is missing and installing tools is allowed, macOS users who already use Homebrew can install Poppler with `brew install poppler`; this is a separate optional system install. [Official package instructions and included binaries](https://formulae.brew.sh/formula/poppler.html). Otherwise use an available PDF viewer or ask the host to inspect the file. No package installation occurs through the kit.

```sh
python3 .agents/skills/technical-research/scripts/library.py extract --root "/absolute/path/to/Library" --file "relative/path/from-search.pdf" --first-page 1 --last-page 2
```

Use an actual relative path returned by search. Extraction needs a text-based PDF and requests at most five pages at once. Check errors and truncation. A requested page range is not proof that all those pages existed. The helper never writes the book or extracted text into your project; terminal output may still be retained by your assistant/session history.

## 3. Research, decide and validate — one question at a time

Paste this into Claude Code with `/technical-research`, or Codex with `$technical-research`:

> My library is at /absolute/path/to/Library. Read the current task and code, then research this decision: [question]. Use the bundled topic map and search to select one or two relevant chapters. Inspect the necessary pages. Cite the title, edition/draft status, chapter and actual PDF page indices. Separate source claims from your analysis. Compare credible options, recommend one for my constraints, and propose a test that could disprove it. Report missing/empty files and uninspected evidence. Keep the result short. Do not upload books or browse private project terms.

For example: “Can this job runner safely retry an external tool call after a timeout?” A useful answer connects failure uncertainty and deduplication to the actual API contract, then proposes a test where the side effect succeeds but the response is lost. A book alone cannot establish that the external service supports an idempotency key.

For design and implementation, continue only as needed:

- `/system-design` or `$system-design`: apply the source-backed constraints to a small design.
- `/build-journal` or `$build-journal`: record the real options, decision owner, reason, tradeoffs and evidence link.
- `/verify-change` or `$verify-change`: run checks against the actual implementation. Reading or model agreement is not a passing test.
- `/session-handoff` or `$session-handoff`: preserve current state and unresolved evidence for another session.

Use the [workflow and short context-note template](../skills/technical-research/references/library-workflow.md) if you want durable notes. Keep private context in an ignored local location and inspect `git status` before committing. Installed projects need their own ignore rules. Do not load the entire library into the prompt or add all book text to `AGENTS.md`/`CLAUDE.md`.

## Existing installs and troubleshooting

Updating the downloaded repository does not update project copies. Inside a clean kit checkout, run these commands separately and stop if one fails:

```sh
git fetch origin
git switch main
git pull --ff-only origin main
```

Do not discard local changes to make an update succeed. For a new project, use the fresh install above. For a project that already has version 0.1/0.2 skills, keep its notes and installed files intact. You can use the new helper directly from the downloaded repository:

```sh
python3 /absolute/path/to/agent-build-kit/skills/technical-research/scripts/library.py find --root "/absolute/path/to/Library" --query "Transactions"
```

Then explicitly ask either host to read `/absolute/path/to/agent-build-kit/skills/technical-research/SKILL.md` and its library workflow for this request. This is a direct-file fallback, not an automatic upgrade or native skill discovery claim. It requires host access to the checkout and selected books. If access is denied, use an allowed location or the host's normal access flow; do not disable permission controls.

The installer intentionally refuses existing destinations. Do not delete `.agent-kit/` or modified skills just to bypass that refusal. A manual upgrade requires reviewing the old manifest and preserving local edits first. An older base install without research can use the existing `design` add-on; a project that already has research must use the fallback or a reviewed manual update.

| Problem | Correct response |
| --- | --- |
| Public clone has no PDFs | Expected. Supply your authorized private source copies separately. |
| Search finds nothing | Try book/chapter terms from the catalog. Filename search is not content search. |
| Entry is empty | Restore a valid copy from your source; do not infer its contents. |
| `pdftotext` is unavailable | Use an existing viewer or install Poppler separately if permitted. |
| PDF produces no usable text | It may need a viewer/OCR; extraction here does not perform OCR. |
| Root has a symlink component | Supply the real library path instead of an alias. |
| Skill is old or missing | Check the selected path; use a new project install or explicit-file fallback. |
| Citations lack inspected pages | Reopen the source or mark the claim unverified. |

The helper performs no network operations. The assistant may send the selected text to its configured model provider, like other file context; local extraction does not mean local model inference. Assessment rules and source-use permissions still apply.
