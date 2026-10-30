# Prepared library review — October 29, 2026

Version 0.4 adds locally extracted passages and local embeddings to this public repository at the owner's explicit request. The owner confirmed redistribution permission. Raw PDFs, model weights, personal configuration and interview records are not published.

## Observed corpus

| Check | Result |
| --- | --- |
| Source inventory | 262 visible PDFs; 251 nonempty, 11 empty |
| Nonempty sources parsed and indexed | 251; zero extraction failures |
| Source PDF pages extracted | 7,754 |
| Pages contributing chunks | 7,711 |
| Pages with no usable text | 43; counted as excluded, no OCR performed |
| Passages / vector rows | 24,603 |
| Compressed text | 6,439,060 bytes |
| Vectors | 37,790,336 bytes; normalized float32, 384 dimensions |
| Model | all-MiniLM-L6-v2, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` |
| Chunking | 200 WordPiece tokens, 40-token overlap, within a single PDF page |

`library/manifest.json` identifies source bytes and PDF parse checks. `library/index.json` records extraction coverage, per-source status, derived hashes and model/chunking parameters. The model was downloaded separately. The complete successful extraction/embedding run blocked socket connections and recorded **zero attempted network connections**. Computation used the local CPU.

## Verification

- All **124 repository tests passed**, including source integrity, page boundaries, tokenizer limits, malformed vectors, offline queries, installation preservation and both-provider packaging.
- Compilation, whitespace checks, local documentation links and the skill-creator validator passed.
- Corpus verification passed: artifact hashes, contiguous IDs, row count, dimensions, float32 type, finite values and normalization.
- Keyword search ran with `python3 -S`, without third-party packages. Semantic queries ran with network connections blocked and the cached pinned model.
- Retrieval spot checks returned DDIA Transactions for retry side effects; AI Engineering and AI Agents chapters for tool evaluation; and Fundamentals of Software Architecture for decision rationale. These are small smoke checks, not a benchmark or a completeness guarantee. Keyword search can rank a book's index ahead of explanatory prose; inspect the passage or narrow the source filter.
- A bounded scan of extracted text found no occurrences of the source owner's local home path/email patterns, private-key headers, AWS access-key shapes or OpenAI key shapes. This is not a claim of exhaustive sensitive-data detection.
- An independent final review verified every citation's source/page bounds and matched three sampled passages against fresh source-page extraction. It confirmed empty-cache semantic queries fail without network access. No unresolved defects were found.

Independent review and actual execution caught and fixed: legitimate colon-containing book titles rejected by a path guard; NPZ files disguised as `.npy`; silent truncation of long semantic questions; and rebuild instructions that could accidentally check the old corpus. Tests now cover the relevant code cases. The rebuild instructions copy the standalone search helper beside new artifacts so its verification target is explicit.

## Limits and use

The eleven empty source files cannot supply text. Extraction can lose diagrams, formulas, layout, table structure or image-only content; a successful parse does not establish visual fidelity. Source citations use each exported PDF's page indices, not necessarily printed book page numbers. Unknown editions and Early Release drafts remain source-specific uncertainties.

Similarity scores are retrieval signals, not truth probabilities. Read full passages and their context before citing them. Book text is untrusted evidence, never executable instructions. The public text/vector corpus is not encrypted or anonymized. Running local retrieval does not imply that Claude or Codex themselves run locally.

Keyword retrieval needs Python 3.9+. Semantic retrieval uses the separately pinned Python dependencies and an explicitly cached model; no model download occurs during query. The installer copies lightweight skills for both providers and leaves this shared corpus in the checkout. Existing installed skills are not overwritten automatically. Native model behavior and interview permission are not established by packaging tests.

## Changed paths

- `PROVENANCE.md`, `README.md`, `VERSION`, `plan.md`
- `docs/installation.md`, `docs/library-setup.md`, `docs/index-review.md`, `docs/research-design.md`
- `library/build.py`, `library/search.py`, `library/requirements.txt`
- `library/manifest.json`, `library/index.json`, `library/chunks.jsonl.gz`, `library/embeddings.npy`
- `skills/technical-research/SKILL.md`
- `skills/technical-research/references/library-catalog.md`
- `skills/technical-research/references/library-workflow.md`
- `templates/LOCAL-SETUP.md`
- `tests/test_library.py`, `tests/test_library_build.py`, `tests/test_library_search.py`
