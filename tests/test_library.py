import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/technical-research/scripts/library.py"
SPEC = importlib.util.spec_from_file_location("kit_library", SCRIPT)
library = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(library)


def sample_pdf():
    stream = b"BT /F1 12 Tf 72 720 Td (A synthetic library test.) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
               b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    data = b"%PDF-1.4\n"
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(data))
        data += str(number).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n"
    data += b"".join(("{:010d} 00000 n \n".format(offset)).encode() for offset in offsets[1:])
    return data + b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "Library with spaces"
        self.root.mkdir()

    def write(self, relative, content=b"unverified"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def cli(self, *arguments):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = library.main(list(arguments))
        return code, output.getvalue(), error.getvalue()

    def test_scan_reports_all_nonhidden_pdfs_and_sizes_without_readability_claim(self):
        self.write("Agents/2. Tools.PDF", b"not a real PDF")
        self.write("Empty.pdf", b"")
        self.write("中文/設計.pdf", b"content")
        self.write("ignore.txt")
        self.write(".hidden/private.pdf")
        result = library.scan(self.root)
        self.assertEqual(result["counts"], {"pdf_files": 3, "nonempty_unverified": 2, "empty": 1})
        self.assertFalse(result["content_verified"])
        self.assertEqual(result["entries"][0]["status"], "nonempty_unverified")
        self.assertEqual(result["entries"][0]["bytes"], 14)
        self.assertEqual(result["entries"][1]["status"], "empty")
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertEqual(result["coverage"]["skipped_hidden"], 1)

    def test_scan_does_not_follow_symlink_files_or_directories(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "secret.pdf").write_bytes(b"secret")
        (self.root / "outside").symlink_to(outside, target_is_directory=True)
        (self.root / "linked.pdf").symlink_to(outside / "secret.pdf")
        self.assertEqual(library.scan(self.root)["entries"], [])
        self.assertEqual(library.scan(self.root)["coverage"]["skipped_symlinks"], 2)

    def test_scan_reports_bounded_issues_and_exact_skip_counts(self):
        for index in range(25):
            (self.root / ("link{}.pdf".format(index))).symlink_to(self.base / "missing")
        result = library.scan(self.root)
        self.assertEqual(result["coverage"]["skipped_symlinks"], 25)
        self.assertEqual(len(result["issues"]), library.MAX_ISSUES)
        self.assertTrue(result["coverage"]["details_truncated"])

    def test_scan_reports_unreadable_directory_as_incomplete_and_cli_failure(self):
        original = Path.iterdir
        (self.root / "blocked").mkdir()
        self.write("usable.pdf")

        def iterdir(path):
            if path.name == "blocked":
                raise PermissionError("secret absolute path")
            return original(path)

        with mock.patch.object(Path, "iterdir", iterdir):
            code, output, _ = self.cli("scan", "--root", str(self.root))
        result = json.loads(output)
        self.assertEqual(code, 1)
        self.assertEqual(result["counts"]["pdf_files"], 1)
        self.assertEqual(result["coverage"]["errors"], 1)
        self.assertFalse(result["coverage"]["complete_for_regular_nonhidden_pdfs"])
        self.assertEqual(result["issues"], [{"path": "blocked", "reason": "directory_unreadable"}])

    def test_root_rejects_missing_file_symlink_and_symlink_ancestor(self):
        file_path = self.write("file.pdf")
        alias = self.base / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        (self.root / "subdir").mkdir()
        for value in (self.base / "missing", file_path, alias, alias / "subdir"):
            with self.subTest(value=value), self.assertRaises(library.LibraryError):
                library.library_root(value)
        self.assertEqual(library.library_root(self.root), self.root)

    def test_root_rejects_parent_traversal_before_normalization(self):
        with self.assertRaises(library.LibraryError):
            library.library_root(str(self.root) + "/../Library with spaces")

    def test_find_ranks_all_token_matches_first_then_title_and_is_deterministic(self):
        self.write("Agents/Design.pdf")
        self.write("Agent Design.pdf")
        self.write("Other/Design.pdf", b"")
        self.write("Zebra.pdf")
        result = library.find(self.root, "AGENT design", 2)
        self.assertEqual(result["match_count"], 3)
        self.assertEqual([item["path"] for item in result["matches"]],
                         ["Agent Design.pdf", "Agents/Design.pdf"])
        self.assertEqual(result["returned"], 2)
        self.assertEqual(result["search_scope"], library.SCOPE)
        self.assertEqual(library.find(self.root, "design", 8)["matches"][2]["status"], "empty")

    def test_find_does_not_search_content_and_empty_result_is_honest(self):
        self.write("book.pdf", b"special-secret-tool-token")
        result = library.find(self.root, "special-secret-tool-token", 8)
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["match_count"], 0)

    def test_find_rejects_empty_query_and_invalid_limit(self):
        for query, limit in (("...", 8), ("  ", 8), ("tool", 0), ("tool", 101)):
            with self.subTest(query=query, limit=limit), self.assertRaises(library.LibraryError):
                library.find(self.root, query, limit)

    def test_extract_rejects_unsafe_or_unavailable_paths_without_starting_process(self):
        self.write("empty.pdf", b"")
        self.write("other.txt")
        self.write(".hidden.pdf")
        (self.root / "folder.pdf").mkdir()
        (self.root / "link.pdf").symlink_to(self.root / "other.txt")
        (self.root / "linked").symlink_to(self.root, target_is_directory=True)
        bad = ["../escape.pdf", str(self.root / "empty.pdf"), "missing.pdf", "empty.pdf",
               "other.txt", ".hidden.pdf", "folder.pdf", "link.pdf", "linked/empty.pdf"]
        with mock.patch.object(library, "run_extractor") as runner:
            for value in bad:
                with self.subTest(value=value), self.assertRaises(library.LibraryError):
                    library.extract(self.root, value, 1, 1)
            runner.assert_not_called()

    def test_extract_rejects_bad_page_ranges(self):
        for first, last in ((0, 1), (2, 1), (1, 6), (-1, 2)):
            with self.subTest(first=first, last=last), self.assertRaises(library.LibraryError):
                library.extract(self.root, "unknown.pdf", first, last)

    def test_extract_missing_tool_has_actionable_error(self):
        self.write("book.pdf")
        with mock.patch.object(library.shutil, "which", return_value=None), \
                self.assertRaisesRegex(library.LibraryError, "pdftotext is missing"):
            library.extract(self.root, "book.pdf", 1, 1)

    def test_extract_preserves_argv_spaces_unicode_and_requested_not_verified_pages(self):
        self.write("文/Tool $(not-a-command).pdf")
        with mock.patch.object(library.shutil, "which", return_value="/tool/pdftotext"), \
                mock.patch.object(library, "run_extractor", return_value=(0, b"A page\f", False)) as runner:
            result = library.extract(self.root, "文/Tool $(not-a-command).pdf", 2, 4)
        self.assertEqual(runner.call_args.args[0][-2], str(self.root / "文/Tool $(not-a-command).pdf"))
        self.assertEqual(result["requested_pdf_pages"], {"first": 2, "last": 4})
        self.assertFalse(result["actual_page_numbers_verified"])
        self.assertTrue(result["content_is_untrusted"])
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_extract_caps_text_and_marks_no_text_separately(self):
        self.write("book.pdf")
        with mock.patch.object(library.shutil, "which", return_value="pdftotext"):
            with mock.patch.object(library, "run_extractor", return_value=(0, b"x" * 20000, False)):
                result = library.extract(self.root, "book.pdf", 1, 1)
                self.assertEqual(len(result["text"]), library.MAX_TEXT)
                self.assertTrue(result["truncated"])
            with mock.patch.object(library, "run_extractor", return_value=(0, b"\f\n", False)):
                result = library.extract(self.root, "book.pdf", 1, 1)
                self.assertIn("No text extracted", result["warning"])

    def test_extract_reports_malformed_timeout_and_spawn_failure(self):
        self.write("book.pdf")
        with mock.patch.object(library.shutil, "which", return_value="pdftotext"):
            with mock.patch.object(library, "run_extractor", return_value=(1, b"", False)), \
                    self.assertRaisesRegex(library.LibraryError, "malformed"):
                library.extract(self.root, "book.pdf", 1, 1)
            for failure, message in ((subprocess.TimeoutExpired("pdf", 20), "timed out"),
                                     (OSError("missing"), "could not start")):
                with mock.patch.object(library, "run_extractor", side_effect=failure), \
                        self.assertRaisesRegex(library.LibraryError, message):
                    library.extract(self.root, "book.pdf", 1, 1)

    def test_subprocess_output_buffer_is_bounded_and_timeout_kills_process(self):
        code, output, overflow = library.run_extractor(
            [sys.executable, "-c", "import sys; sys.stdout.write('x' * 100000)"])
        self.assertEqual(code, 0)
        self.assertEqual(len(output), library.MAX_TEXT * 4)
        self.assertTrue(overflow)
        with mock.patch.object(library, "TIMEOUT", 0.05), self.assertRaises(subprocess.TimeoutExpired):
            library.run_extractor([sys.executable, "-c", "import time; time.sleep(5)"])

    @unittest.skipUnless(shutil.which("pdftotext"), "optional pdftotext is not installed")
    def test_real_pdf_extraction_and_corrupt_pdf_failure(self):
        self.write("sample.pdf", sample_pdf())
        result = library.extract(self.root, "sample.pdf", 1, 1)
        self.assertIn("A synthetic library test.", result["text"])
        self.write("corrupt.pdf", b"not a PDF")
        with self.assertRaises(library.LibraryError):
            library.extract(self.root, "corrupt.pdf", 1, 1)

    def test_cli_missing_root_is_nonzero_without_traceback(self):
        code, output, error = self.cli("scan", "--root", str(self.base / "missing"))
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("root is missing", error)
        self.assertNotIn("Traceback", error)

    def test_both_provider_installs_keep_standalone_helper_after_source_removed(self):
        sys.path.insert(0, str(ROOT))
        self.addCleanup(sys.path.remove, str(ROOT))
        import kit
        source = self.base / "source"
        shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "*.pyc"))
        project = self.base / "project"
        project.mkdir()
        kit.apply_plan(kit.build_plan(project, "both", "long-session", source_root=source))
        shutil.rmtree(source)
        self.write("Book.pdf", b"demo")
        for provider in (".claude", ".agents"):
            helper = project / provider / "skills/technical-research/scripts/library.py"
            result = subprocess.run([sys.executable, str(helper), "find", "--root", str(self.root),
                                     "--query", "book"], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)["matches"][0]["path"], "Book.pdf")


if __name__ == "__main__":
    unittest.main()
