# Local kit setup

This folder records a project-local installation. `installed.json` lists the version, profile, provider and SHA-256 hashes of installed files. Installation adds no permissions, credentials, hooks, integrations or background services. Existing global configuration can still affect provider behavior.

Open the target project in Claude Code or Codex. Start a new session after installation if skills do not appear. Check the available skill list before relying on an invocation.

| Purpose | Claude Code | Codex |
| --- | --- | --- |
| Plan and build | `/build-session` | `$build-session` |
| Capture decisions | `/build-journal` | `$build-journal` |
| Check the result | `/verify-change` | `$verify-change` |
| Save or resume a long session | `/session-handoff` | `$session-handoff` |
| Resolve a technical unknown | `/technical-research` | `$technical-research` |
| Design a small system | `/system-design` | `$system-design` |
| Challenge a proposed design | `/design-review` | `$design-review` |

The build profile includes the first three. The long-session profile includes all seven. The design profile includes only the last three and keeps its setup/manifest under `.agent-kit/design/`; it can be added to an existing base install. The manual profile installs no AI skills. Native invocation requires a host version supporting the documented project skill paths. A plain chat without project-file access cannot install or maintain the files automatically.

Example request during an AI-permitted build:

“Use build-session for this task. Keep a brief build journal in notes/. Capture consequential options and actual reasons without inventing rationale. Verify each working slice. Finish with a reproducible demo and source-linked presentation notes.”

If automatic discovery fails, explicitly ask the host to read the intended `SKILL.md` in `.claude/skills/` or `.agents/skills/`. Direct reading is a fallback workflow, not proof that native discovery works.

Templates are optional. Importing this kit into an assessment requires the interviewer's permission independently of permission to use AI. No-AI phases require no AI assistance. Do not use the kit to bypass those rules.

To inspect an installation, compare files against the manifest and your project diff. The installer refuses repeat/conflicting installs and does not update existing files. To remove or update, review the manifest and current edits first; preserve your records and changed files. No automatic uninstall is provided.

For a research/design sequence, invoke only the needed skills: research one blocking question with the project version and official sources; describe a compact mechanism; then request one review pass with concrete counterexamples. Save to named notes only when useful. No extra connector or model is required. Offline research must disclose source/freshness limits; AI remains prohibited during a no-AI phase.

For local books, technical-research includes `references/library-workflow.md`, `references/library-catalog.md` and `scripts/library.py` under its installed skill directory. Give the assistant your real library root and a specific engineering question. It should search titles, read selected pages, cite the inspected evidence, then connect it to a decision and test. The catalog is metadata; no books or private configuration are installed. Filename search needs only Python; PDF extraction optionally uses an existing `pdftotext`. Neither helper installs dependencies or makes network calls. Source access, source-use permissions and host model-provider behavior remain separate.

For the prepared corpus in Agent Build Kit 0.4, supply the downloaded checkout's `library/` path. Its `search.py` searches actual extracted text and returns source/page references. Keyword search needs only Python; semantic search uses an explicitly prepared local model. The installer leaves the larger corpus in the checkout, so keep that directory. No raw PDFs are required for searching the prepared text.
