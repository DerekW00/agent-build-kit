# Useful tools and primary sources

Reviewed October 26, 2026. Nothing in this document is installed automatically. Prefer the environment already supplied by the project or interviewer. Introduce tools during practice, then rehearse from a fresh directory.

## Python environment and checks

**uv** can keep Python and dependencies reproducible through `pyproject.toml`, `.python-version` and `uv.lock`. Use the [official installation instructions](https://docs.astral.sh/uv/getting-started/installation/) for the machine. Review the installer before running it; this kit does not fetch or execute it.

For a new personal Python project that does not already have dependency management:

```sh
uv init --bare
uv add --dev pytest ruff
uv lock
uv sync --locked
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
```

These commands create or change project files and resolve dependencies over the network. Inspect and commit the resulting project files through your normal workflow. Do not run them in a supplied exercise merely to replace its existing setup. A lockfile does not provide an installed Python or cached packages; rehearse offline on the actual machine if offline use matters. [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/).

**pytest** is useful for a required behavior, an invalid input and a meaningful failure path. Use deterministic fake clients or [`monkeypatch`](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) to isolate most tests from external services. Then separately identify any real model/API integration check. Fake tests do not establish real-provider integration.

**Ruff** provides a quick lint and formatting gate. It does not prove behavior or full type correctness. Keep rules narrow in an existing project. [Ruff documentation](https://docs.astral.sh/ruff/) · [formatter](https://docs.astral.sh/ruff/formatter/).

## Longer sessions

Use a checkpoint linked to decision records and actual test evidence. Resume by reading the files and checking current state, not by trusting a previous agent's completion claim. [Anthropic's long-running-agent research](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents) supports incremental work, progress artifacts and verification across sessions.

Use [Git worktrees](https://git-scm.com/docs/git-worktree) only if parallel tasks benefit from isolated branches. They add coordination cost. For a short build, a single working tree and one writer are often enough.

[Superpowers](https://github.com/obra/superpowers) offers broader engineering workflows. Its [verification skill](https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md?plain=1) is a useful reference. The full bundle imposes more process than this kit's short-session default, so it is not included. If adopting it for ongoing work, review its workflow and permissions first. A read-only upstream check observed `v7.0.1` at `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b`; pin and review an exact version rather than silently following main. [Upstream MIT license](https://github.com/obra/superpowers/blob/main/LICENSE).

## MCP only when required

[MCP Inspector](https://modelcontextprotocol.io/docs/2026-07-28/tools/inspector) can inspect tool schemas and invoke tools without relying on an LLM's judgment. Current documentation requires Node 22.19.0 or newer. It adds another runtime, so it is outside the base kit. Use a reviewed, pinned package version for an actual MCP task; no version is installed or validated by this kit. [Upstream repository and license status](https://github.com/modelcontextprotocol/inspector).

A normal backend or agent API exercise does not need MCP merely because it uses tools. Add it only when interoperability through MCP is a requirement.
