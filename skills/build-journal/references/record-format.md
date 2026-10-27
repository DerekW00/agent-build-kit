# Record format

Use the bundled templates. The helper is a deliberately small parser, so keep these fields exact. Put nuance in the relevant prose section, not in a fixed field.

## Decision metadata

Each field occupies one physical line, before the first `##` section:

```text
Status: accepted
Recorded: 2026-10-26
Author: Human decision owner; AI drafting contribution; acceptance/delegation source
Provenance: retrospective
Supersedes: none
```

- `Status`: exactly `proposed`, `accepted` or `superseded`.
- `Recorded`: actual capture date as `YYYY-MM-DD`; do not invent the original event date.
- `Author`: free text on one line. Explain longer attribution in Evidence.
- `Provenance`: exactly `contemporaneous`, `retrospective` or `AI-suggested`. Explain fictional source, unknown event time, or other nuance in Context/Evidence. Do not append qualifiers to this field. A retrospective capture can include an AI suggestion; identify that suggestion in its row/prose without changing the capture value.
- `Supersedes`: `none` or an existing ID such as `D001`. A superseded record also needs `Superseded by: D002`, with reciprocal linkage in the replacement.

## Options and choice

Keep these column names. Use a single-letter identifier before the option name:

```markdown
| Option | State | Benefits | Costs and risks | Fit and rejection reason |
| --- | --- | --- | --- | --- |
| A: SQLite | chosen | Documented benefit | Unknown; TODO | Recorded reason |
| B: PostgreSQL | unexplored | Unverified AI suggestion | Not assessed | Not evaluated |
```

Option state is exactly `considered`, `chosen`, `rejected`, `deferred` or `unexplored`. Put “AI suggestion” in a descriptive cell or prose, never in the State value. The Choice section uses only the letter, not the label or explanation:

```text
Option: A
Implementation: planned
```

Implementation is exactly `planned`, `implemented`, `partially implemented`, `not implemented` or `unverified`. Explain the selection and uncertainty below these lines. For an open choice use `Option: TODO` and keep Status proposed. More than one option is not mandatory.

## Evidence and checks

Unknown reasons, costs and evidence remain visibly unknown; `TODO` is valid unfinished work. The helper reports these gaps with exit 1, which is expected during a build. Fix schema errors without turning unknowns into facts. Exit 0 means structurally complete, not implemented, true, tested or ready.

Keep required `##` headings from the templates. Process entries preserve the capture order; use the actual capture timestamp when available and label unknown source-event times. Never fabricate timing precision. Use `change` for a correction when using the helper's event kinds.
