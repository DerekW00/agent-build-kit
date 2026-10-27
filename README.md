# Agent Build Kit

A small, project-local workflow for **Claude Code and Codex**: scope a build, record consequential decisions, verify behavior, and resume longer sessions. It keeps evidence for a demo without turning the build into a documentation exercise.

Python 3.9+ is the only installer dependency. No package installation, credentials, model calls, global settings, hooks or background services are added. The same skill content is copied to each provider's documented project location.

## Set up in a few minutes

This initial kit is published on `feat/portable-kit` for review. Until that change merges, clone that branch:

```sh
git clone --branch feat/portable-kit https://github.com/DerekW00/agent-build-kit.git
cd agent-build-kit
python3 kit.py doctor
python3 kit.py install --project /absolute/path/to/your/project --provider both --profile build
```

The target must be an **existing project directory**. The last command only previews changes. Inspect the list, then apply:

```sh
python3 kit.py install --project /absolute/path/to/your/project --provider both --profile build --apply
```

Use `--provider claude` or `--provider codex` to install one provider. Use `--profile long-session` for checkpointing. Add `--with-instructions` only when you also want the starter `AGENTS.md` and `CLAUDE.md`; installation refuses if either exists. Existing project instructions are never merged or overwritten.

The installer refuses an existing skill destination or `.agent-kit/`. It does not upgrade a previous install. Review the manifest and preserve local edits before any manual replacement. [Installation details and boundaries](docs/installation.md).

## Use directly in Claude Code or Codex

Open the **target project**, then start a new session if skills are not discovered. Verify them in the host's skill list.

| Action | Claude Code | Codex |
| --- | --- | --- |
| Scope and implement a build | `/build-session` | `$build-session` |
| Capture design decisions | `/build-journal` | `$build-journal` |
| Check a change | `/verify-change` | `$verify-change` |
| Save or resume a checkpoint | `/session-handoff` | `$session-handoff` |

Example prompt in an AI-permitted session:

> Use build-session to implement the task below. Keep a brief build journal in notes/. Record consequential choices, credible alternatives, actual reasons and observed checks. Leave unknowns explicit. Verify the working slice before expanding. End with a reproducible demo and a short presentation outline linked to the notes. Task: …

For an existing build, invoke only the skill you need. For example, `/build-journal Capture the decisions from this session in notes/` in Claude Code, or `$build-journal …` in Codex. A one-time capture does not start background monitoring.

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
| `long-session` | Build profile plus session handoff | Multi-session work or provider switches |
| `manual` | Blank checklist and local setup record; no AI skills | Manual practice, only where imported materials are allowed |

For an assessment, permission to use AI **does not establish permission to import this kit**. Confirm personal-material rules separately. During a no-AI debugging round or no-internet/no-AI design phase, do not use an assistant. Even the manual template requires permission to bring personal materials. The manual profile is not an AI-disable switch; it does not remove existing skills or change your host's settings.

For short sessions, capture only decisions that affect correctness, interfaces, failure behavior or the demo. Record the credible options actually considered, not an invented exhaustive list. Keep human choices, delegated agent choices, suggestions, implementation and verification separate.

## Optional tools and verification

Use the supplied project's environment first. For your own Python projects, `uv`, `pytest` and Ruff are useful additions. MCP Inspector is optional when the task actually requires MCP. Full autonomous workflow bundles and background loops are excluded from the default kit. [Tool recommendations and sources](docs/tools.md) · [Selection rationale](docs/selection.md).

Run the kit checks:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q kit.py skills/build-journal/journal.py
git diff --check
```

[Observed verification and limitations](docs/verification.md) · [Provenance](PROVENANCE.md).
