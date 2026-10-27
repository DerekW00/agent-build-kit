# Agent Build Kit

Public, portable, project-local tooling for Claude Code and Codex. Python 3.9+ standard library.

- Publish only original generic skills and explicitly reviewed redistributable files. Never copy personal configuration, secrets, private inventories, employer prompts or local logs.
- No automatic dependency installation, authentication copying, broad permission grants, hooks, background agents, external sends or network actions in the installer.
- Installer defaults to dry run, refuses conflicts and preserves existing project instructions. No global installs.
- Keep setup small; one writer per journal; separate recorded decisions, AI suggestions, implementation and evidence. Assessment rules control use.
- Work on a feature branch from main. Do not push to main/master/prod or merge without explicit authorization.
- Checks: python3 -m unittest discover -s tests -v; python3 -m compileall -q kit.py; git diff --check. Exercise a complete install in a temporary project for both providers.
