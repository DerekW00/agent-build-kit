import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("library_builder", ROOT / "library/build.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
try:
    import numpy as np
except ImportError:
    np = None


class Tokenizer:
    is_fast = True

    def __call__(self, text, **kwargs):
        return {"offset_mapping": [match.span() for match in re.finditer(r"\S+", text)]}

    def encode(self, text, **kwargs):
        return [1] * (len(re.findall(r"\S+", text)) + 2)


class Encoder:
    tokenizer = Tokenizer()

    def encode(self, texts, **kwargs):
        vectors = np.zeros((len(texts), builder.DIMENSIONS), dtype=np.float32)
        vectors[:, 0] = 1
        return vectors


class LibraryBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.source = self.base / "source"
        self.source.mkdir()
        self.output = self.base / "output"
        self.output.mkdir()
        self.manifest_path = self.base / "manifest.json"

    def entry(self, relative="book.pdf", data=b"synthetic", pages=2):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        result = {"path": relative, "bytes": len(data), "status": "available" if data else "source_empty"}
        if data:
            result.update(sha256=hashlib.sha256(data).hexdigest(), pdf_check={"status": "parseable", "pages": pages})
        return result

    def write_manifest(self, entries):
        manifest = {"schema_version": 1, "entries": entries}
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def test_chunks_preserve_original_text_offsets_and_exact_overlap(self):
        text = "\n".join("word{}".format(index) for index in range(450))
        chunks = builder.page_chunks(text, Tokenizer())
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0], "\n".join("word{}".format(index) for index in range(200)))
        self.assertEqual(chunks[1].split()[0], "word160")
        self.assertEqual(chunks[2].split()[0], "word320")
        self.assertEqual(chunks[-1].split()[-1], "word449")
        self.assertTrue(all(chunk in text for chunk in chunks))

    def test_chunks_preserve_unicode_and_blank_page_is_explicitly_empty(self):
        text = "繁體中文\tEnglish\nnaïve café"
        self.assertEqual(builder.page_chunks(text, Tokenizer()), [text])
        self.assertEqual(builder.page_chunks(" \n\t", Tokenizer()), [])

    def test_refuses_chunk_exceeding_model_limit(self):
        tokenizer = Tokenizer()
        tokenizer.encode = lambda *args, **kwargs: [1] * 257
        with self.assertRaisesRegex(builder.BuildError, "silent truncation"):
            builder.page_chunks("a page", tokenizer)

    def test_collect_keeps_page_indices_contiguous_chunk_ids_and_empty_source_count(self):
        manifest = self.write_manifest([self.entry("Book A.pdf", pages=3), self.entry("Empty.pdf", data=b"")])
        with mock.patch.object(builder, "extract_pdf", return_value=["first page", " \n", "第三頁"]):
            chunks, sources, coverage = builder.collect_chunks(self.source, manifest, Tokenizer(), "pdf")
        self.assertEqual([row["id"] for row in chunks], [0, 1])
        self.assertEqual([row["pdf_page"] for row in chunks], [1, 3])
        self.assertEqual([row["source"] for row in chunks], ["Book A.pdf", "Book A.pdf"])
        self.assertEqual(coverage["indexed_pages"], 2)
        self.assertEqual(coverage["excluded_pages"], 1)
        self.assertEqual(coverage["empty_text_pages"], 1)
        self.assertEqual(coverage["source_empty"], 1)
        self.assertEqual(sources[1]["status"], "source_empty")
        self.assertNotIn(str(self.source), json.dumps(sources))

    def test_collect_reports_no_text_without_inventing_ocr(self):
        manifest = self.write_manifest([self.entry(pages=2)])
        with mock.patch.object(builder, "extract_pdf", return_value=["", " \n"]):
            chunks, sources, coverage = builder.collect_chunks(self.source, manifest, Tokenizer(), "pdf")
        self.assertEqual(chunks, [])
        self.assertEqual(sources[0]["status"], "no_text")
        self.assertEqual(coverage["no_text"], 1)
        self.assertEqual(coverage["excluded_pages"], 2)

    def test_source_hash_mismatch_prevents_extraction_and_is_reported(self):
        manifest = self.write_manifest([self.entry()])
        (self.source / "book.pdf").write_bytes(b"different")
        with mock.patch.object(builder, "extract_pdf") as extract:
            chunks, sources, coverage = builder.collect_chunks(self.source, manifest, Tokenizer(), "pdf")
            extract.assert_not_called()
        self.assertEqual(chunks, [])
        self.assertEqual(coverage["failed"], 1)
        self.assertEqual(sources[0]["error"], "source_bytes_do_not_match_manifest")

    def test_failed_page_count_cannot_produce_false_page_citations(self):
        manifest = self.write_manifest([self.entry(pages=2)])
        with mock.patch.object(builder, "extract_pdf", return_value=["one page"]):
            chunks, sources, coverage = builder.collect_chunks(self.source, manifest, Tokenizer(), "pdf")
        self.assertEqual(chunks, [])
        self.assertEqual(coverage["failed"], 1)
        self.assertEqual(sources[0]["error"], "extracted_page_count_differs_from_manifest")
        self.assertEqual(coverage["excluded_pages"], 2)

    def test_failed_later_page_does_not_leave_partial_chunks_or_id_gaps(self):
        manifest = self.write_manifest([self.entry("bad.pdf", pages=2), self.entry("good.pdf", pages=1)])
        with mock.patch.object(builder, "extract_pdf", side_effect=[["good", "bad"], ["good again"]]), \
                mock.patch.object(builder, "page_chunks", side_effect=[["good"], builder.BuildError("bad page"), ["good again"]]):
            chunks, sources, coverage = builder.collect_chunks(self.source, manifest, Tokenizer(), "pdf")
        self.assertEqual(chunks[0]["id"], 0)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["source"], "good.pdf")
        self.assertEqual(coverage["failed"], 1)

    def test_manifest_rejects_unsafe_empty_paths_and_case_collisions(self):
        for path in ("../outside.pdf", "/absolute.pdf", "folder\\outside.pdf", ".hidden.pdf", "C:/file.pdf", "C:relative.pdf", "a/./x.pdf"):
            self.write_manifest([{"path": path, "bytes": 0, "status": "source_empty"}])
            with self.subTest(path=path), self.assertRaises(builder.BuildError):
                builder.read_manifest(self.manifest_path)
        self.write_manifest([self.entry("book.pdf"), self.entry("BOOK.pdf")])
        with self.assertRaisesRegex(builder.BuildError, "case-colliding"):
            builder.read_manifest(self.manifest_path)

    def test_colon_in_posix_title_is_valid_and_preserved(self):
        entry = self.entry("Observability/05 - How Code Crosses Over: Validating Intent.pdf", pages=1)
        manifest = self.write_manifest([entry])
        self.assertEqual(builder.read_manifest(self.manifest_path)["entries"][0]["path"], entry["path"])
        self.assertEqual(builder.source_path(self.source, entry["path"]), self.source / entry["path"])
        with mock.patch.object(builder, "extract_pdf", return_value=["valid chapter"]):
            chunks, sources, coverage = builder.collect_chunks(self.source, manifest, Tokenizer(), "pdf")
        self.assertEqual(coverage["failed"], 0)
        self.assertEqual(chunks[0]["source"], entry["path"])
        self.assertEqual(chunks[0]["title"], "05 - How Code Crosses Over: Validating Intent")

    def test_manifest_rejects_nonobject_top_level_with_build_error(self):
        for value in ([], None, "manifest"):
            self.manifest_path.write_text(json.dumps(value), encoding="utf-8")
            with self.subTest(value=value), self.assertRaisesRegex(builder.BuildError, "unsupported"):
                builder.read_manifest(self.manifest_path)

    def test_manifest_rejects_null_or_nonstring_hash_with_build_error(self):
        for value in (None, 123, [], {}):
            entry = self.entry()
            entry["sha256"] = value
            self.write_manifest([entry])
            with self.subTest(value=value), self.assertRaisesRegex(builder.BuildError, "SHA-256"):
                builder.read_manifest(self.manifest_path)

    def test_source_symlinks_and_symlink_ancestors_are_rejected(self):
        actual = self.entry()
        (self.source / "link.pdf").symlink_to(self.source / actual["path"])
        (self.source / "linked").symlink_to(self.source, target_is_directory=True)
        for path in ("link.pdf", "linked/book.pdf"):
            with self.subTest(path=path), self.assertRaisesRegex(builder.BuildError, "symlink"):
                builder.source_path(self.source, path)

    def test_extract_preserves_blank_page_positions_and_uses_no_shell(self):
        fake = mock.Mock()
        fake.stdout = io.BytesIO(b"first\f\fthird\f")
        fake.returncode = 0
        with mock.patch.object(builder.subprocess, "Popen", return_value=fake) as popen:
            result = builder.extract_pdf("pdftotext", self.source / "a $(command).pdf")
        self.assertEqual(result, ["first", "", "third"])
        self.assertIsInstance(popen.call_args.args[0], list)
        self.assertNotIn("shell", popen.call_args.kwargs)

    def test_extract_timeout_kills_process_and_output_cap_is_not_silent(self):
        fake = mock.Mock()
        fake.stdout = io.BytesIO(b"page\f")
        fake.wait.side_effect = [subprocess.TimeoutExpired("pdf", 60), None]
        with mock.patch.object(builder.subprocess, "Popen", return_value=fake), \
                self.assertRaisesRegex(builder.BuildError, "timeout"):
            builder.extract_pdf("pdf", self.source / "book.pdf")
        fake.kill.assert_called_once()
        fake = mock.Mock()
        fake.stdout = io.BytesIO(b"too much text\f")
        fake.returncode = 0
        with mock.patch.object(builder.subprocess, "Popen", return_value=fake), \
                mock.patch.object(builder, "MAX_EXTRACT_BYTES", 3), \
                self.assertRaisesRegex(builder.BuildError, "limit"):
            builder.extract_pdf("pdf", self.source / "book.pdf")

    def test_existing_artifact_is_refused_before_loading_model(self):
        (self.output / "index.json").write_text("preserve", encoding="utf-8")
        with mock.patch.object(builder, "load_model") as load, self.assertRaisesRegex(builder.BuildError, "exists"):
            builder.build(self.source, self.output, self.manifest_path)
        load.assert_not_called()
        self.assertEqual((self.output / "index.json").read_text(), "preserve")

    @unittest.skipIf(np is None, "NumPy is optional for the source/installer test suite")
    def test_build_writes_valid_normalized_artifacts_with_hashes_and_no_pdf_copy(self):
        self.write_manifest([self.entry()])
        with mock.patch.object(builder.shutil, "which", return_value="pdf"), \
                mock.patch.object(builder, "extract_pdf", return_value=["page one", "page two"]), \
                contextlib.redirect_stderr(io.StringIO()):
            index = builder.build(self.source, self.output, self.manifest_path, model=Encoder())
        self.assertEqual(index["chunk_count"], 2)
        self.assertEqual(set(path.name for path in self.output.iterdir()), set(builder.ARTIFACTS))
        vectors = np.load(self.output / "embeddings.npy", allow_pickle=False)
        self.assertEqual(vectors.dtype, np.float32)
        self.assertEqual(vectors.shape, (2, 384))
        with gzip.open(self.output / "chunks.jsonl.gz", "rt", encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle]
        self.assertEqual([row["pdf_page"] for row in rows], [1, 2])
        for name, digest in index["files"].items():
            self.assertEqual(builder.sha256(self.output / name), digest)
        self.assertNotIn(str(self.source), json.dumps(index))

    @unittest.skipIf(np is None, "NumPy is optional for the source/installer test suite")
    def test_failed_encoder_preserves_existing_artifacts_when_replacing(self):
        self.write_manifest([self.entry()])
        for name in builder.ARTIFACTS:
            (self.output / name).write_bytes(b"old")
        bad = Encoder()
        bad.encode = lambda *args, **kwargs: np.zeros((2, 384), dtype=np.float32)
        with mock.patch.object(builder.shutil, "which", return_value="pdf"), \
                mock.patch.object(builder, "extract_pdf", return_value=["one", "two"]), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(builder.BuildError, "normalized"):
            builder.build(self.source, self.output, self.manifest_path, replace=True, model=bad)
        self.assertTrue(all((self.output / name).read_bytes() == b"old" for name in builder.ARTIFACTS))


if __name__ == "__main__":
    unittest.main()
