# Installation and provider behavior

## What gets copied

- Claude Code: `.claude/skills/<name>/`.
- Codex: `.agents/skills/<name>/`.
- Both: `.agent-kit/SETUP.md`, `.agent-kit/MANUAL.md`, and a manifest with file hashes.
- Long session: `.agent-kit/SESSION.template.md`.
- Optional instructions: new `AGENTS.md` plus `CLAUDE.md` importing it.

Every Build Journal copy includes its helper, templates and references. It works after the kit checkout is removed. The installer uses ordinary files rather than symlinks, so another laptop does not need this checkout at the same path.

The manifest records file integrity at installation, not authenticity or future correctness. It excludes its own hash. The installer does not modify `.gitignore`; decide which project notes/configurations should be tracked after reviewing their contents. Nothing is committed or pushed automatically.

## Discovery

Both hosts document project skills with `SKILL.md`. The common files use only `name` and `description` frontmatter. Provider-specific hooks, tool names, model choices and permissions are deliberately absent. Common Markdown does not make the providers' runtime behavior identical.

- [Claude Code skills](https://code.claude.com/docs/en/skills): invoke `/skill-name`. A user-level skill with the same name may override a project skill. Inspect the loaded path if behavior is unexpected.
- [Codex skills](https://learn.chatgpt.com/docs/build-skills): invoke `$skill-name` or use the skill list. Duplicate names can cause ambiguity; select the project copy.
- [Agent Skills format](https://agentskills.io/specification): the shared file format, not a permission or portability guarantee.

Open the target project and restart the session if discovery misses newly installed folders. Check the selected skill's path. As a fallback, explicitly ask the host to read the desired project `SKILL.md`; this is direct instruction use, not proof of native discovery.

Global settings, managed policy, plugins and inherited instructions can still affect the session. This kit neither disables them nor copies them to another machine. Use the interviewer's provided model/CLI and permissions during an assessment; do not replace them with your personal setup without permission.

## Preservation and limits

Installation is a dry run unless `--apply` is given. All conflicts are checked before writing. Existing skill directories, `.agent-kit/`, and optional instruction files are refused. Managed child symlinks and symlink project leaves are refused; an explicitly supplied parent alias can resolve to its real directory.

On an ordinary write failure, the installer attempts to remove only files/directories it created. It preserves pre-existing paths and reports rollback problems. It is a single-writer local utility, not a hardened installer for a hostile filesystem changing concurrently. Do not run two installers against the same project.

`doctor` runs bounded `--version` checks for tools already on PATH. It does not check authentication, model availability, network policy, package caches or project behavior. Running a tool's version command relies on trusting that installed executable; the kit does not inspect its implementation.

No automatic upgrades or uninstall are provided. Before a manual update, read `.agent-kit/installed.json`, inspect the project diff and preserve modified skills/notes. Re-run the relevant checks after any update.
