# Local kit setup

This folder records a project-local installation. `installed.json` lists the version, profile, provider and SHA-256 hashes of installed files. Installation adds no permissions, credentials, hooks, integrations or background services. Existing global configuration can still affect provider behavior.

Open the target project in Claude Code or Codex. Start a new session after installation if skills do not appear. Check the available skill list before relying on an invocation.

| Purpose | Claude Code | Codex |
| --- | --- | --- |
| Plan and build | `/build-session` | `$build-session` |
| Capture decisions | `/build-journal` | `$build-journal` |
| Check the result | `/verify-change` | `$verify-change` |
| Save or resume a long session | `/session-handoff` | `$session-handoff` |

The build profile includes the first three. The long-session profile includes all four. The manual profile installs no AI skills. Native invocation requires a host version supporting the documented project skill paths. A plain chat without project-file access cannot install or maintain the files automatically.

Example request during an AI-permitted build:

“Use build-session for this task. Keep a brief build journal in notes/. Capture consequential options and actual reasons without inventing rationale. Verify each working slice. Finish with a reproducible demo and source-linked presentation notes.”

If automatic discovery fails, explicitly ask the host to read the intended `SKILL.md` in `.claude/skills/` or `.agents/skills/`. Direct reading is a fallback workflow, not proof that native discovery works.

Templates are optional. Importing this kit into an assessment requires the interviewer's permission independently of permission to use AI. No-AI phases require no AI assistance. Do not use the kit to bypass those rules.

To inspect an installation, compare files against the manifest and your project diff. The installer refuses repeat/conflicting installs and does not update existing files. To remove or update, review the manifest and current edits first; preserve your records and changed files. No automatic uninstall is provided.
