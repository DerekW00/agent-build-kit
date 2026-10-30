import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bundled_library_search", ROOT / "library/search.py")
search = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(search)


def write_npy(path, count, dimensions=384):
    header = str({"descr": "<f4", "fortran_order": False, "shape": (count, dimensions)})
    padding = (16 - (10 + len(header) + 1) % 16) % 16
    encoded = (header + " " * padding + "\n").encode("ascii")
    with path.open("wb") as stream:
        stream.write(b"\x93NUMPY\x01\x00" + struct.pack("<H", len(encoded)) + encoded)
        for row_id in range(count):
            vector = [0.0] * dimensions
            vector[row_id % 2] = 1.0
            stream.write(struct.pack("<" + "f" * dimensions, *vector))


class LibrarySearchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.patch = mock.patch.object(search, "DATA_DIR", self.folder)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.rows = [
            {"id": 0, "source": "Books/Distributed systems.pdf", "title": "Distributed Systems",
             "pdf_page": 6, "text": "A timeout leaves the operation outcome unknown. A retry may duplicate work."},
            {"id": 1, "source": "Books/AI evaluation.pdf", "title": "AI Evaluation",
             "pdf_page": 2, "text": "Measure the outcome of an evaluation. Include café cases."},
            {"id": 2, "source": "Books/Distributed systems.pdf", "title": "Distributed Systems",
             "pdf_page": 7, "text": "Retry retry retry with a stable key and a documented deduplication contract."},
        ]
        self.index = {
            "model": {"name": search.MODEL_NAME, "revision": search.MODEL_REVISION,
                      "dimensions": 384, "normalize_embeddings": True},
            "chunk_count": 3, "files": {},
        }
        write_npy(self.folder / "embeddings.npy", 3)
        self.write_rows()

    def write_rows(self):
        with gzip.open(self.folder / "chunks.jsonl.gz", "wt", encoding="utf-8") as stream:
            for row in self.rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.write_index()

    def write_index(self):
        for name in search.FILES:
            self.index["files"][name] = hashlib.sha256((self.folder / name).read_bytes()).hexdigest()
        (self.folder / "index.json").write_text(json.dumps(self.index), encoding="utf-8")

    def test_verify_without_numpy_checks_hashes_and_rows_but_discloses_vectors(self):
        with mock.patch.dict(sys.modules, {"numpy": None}):
            result = search.verify()
        self.assertEqual(result["chunk_count"], 3)
        self.assertEqual(result["status"], "partially verified")
        self.assertEqual(result["checksums"], "passed")
        self.assertIn("not validated", result["vector_structure"])

    def test_keyword_search_is_ranked_by_text_with_stable_ties_and_no_model(self):
        with mock.patch.object(search, "load_model", side_effect=AssertionError("model must not load")):
            result = search.query("RETRY!", limit=2)
            self.assertEqual([row["id"] for row in result["matches"]], [2, 0])
            self.assertEqual(search.query("distributed")["matches"], [])
            self.assertEqual(search.query("café")["matches"][0]["id"], 1)
        self.assertTrue(result["content_is_untrusted"])
        self.assertEqual(result["matches"][0]["pdf_page"], 7)

    def test_book_filter_and_no_matches(self):
        result = search.query("outcome", book="EVALUATION")
        self.assertEqual([row["id"] for row in result["matches"]], [1])
        self.assertEqual(search.query("outcome", book="missing")["returned"], 0)
        self.assertEqual(search.query("absentword")["returned"], 0)

    def test_bounded_snippet_and_read_keep_source_citation(self):
        self.rows[0]["text"] = "timeout " * 400
        self.write_rows()
        result = search.query("timeout")["matches"][0]
        self.assertEqual(len(result["text"]), 1500)
        self.assertTrue(result["truncated"])
        full = search.read_chunk(0)
        self.assertEqual(full["text"], self.rows[0]["text"])
        self.assertFalse(full["truncated"])
        self.assertEqual(full["pdf_page"], 6)
        self.assertEqual(full["source"], self.rows[0]["source"])

    def test_oversized_untrusted_chunk_read_is_bounded(self):
        self.rows[0]["text"] = "x" * 12001
        self.write_rows()
        result = search.read_chunk(0)
        self.assertEqual(len(result["text"]), 12000)
        self.assertTrue(result["truncated"])

    def test_empty_queries_invalid_limits_and_ids_fail(self):
        for question in ("", "  ", "!!!"):
            with self.subTest(question=question), self.assertRaises(search.LibraryError):
                search.query(question)
        for limit in (0, 21, -1, True):
            with self.subTest(limit=limit), self.assertRaises(search.LibraryError):
                search.query("retry", limit=limit)
        for chunk_id in (-1, 3, True):
            with self.subTest(chunk_id=chunk_id), self.assertRaises(search.LibraryError):
                search.read_chunk(chunk_id)

    def test_corrupted_file_hash_fails_before_search(self):
        with (self.folder / "embeddings.npy").open("ab") as stream:
            stream.write(b"corrupt")
        with self.assertRaisesRegex(search.LibraryError, "checksum mismatch"):
            search.query("retry")

    def test_invalid_or_incomplete_index_fails(self):
        for value in ([], {}, {"model": []}, {"model": self.index["model"], "chunk_count": True}):
            with self.subTest(index=value):
                (self.folder / "index.json").write_text(json.dumps(value))
                with self.assertRaises(search.LibraryError):
                    search.load_bundle()

    def test_wrong_pinned_model_fails(self):
        self.index["model"]["revision"] = "main"
        self.write_index()
        with self.assertRaisesRegex(search.LibraryError, "pinned model"):
            search.load_bundle()

    def test_row_count_and_order_must_match_index(self):
        self.index["chunk_count"] = 4
        self.write_index()
        with self.assertRaisesRegex(search.LibraryError, "chunk count"):
            search.load_bundle()
        self.index["chunk_count"] = 3
        self.rows[1]["id"] = 0
        self.write_rows()
        with self.assertRaisesRegex(search.LibraryError, "sequential"):
            search.load_bundle()

    def test_missing_fields_unsafe_paths_and_invalid_pages_fail(self):
        for field, value in (("source", "/absolute/book.pdf"), ("source", "../book.pdf"),
                             ("source", "Books\\book.pdf"), ("pdf_page", 0),
                             ("pdf_page", True), ("text", ""), ("title", None)):
            with self.subTest(field=field, value=value):
                original = self.rows[0][field]
                self.rows[0][field] = value
                self.write_rows()
                with self.assertRaises(search.LibraryError):
                    search.load_bundle()
                self.rows[0][field] = original

    def test_symlink_bundle_file_refused(self):
        real = self.folder / "real.npy"
        (self.folder / "embeddings.npy").rename(real)
        (self.folder / "embeddings.npy").symlink_to(real)
        with self.assertRaisesRegex(search.LibraryError, "regular file"):
            search.load_bundle()

    def test_malformed_gzip_and_json_fail_cleanly(self):
        (self.folder / "chunks.jsonl.gz").write_bytes(b"not gzip")
        self.write_index()
        with self.assertRaises(search.LibraryError):
            search.load_bundle()
        with gzip.open(self.folder / "chunks.jsonl.gz", "wt") as stream:
            stream.write("not json\n")
        self.write_index()
        with self.assertRaises(search.LibraryError):
            search.load_bundle()

    def test_offline_model_load_has_no_download_or_remote_code_fallback(self):
        constructor = mock.Mock(side_effect=OSError("model is not cached"))
        fake_module = types.SimpleNamespace(SentenceTransformer=constructor)
        with mock.patch.dict(sys.modules, {"sentence_transformers": fake_module}), \
                mock.patch.dict(search.os.environ, {}, clear=True):
            with self.assertRaisesRegex(search.LibraryError, "run prepare explicitly"):
                search.load_model(offline=True)
            self.assertEqual(search.os.environ["HF_HUB_OFFLINE"], "1")
            self.assertEqual(search.os.environ["TRANSFORMERS_OFFLINE"], "1")
            self.assertEqual(search.os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"], "1")
            self.assertEqual(search.os.environ["HF_HUB_DISABLE_TELEMETRY"], "1")
        constructor.assert_called_once_with(search.MODEL_NAME, revision=search.MODEL_REVISION,
                                            local_files_only=True, trust_remote_code=False, device="cpu")

    def test_prepare_loads_only_pinned_model_not_library_sources(self):
        constructor = mock.Mock(return_value=object())
        fake_module = types.SimpleNamespace(SentenceTransformer=constructor)
        with mock.patch.dict(sys.modules, {"sentence_transformers": fake_module}), \
                mock.patch.dict(search.os.environ, {}, clear=True), \
                mock.patch.object(search, "load_bundle", side_effect=AssertionError("must not read sources")):
            self.assertEqual(search.prepare()["status"], "model cached")
            self.assertEqual(search.os.environ["HF_HUB_OFFLINE"], "0")
        constructor.assert_called_once_with(search.MODEL_NAME, revision=search.MODEL_REVISION,
                                            local_files_only=False, trust_remote_code=False, device="cpu")

    def test_optional_semantic_ranking_and_structure_validation(self):
        try:
            import numpy
        except ImportError:
            self.skipTest("NumPy is optional")
        self.assertIn("passed", search.verify()["vector_structure"])
        model = mock.Mock()
        model.max_seq_length = 256
        model.tokenizer.encode.return_value = [1, 2, 3]
        query_vector = numpy.zeros(384, dtype=numpy.float32)
        query_vector[0] = 1.0
        model.encode.return_value = query_vector
        with mock.patch.object(search, "load_model", return_value=model) as loader:
            result = search.query("uncertain external operation", mode="semantic", limit=3)
            self.assertEqual([row["id"] for row in result["matches"]], [0, 2, 1])
            loader.assert_called_once_with(offline=True)
        write_npy(self.folder / "embeddings.npy", 2)
        self.write_index()
        with self.assertRaisesRegex(search.LibraryError, "one 384-dimensional row"):
            search.verify()

    def test_npz_archive_named_npy_with_matching_hash_fails_cleanly(self):
        try:
            import numpy
        except ImportError:
            self.skipTest("NumPy is optional")
        with (self.folder / "embeddings.npy").open("wb") as stream:
            numpy.savez(stream, vectors=numpy.zeros((3, 384), dtype=numpy.float32))
        self.write_index()
        archive = numpy.load(self.folder / "embeddings.npy", allow_pickle=False)
        with mock.patch.object(numpy, "load", return_value=archive), \
                mock.patch.object(archive, "close", wraps=archive.close) as close:
            with self.assertRaisesRegex(search.LibraryError, "one NPY array"):
                search.verify()
            close.assert_called_once_with()
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            status = search.main(["verify"])
        self.assertEqual(status, 2)
        self.assertIn("one NPY array", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_semantic_query_token_limit_prevents_silent_truncation(self):
        try:
            import numpy
        except ImportError:
            self.skipTest("NumPy is optional")
        model = mock.Mock()
        model.max_seq_length = 256
        model.tokenizer.encode.return_value = list(range(257))
        query_vector = numpy.zeros(384, dtype=numpy.float32)
        query_vector[0] = 1.0
        model.encode.return_value = query_vector
        with mock.patch.object(search, "load_model", return_value=model):
            with self.assertRaisesRegex(search.LibraryError, "limit of 256 tokens"):
                search.query("long question", mode="semantic")
            model.encode.assert_not_called()
            model.tokenizer.encode.assert_called_once_with(
                "long question", add_special_tokens=True, truncation=False)
            model.tokenizer.encode.return_value = list(range(256))
            self.assertEqual(search.query("boundary question", mode="semantic")["returned"], 3)
            model.encode.assert_called_once()

    def test_cli_errors_have_nonzero_exit_without_traceback(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            status = search.main(["query", "retry", "--limit", "0"])
        self.assertEqual(status, 2)
        self.assertIn("between 1 and 20", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())


if __name__ == "__main__":
    unittest.main()
