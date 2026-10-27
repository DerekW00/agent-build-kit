import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "skills" / "build-journal" / "journal.py"
BUILD_HEADINGS = (
    "Goal", "Constraints", "Success criteria", "Design and request trace",
    "Scope and cuts", "Verification", "Current state",
)
DECISION = """# D001 — Store local notes

Status: accepted
Recorded: 2026-10-26
Provenance: contemporaneous
Supersedes: none
Author: Synthetic test author

## Context and constraints

The local example needs editable records and no server.

## Options

| Option | State | Benefits | Costs and risks | Fit and rejection reason |
| --- | --- | --- | --- | --- |
| A: Markdown | chosen | Human readable | Limited querying | Fits a local editable journal |
| B: Database | rejected | Structured queries | More setup | Rejected because this example needs no query service |

## Choice

Option: A
Implementation: planned

## Rationale

Markdown meets the recorded constraint with less setup.

## Consequences

The author must keep stable headings. This is a recorded risk.

## Evidence

Author reports inspecting the example by hand. No project tests were run.

## Revisit when

Revisit if the journal needs queries across many projects.
"""


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="build-journal-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name).resolve()
        self.root = self.folder / "a journal with spaces"

    def run_cli(self, *args, input_text=None, expected=0, cwd=None, cli=CLI):
        result = subprocess.run(
            [sys.executable, str(cli)] + [str(arg) for arg in args],
            input=input_text, capture_output=True, text=True,
            cwd=str(cwd or self.folder), timeout=10,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def initialize(self):
        self.run_cli("init", self.root, "--title", "Local example")

    def complete_journal(self, decision=DECISION):
        self.initialize()
        build = "# Local example\n\n" + "\n\n".join(
            "## {}\n\n{}".format(name, "A bounded, author-recorded example." if name != "Verification"
                                    else "No project tests run. Verification remains planned.")
            for name in BUILD_HEADINGS
        ) + "\n"
        (self.root / "BUILD.md").write_text(build, encoding="utf-8")
        path = self.root / "decisions" / "D001-store-notes.md"
        path.write_text(decision, encoding="utf-8")
        return path

    def test_end_to_end_from_unrelated_working_directory(self):
        decision = self.complete_journal()
        self.run_cli("log", self.root, "--kind", "experiment", "--text", "Plan: run an example later.")
        self.run_cli("log", self.root, "--kind", "result", "--text", "-",
                     input_text="Author reports: a manual example looked correct.\n")
        result = self.run_cli("check", self.root)
        self.assertIn("No structural gaps found", result.stdout)
        self.assertIn("Claims are unverified", result.stdout)
        self.run_cli("present", self.root)
        presentation = (self.root / "PRESENTATION.md").read_text(encoding="utf-8")
        self.assertIn("not independent verification", presentation)
        self.assertIn("Implementation: planned", presentation)
        self.assertIn("No project tests were run", presentation)
        self.assertIn("Plan: run an example later.", presentation)
        self.assertIn("Author reports: a manual example looked correct.", presentation)
        self.assertIn("B: Database", presentation)
        self.assertIn("Rejected because", presentation)
        self.assertIn("source retains the full history", presentation)
        self.assertIn(decision.name, presentation)
        self.assertNotIn("tests passed", presentation)

    def test_init_creates_only_contract_files_and_rejects_repeat(self):
        self.initialize()
        self.assertEqual({path.name for path in self.root.iterdir()}, {"BUILD.md", "PROCESS.md", "decisions"})
        before = (self.root / "BUILD.md").read_bytes()
        self.run_cli("init", self.root, "--title", "Replacement", expected=2)
        self.assertEqual((self.root / "BUILD.md").read_bytes(), before)

    def test_init_accepts_empty_directory_and_preserves_nonempty_directory(self):
        self.root.mkdir()
        marker = self.root / "manual.txt"
        marker.write_text("keep me", encoding="utf-8")
        self.run_cli("init", self.root, "--title", "Example", expected=2)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep me")
        self.assertEqual(list(self.root.iterdir()), [marker])
        marker.unlink()
        self.initialize()

    def test_decision_numbers_existing_files_without_clobbering(self):
        self.initialize()
        self.run_cli("decision", self.root, "Choose a local format")
        first = self.root / "decisions" / "D001-choose-a-local-format.md"
        first.write_text(first.read_text(encoding="utf-8") + "\nHandwritten note: preserve this.\n", encoding="utf-8")
        before = first.read_bytes()
        (self.root / "decisions" / "D019-existing.md").write_text("manual record", encoding="utf-8")
        self.run_cli("decision", self.root, "Choose a local format")
        self.assertTrue((self.root / "decisions" / "D020-choose-a-local-format.md").is_file())
        self.assertEqual(first.read_bytes(), before)
        self.run_cli("decision", self.root, "Choose a local format")
        self.assertTrue((self.root / "decisions" / "D021-choose-a-local-format.md").is_file())

    def test_titles_cannot_escape_decisions_directory(self):
        self.initialize()
        self.run_cli("decision", self.root, "../../outside / odd \\ path")
        paths = list((self.root / "decisions").iterdir())
        self.assertEqual(len(paths), 1)
        self.assertRegex(paths[0].name, r"^D001-[a-z0-9-]+\.md$")
        self.assertFalse((self.folder / "outside").exists())
        self.run_cli("decision", self.root, "\n\t", expected=2)
        self.run_cli("decision", self.root, "Line\n## New heading", expected=2)
        self.assertEqual(len(list((self.root / "decisions").iterdir())), 1)

    def test_log_appends_preserves_manual_content_and_never_executes(self):
        self.initialize()
        path = self.root / "PROCESS.md"
        initial = "# Process log\n\nManual notes without a final newline"
        path.write_text(initial, encoding="utf-8")
        command = "touch {}".format(self.folder / "do-not-execute")
        self.run_cli("log", self.root, "--kind", "experiment", "--text", command)
        after = path.read_text(encoding="utf-8")
        self.assertTrue(after.startswith(initial + "\n\n"))
        self.assertRegex(after, r"## \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z — experiment")
        self.assertIn(command, after)
        self.assertFalse((self.folder / "do-not-execute").exists())
        self.run_cli("log", self.root, "--kind", "observation", "--text", "-", input_text="\n  \n", expected=2)
        self.assertEqual(path.read_text(encoding="utf-8"), after)
        self.run_cli("log", self.root, "--kind", "invalid", "--text", "text", expected=2)

    def test_check_placeholders_proposed_and_runtime_exit_codes(self):
        self.run_cli("check", self.root, expected=2)
        self.initialize()
        self.run_cli("decision", self.root, "An open decision")
        result = self.run_cli("check", self.root, expected=1)
        self.assertIn("BUILD.md:", result.stdout)
        self.assertIn("unresolved placeholder", result.stdout)
        self.assertIn("proposed decision is incomplete", result.stdout)
        self.assertIn("Completeness does not establish correctness", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_complete_proposed_decision_is_still_flagged_open(self):
        self.complete_journal(DECISION.replace("Status: accepted", "Status: proposed"))
        result = self.run_cli("check", self.root, expected=1)
        self.assertIn("choice remains open", result.stdout)

    def test_unknown_chosen_option_and_contradictory_rows(self):
        path = self.complete_journal(DECISION.replace("Option: A\n", "Option: C\n"))
        result = self.run_cli("check", self.root, expected=1)
        self.assertIn("chosen option is absent", result.stdout)
        path.write_text(DECISION.replace("| B: Database | rejected |", "| B: Database | chosen |"), encoding="utf-8")
        result = self.run_cli("check", self.root, expected=1)
        self.assertIn("chosen table rows contradict Choice", result.stdout)

    def test_duplicate_headings_metadata_and_malformed_values(self):
        malformed = DECISION.replace("Status: accepted", "Status: accepted\nStatus: invented")
        malformed = malformed.replace("Recorded: 2026-10-26", "Recorded: yesterday")
        malformed = malformed.replace("Author: Synthetic test author", "Author: Synthetic test author\nAuthor: Another author")
        malformed = malformed.replace("Provenance: contemporaneous", "Provenance: guessed")
        malformed += "\n## Evidence\n\nA contradictory second evidence section.\n"
        path = self.complete_journal(malformed)
        result = self.run_cli("check", self.root, expected=1)
        for expected in ("duplicate section: Evidence", "duplicate metadata: Status", "duplicate metadata: Author", "valid YYYY-MM-DD", "unsupported provenance"):
            self.assertIn(expected, result.stdout)
        path.write_text(DECISION.replace("## Evidence", "##Evidence"), encoding="utf-8")
        result = self.run_cli("check", self.root, expected=1)
        self.assertIn("missing section: Evidence", result.stdout)
        self.assertIn("malformed Markdown heading", result.stdout)

    def test_decision_requires_nonempty_author_metadata(self):
        path = self.complete_journal()
        for author_line in ("", "Author: "):
            with self.subTest(author_line=author_line):
                path.write_text(DECISION.replace("Author: Synthetic test author", author_line), encoding="utf-8")
                result = self.run_cli("check", self.root, expected=1)
                self.assertIn("missing or empty metadata: Author", result.stdout)

    def test_required_sections_and_option_table_failures(self):
        path = self.complete_journal()
        cases = [
            (DECISION.replace("Status: accepted", "Status: unknown"), "unsupported decision status"),
            (DECISION.replace("Costs and risks", "Costs"), "five contract table columns"),
            (DECISION.replace("| B: Database | rejected |", "| A: Database | rejected |"), "duplicate option ID"),
            (DECISION.replace("| B: Database | rejected |", "| B: Database | invented |"), "unsupported option state"),
            (DECISION.replace("Implementation: planned", "Implementation: shipped"), "supported implementation state"),
            (DECISION.replace("## Revisit when", "## Something else"), "missing section: Revisit when"),
            (DECISION.replace("More setup | Rejected because this example needs no query service", "More setup | "), "fit/rejection reason"),
        ]
        for content, warning in cases:
            with self.subTest(warning=warning):
                path.write_text(content, encoding="utf-8")
                result = self.run_cli("check", self.root, expected=1)
                self.assertIn(warning, result.stdout)

    def test_single_viable_option_allowed_with_recorded_constraint(self):
        content = "\n".join(line for line in DECISION.splitlines() if not line.startswith("| B:")) + "\n"
        content = content.replace("Markdown meets the recorded constraint with less setup.",
                                  "The required plain-text-only output rules out a database, leaving one viable option.")
        self.complete_journal(content)
        self.run_cli("check", self.root)

    def test_superseded_requires_forward_link_to_existing_decision(self):
        path = self.complete_journal(DECISION.replace("Status: accepted", "Status: superseded"))
        result = self.run_cli("check", self.root, expected=1)
        self.assertIn("needs Superseded by", result.stdout)
        path.write_text(path.read_text(encoding="utf-8").replace("Supersedes: none", "Supersedes: none\nSuperseded by: D002"), encoding="utf-8")
        result = self.run_cli("check", self.root, expected=1)
        self.assertIn("reference an existing decision", result.stdout)
        replacement = self.root / "decisions" / "D002-replacement.md"
        replacement.write_text(DECISION.replace("# D001", "# D002").replace("Supersedes: none", "Supersedes: D001"), encoding="utf-8")
        self.run_cli("check", self.root)

    def test_supersession_requires_consistent_status_and_reciprocal_links(self):
        path = self.complete_journal()
        replacement = self.root / "decisions" / "D002-replacement.md"
        replacement.write_text(DECISION.replace("# D001", "# D002").replace("Supersedes: none", "Supersedes: D001"), encoding="utf-8")
        result = self.run_cli("check", self.root, expected=1)
        self.assertIn("older decision to be superseded and link back", result.stdout)
        path.write_text(DECISION.replace("Status: accepted", "Status: superseded").replace("Supersedes: none", "Supersedes: none\nSuperseded by: D002"), encoding="utf-8")
        replacement.write_text(DECISION.replace("# D001", "# D002"), encoding="utf-8")
        result = self.run_cli("check", self.root, expected=1)
        self.assertIn("link back with Supersedes", result.stdout)
        replacement.write_text(DECISION.replace("# D001", "# D002").replace("Status: accepted", "Status: proposed").replace("Supersedes: none", "Supersedes: D001"), encoding="utf-8")
        result = self.run_cli("check", self.root, expected=1)
        self.assertIn("replacement must be accepted or superseded", result.stdout)

    def test_supersession_cycle_is_flagged(self):
        first = DECISION.replace("Status: accepted", "Status: superseded").replace("Supersedes: none", "Supersedes: D002\nSuperseded by: D002")
        self.complete_journal(first)
        second = first.replace("# D001", "# D002").replace("Supersedes: D002", "Supersedes: D001").replace("Superseded by: D002", "Superseded by: D001")
        (self.root / "decisions" / "D002-cycle.md").write_text(second, encoding="utf-8")
        result = self.run_cli("check", self.root, expected=1)
        self.assertIn("supersession linkage contains a cycle", result.stdout)

    def test_current_build_references_to_superseded_decisions_need_reconciliation(self):
        old = DECISION.replace("Status: accepted", "Status: superseded")
        old = old.replace("Supersedes: none", "Supersedes: none\nSuperseded by: D003")
        self.complete_journal(old)
        replacement = DECISION.replace("# D001", "# D003").replace("Supersedes: none", "Supersedes: D001")
        (self.root / "decisions" / "D003-replacement.md").write_text(replacement, encoding="utf-8")
        path = self.root / "BUILD.md"
        original = path.read_text(encoding="utf-8")
        for name in ("Design and request trace", "Current state"):
            with self.subTest(section=name):
                current = original.replace(
                    "## {}\n\nA bounded, author-recorded example.".format(name),
                    "## {}\n\nCurrent storage choice: [D001](decisions/D001-store-notes.md).".format(name),
                )
                path.write_text(current, encoding="utf-8")
                result = self.run_cli("check", self.root, expected=1)
                self.assertIn("{} references superseded decision D001".format(name), result.stdout)
                self.assertIn("replacement: D003", result.stdout)
                path.write_text(current.replace("[D001](decisions/D001-store-notes.md)",
                                                "[D003](decisions/D003-replacement.md)"), encoding="utf-8")
                self.run_cli("check", self.root)

    def test_fenced_headings_do_not_drop_evidence_or_process_caveats(self):
        evidence = "Recorded output follows.\n\n```markdown\n## expected report\n### detail\n```\n\nCaveat: this was planned, not run.\n\n~~~text\n## second heading\n~~~\n\nFinal evidence caveat."
        self.complete_journal(DECISION.replace("Author reports inspecting the example by hand. No project tests were run.", evidence))
        process = "Plan only.\n\n```markdown\n" + "\n".join("## sample {}".format(index) for index in range(10)) + "\n```\n\nProcess caveat remains."
        self.run_cli("log", self.root, "--kind", "experiment", "--text", process)
        self.run_cli("check", self.root)
        self.run_cli("present", self.root)
        text = (self.root / "PRESENTATION.md").read_text(encoding="utf-8")
        for expected in ("Caveat: this was planned, not run.", "Final evidence caveat.", "Plan only.", "## sample 0", "Process caveat remains."):
            self.assertIn(expected, text)

    def test_repeated_process_timestamp_and_kind_are_valid_history(self):
        self.complete_journal()
        (self.root / "PROCESS.md").write_text(
            "# Process log\n\n## 2026-10-26T12:00:00Z — observation\n\nFirst recorded fact.\n\n"
            "## 2026-10-26T12:00:00Z — observation\n\nSecond recorded fact.\n", encoding="utf-8")
        self.run_cli("check", self.root)
        self.run_cli("present", self.root)
        text = (self.root / "PRESENTATION.md").read_text(encoding="utf-8")
        self.assertIn("First recorded fact.", text)
        self.assertIn("Second recorded fact.", text)

    def test_presentation_preserves_full_process_history_in_order(self):
        self.complete_journal()
        entries = [
            ("result", "The first check failed: duplicate records were returned."),
            ("change", "Correction: preserve unique records before returning the result."),
        ] + [("observation", "Later recorded event {}.".format(index)) for index in range(1, 11)]
        for kind, content in entries:
            self.run_cli("log", self.root, "--kind", kind, "--text", content)
        before = (self.root / "PROCESS.md").read_bytes()
        self.run_cli("check", self.root)
        self.run_cli("present", self.root)
        text = (self.root / "PRESENTATION.md").read_text(encoding="utf-8")
        positions = [text.index(content) for _, content in entries]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("uncurated review draft", text)
        self.assertIn("Process history (author supplied; not independently verified)", text)
        self.assertIn("The full process source is quoted in its original order", text)
        self.assertEqual((self.root / "PROCESS.md").read_bytes(), before)

    def test_presentation_preserves_build_and_decision_authorship(self):
        self.complete_journal(DECISION.replace("Author: Synthetic test author",
                                              "Author: Synthetic human decision owner\n  Synthetic AI wrapped drafting contribution."))
        build = self.root / "BUILD.md"
        build.write_text(build.read_text(encoding="utf-8").replace(
            "# Local example\n", "# Local example\n\nAuthor: Synthetic human with AI assistance\n"), encoding="utf-8")
        second = DECISION.replace("# D001", "# D002").replace(
            "Author: Synthetic test author", "Author: Synthetic AI drafting contribution, reviewed by human")
        (self.root / "decisions" / "D002-another-decision.md").write_text(second, encoding="utf-8")
        self.run_cli("check", self.root)
        self.run_cli("present", self.root)
        text = (self.root / "PRESENTATION.md").read_text(encoding="utf-8")
        for author in ("Synthetic human with AI assistance", "Synthetic human decision owner",
                       "Synthetic AI drafting contribution, reviewed by human"):
            self.assertIn("> Author: " + author, text)
        for metadata in ("Status: accepted", "Recorded: 2026-10-26", "Provenance: contemporaneous",
                         "  Synthetic AI wrapped drafting contribution."):
            self.assertIn("> " + metadata, text)

    def test_presentation_preserves_source_preambles_and_rebases_links(self):
        decision = DECISION.replace("Status: accepted", (
            "This fictional decision was reconstructed later; see [build context](../BUILD.md#goal).\n\n"
            "Status: accepted"))
        self.complete_journal(decision)
        build = self.root / "BUILD.md"
        build.write_text(build.read_text(encoding="utf-8").replace("# Local example\n", (
            "# Local example\n\nRecorded: 2026-10-25\nAuthor: Synthetic example author\nProvenance: retrospective\n\n"
            "This fictional account reports no observed execution.\n\n```markdown\n## Illustrative heading\n```\n\n"
            "The caveat continues after the code sample; see [process context](PROCESS.md#process-log).\n")), encoding="utf-8")
        (self.root / "PROCESS.md").write_text(
            "# Process log\n\nRetrospective teaching timeline; all reported results are fictional.\n\n"
            "See [build source](BUILD.md#goal).\n", encoding="utf-8")
        self.run_cli("log", self.root, "--kind", "result", "--text", "A fictional failed result.")
        output = self.folder / "review.md"
        self.run_cli("present", self.root, "--output", output)
        text = output.read_text(encoding="utf-8")
        for expected in (
            "> Recorded: 2026-10-25", "> Author: Synthetic example author", "> Provenance: retrospective",
            "> This fictional account reports no observed execution.", "> ## Illustrative heading",
            "> The caveat continues after the code sample", "> This fictional decision was reconstructed later",
            "> Retrospective teaching timeline; all reported results are fictional.", "> A fictional failed result.",
            "[process context](a%20journal%20with%20spaces/PROCESS.md#process-log)",
            "[build context](a%20journal%20with%20spaces/BUILD.md#goal)",
            "[build source](a%20journal%20with%20spaces/BUILD.md#goal)",
        ):
            self.assertIn(expected, text)
        self.assertLess(text.index("Retrospective teaching timeline"), text.index("A fictional failed result."))

    def test_presentation_preserves_process_text_without_event_headers(self):
        self.complete_journal()
        (self.root / "PROCESS.md").write_text(
            "# Process log\n\nNo observed execution; only a retrospective author note exists.\n", encoding="utf-8")
        self.run_cli("present", self.root)
        text = (self.root / "PRESENTATION.md").read_text(encoding="utf-8")
        self.assertIn("> No observed execution; only a retrospective author note exists.", text)

    def test_presentation_rebases_relative_links_but_preserves_code_and_web_links(self):
        evidence = (
            '[project](../BUILD.md#goal) and [process](<../PROCESS.md> "recorded history").\n'
            '[web](https://example.com/spec) and [same record](#context-and-constraints).\n'
            '[reference]: ../BUILD.md "source"\n'
            '`[literal](../BUILD.md)` and ``[also literal](../PROCESS.md)``.\n'
            '```markdown\n[fenced](../BUILD.md)\n```'
        )
        self.complete_journal(DECISION.replace("Author reports inspecting the example by hand. No project tests were run.", evidence))
        self.run_cli("present", self.root)
        text = (self.root / "PRESENTATION.md").read_text(encoding="utf-8")
        for expected in ('[project](BUILD.md#goal)', '[process](<PROCESS.md> "recorded history")',
                         '[web](https://example.com/spec)', '[same record](decisions/D001-store-notes.md#context-and-constraints)',
                         '[reference]: BUILD.md "source"', '`[literal](../BUILD.md)`',
                         '``[also literal](../PROCESS.md)``', '[fenced](../BUILD.md)'):
            self.assertIn(expected, text)
        external = self.folder / "external.md"
        self.run_cli("present", self.root, "--output", external)
        self.assertIn('[project](a%20journal%20with%20spaces/BUILD.md#goal)', external.read_text(encoding="utf-8"))

    def test_presentation_never_overwrites_and_is_deterministic(self):
        self.complete_journal()
        self.run_cli("present", self.root)
        first = self.root / "PRESENTATION.md"
        before = first.read_bytes()
        second = self.root / "PRESENTATION-2.md"
        self.run_cli("present", self.root, "--output", second)
        self.assertEqual(second.read_bytes(), before)
        first.write_text("Edited by hand. Preserve this.\n", encoding="utf-8")
        self.run_cli("present", self.root, expected=2)
        self.run_cli("present", self.root, "--output", self.root / "BUILD.md", expected=2)
        self.assertEqual(first.read_text(encoding="utf-8"), "Edited by hand. Preserve this.\n")

    def test_relative_output_is_relative_to_working_directory(self):
        self.complete_journal()
        output = self.folder / "external notes with spaces.md"
        self.run_cli("present", self.root, "--output", output.name)
        self.assertTrue(output.is_file())
        self.assertFalse((self.root / output.name).exists())
        self.assertIn("a%20journal%20with%20spaces/BUILD.md", output.read_text(encoding="utf-8"))

    def test_presentation_quotes_unverified_author_test_assertion(self):
        content = DECISION.replace("Author reports inspecting the example by hand. No project tests were run.",
                                   "Author says: pytest passed. This is an unverified historical claim.")
        self.complete_journal(content)
        self.run_cli("present", self.root)
        text = (self.root / "PRESENTATION.md").read_text(encoding="utf-8")
        self.assertIn("Evidence (author supplied; not independently verified)", text)
        self.assertIn("> Author says: pytest passed. This is an unverified historical claim.", text)
        self.assertIn("> Implementation: planned", text)

    def test_missing_journal_files_and_invalid_utf8_are_runtime_errors(self):
        self.initialize()
        (self.root / "BUILD.md").unlink()
        self.run_cli("decision", self.root, "No journal", expected=2)
        self.run_cli("log", self.root, "--kind", "next", "--text", "no", expected=2)
        self.run_cli("present", self.root, expected=2)
        (self.root / "BUILD.md").write_bytes(b"\xff")
        self.run_cli("check", self.root, expected=2)

    def test_symlink_journal_is_rejected_and_explicit_parent_is_resolved(self):
        self.initialize()
        alias = self.folder / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        self.run_cli("log", alias, "--kind", "next", "--text", "no", expected=2)
        self.run_cli("init", alias, "--title", "No", expected=2)
        self.run_cli("init", alias / "new-journal", "--title", "Explicit child")
        self.assertTrue((self.root / "new-journal" / "BUILD.md").is_file())

    def test_symlink_records_and_decisions_cannot_redirect_writes(self):
        self.initialize()
        outside = self.folder / "outside.md"
        outside.write_text("preserve", encoding="utf-8")
        process = self.root / "PROCESS.md"
        process.unlink()
        process.symlink_to(outside)
        self.run_cli("log", self.root, "--kind", "result", "--text", "bad", expected=2)
        self.assertEqual(outside.read_text(encoding="utf-8"), "preserve")
        process.unlink()
        process.write_text("# Process log\n", encoding="utf-8")
        decisions = self.root / "decisions"
        decisions.rmdir()
        decisions.symlink_to(self.folder, target_is_directory=True)
        self.run_cli("decision", self.root, "Bad", expected=2)
        self.assertEqual(list(self.folder.glob("D*.md")), [])

    def test_symlink_decision_and_presentation_paths_are_rejected(self):
        self.complete_journal()
        outside = self.folder / "outside.md"
        outside.write_text("preserve", encoding="utf-8")
        alias = self.root / "decisions" / "D002-alias.md"
        alias.symlink_to(outside)
        self.run_cli("check", self.root, expected=2)
        self.run_cli("decision", self.root, "No", expected=2)
        alias.unlink()
        output = self.root / "PRESENTATION.md"
        output.symlink_to(outside)
        self.run_cli("present", self.root, expected=2)
        output.unlink()
        directory_alias = self.root / "outside-alias"
        directory_alias.symlink_to(self.folder, target_is_directory=True)
        self.run_cli("present", self.root, "--output", directory_alias / "escaped.md", expected=2)
        self.assertFalse((self.folder / "escaped.md").exists())
        self.assertEqual(outside.read_text(encoding="utf-8"), "preserve")




if __name__ == "__main__":
    unittest.main()
