# Agent Build Kit

A small, project-local workflow for **Claude Code and Codex**: scope a build, research a blocking question, design and review the mechanism, record consequential decisions, verify behavior, and resume longer sessions. It keeps evidence for a demo without turning the build into a documentation exercise.

**Build Journal is included in this repository**: its Claude/Codex skill, Python helper, decision templates and references. You only need to download Agent Build Kit.

**A searchable reading library is included too**: locally extracted passages, precomputed embeddings, keyword/semantic search, source/page references and a complete bibliography. No raw PDFs are uploaded. [Set up the included library on this or another laptop](docs/library-setup.md). Keyword search works with Python alone; semantic search uses an optional local model.

Python 3.9+ is the only installer dependency. No package installation, credentials, model calls, global settings, hooks or background services are added. The same skill content is copied to each provider's documented project location.

## One-repository setup, including Build Journal

Clone the repository's default branch, `main`:

```sh
git clone https://github.com/DerekW00/agent-build-kit.git
cd agent-build-kit
python3 kit.py doctor
python3 kit.py install --project /absolute/path/to/your/project --provider both --profile long-session
```

The target must be an **existing project directory**. The last command only previews changes. Inspect the list, then apply:

```sh
python3 kit.py install --project /absolute/path/to/your/project --provider both --profile long-session --apply
```

This `long-session` setup installs all seven skills, including Build Journal, for both providers. Use `--provider claude` or `--provider codex` to install one provider. Use `--profile build` for the smaller three-skill setup, which also includes Build Journal. Add `--with-instructions` only when you also want the starter `AGENTS.md` and `CLAUDE.md`; installation refuses if either exists. Existing project instructions are never merged or overwritten.

Base profiles refuse an existing skill destination or `.agent-kit/`. The `design` add-on uses separate metadata and can extend an existing base kit. Neither path overwrites existing files or upgrades old skills. [Installation details and boundaries](docs/installation.md).

### Add research and design to an existing kit

In your kit checkout, switch to `main`, update it, then preview the add-on. If switching or updating fails because of local changes or divergent commits, resolve those first; do not discard them:

```sh
git fetch origin
git switch main
git pull --ff-only origin main
python3 kit.py install --project /absolute/path/to/your/project --provider both --profile design
```

If the preview is correct, apply it:

```sh
python3 kit.py install --project /absolute/path/to/your/project --provider both --profile design --apply
```

This adds only `technical-research`, `system-design` and `design-review`, plus setup records under `.agent-kit/design/`. It preserves your existing base manifest, skills, notes and instructions. Do not add `--with-instructions` to an existing instructed project. A conflicting skill name or previous design add-on is refused, not overwritten.

For a **new project needing all seven skills**, install `--profile long-session` directly. A design-only install does not include the original four skills. Base profiles will refuse an already-existing `.agent-kit/`, so use the full profile up front or install a base profile before adding `design`.

## Use directly in Claude Code or Codex

Open the **target project**, then start a new session if skills are not discovered. Verify them in the host's skill list.

| Action | Claude Code | Codex |
| --- | --- | --- |
| Scope and implement a build | `/build-session` | `$build-session` |
| Capture design decisions | `/build-journal` | `$build-journal` |
| Check a change | `/verify-change` | `$verify-change` |
| Save or resume a checkpoint | `/session-handoff` | `$session-handoff` |
| Resolve a technical unknown | `/technical-research` | `$technical-research` |
| Design a small system | `/system-design` | `$system-design` |
| Challenge a proposed design | `/design-review` | `$design-review` |

See [research and design usage](docs/research-design.md) for copyable prompts, outputs and selection rules.

For the prepared library, use `/technical-research` or `$technical-research` with the downloaded kit's `library/` path and one engineering question. The updated skill selects relevant chapters, reads the needed pages, compares options and proposes a check. It reports missing sources and citation gaps. [Book workflow and topic map](skills/technical-research/references/library-workflow.md) · [Full bibliography](skills/technical-research/references/library-catalog.md).

Example prompt in an AI-permitted session:

> Use build-session to implement the task below. Keep a brief build journal in notes/. Record consequential choices, credible alternatives, actual reasons and observed checks. Leave unknowns explicit. Verify the working slice before expanding. End with a reproducible demo and a short presentation outline linked to the notes. Task: …

For an existing build, invoke only the skill you need. For example, `/build-journal Capture the decisions from this session in notes/` in Claude Code, or `$build-journal …` in Codex. A one-time capture does not start background monitoring.

### Bundled Build Journal

The complete bundle is in `skills/build-journal/`. Installation copies its helper, templates and references together. After installation, the journal copy remains usable without the downloaded checkout. Keep the checkout if you use its separate `library/` search corpus.

In an AI-permitted session, ask `/build-journal` in Claude Code or `$build-journal` in Codex to keep notes in `notes/`. It records:

- `BUILD.md`: goal, constraints, design and verification state.
- `PROCESS.md`: experiments, failures, corrections and next steps.
- `decisions/D###-name.md`: considered options, choice, reasons and tradeoffs.

The installed journal helper also works without a model:

```sh
# Claude install; use .agents/skills for a Codex install.
python3 .claude/skills/build-journal/journal.py init notes --title "My build"
python3 .claude/skills/build-journal/journal.py check notes
python3 .claude/skills/build-journal/journal.py present notes
```

Fill the Markdown records before expecting the checker to pass. `present` produces a detailed evidence packet, not a finished short speech. Structural checks cannot establish that the recorded reasoning or results are true.

These instructions are for **Claude Code and Codex with project-file access**. Pasting a repository link into an ordinary chat does not install skills or give access to your working files. [Discovery and fallback details](docs/installation.md).

## Choose the smallest profile

| Profile | Contents | Use |
| --- | --- | --- |
| `build` | Build session, build journal, verify change | A short AI-permitted build |
| `long-session` | All seven skills, including Build Journal | One-repository setup for a fresh project |
| `design` | Technical research, system design, design review | Standalone design work or an add-on to an existing base kit |
| `manual` | Blank checklist and local setup record; no AI skills | Manual practice, only where imported materials are allowed |

For an assessment, permission to use AI **does not establish permission to import this kit**. Confirm personal-material rules separately. During a no-AI debugging round or no-internet/no-AI design phase, do not use an assistant. Even the manual template requires permission to bring personal materials. The manual profile is not an AI-disable switch; it does not remove existing skills or change your host's settings.

For short sessions, capture only decisions that affect correctness, interfaces, failure behavior or the demo. Record the credible options actually considered, not an invented exhaustive list. Keep human choices, delegated agent choices, suggestions, implementation and verification separate.

## Optional tools and verification

Use the supplied project's environment first. For your own Python projects, `uv`, `pytest` and Ruff are useful additions. MCP Inspector is optional when the task actually requires MCP. Full autonomous workflow bundles and background loops are excluded from the default kit. [Tool recommendations and sources](docs/tools.md) · [Selection rationale](docs/selection.md).

Run the kit checks:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q kit.py skills/build-journal/journal.py skills/technical-research/scripts/library.py
git diff --check
```

[Observed verification and limitations](docs/verification.md) · [Library extension review](docs/library-review.md) · [Prepared index review](docs/index-review.md) · [Provenance](PROVENANCE.md).
