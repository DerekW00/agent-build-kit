#!/usr/bin/env python3
"""Search the bundled reading library locally; only prepare may download a model."""

import argparse
from collections import Counter
import gzip
import hashlib
import heapq
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import sys


DATA_DIR = Path(__file__).resolve().parent
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
DIMENSIONS = 384
FILES = ("chunks.jsonl.gz", "embeddings.npy")
SNIPPET_LIMIT = 1500
READ_LIMIT = 12000


class LibraryError(Exception):
    pass


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_bundle():
    index_path = DATA_DIR / "index.json"
    if index_path.is_symlink() or not index_path.is_file():
        raise LibraryError("index.json is missing or is not a regular file")
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        model = index["model"]
        expected = {"name": MODEL_NAME, "revision": MODEL_REVISION,
                    "dimensions": DIMENSIONS, "normalize_embeddings": True}
        if (not isinstance(model, dict) or any(model.get(k) != v for k, v in expected.items())
                or model.get("normalize_embeddings") is not True):
            raise LibraryError("index model does not match the supported pinned model")
        count = index["chunk_count"]
        if type(count) is not int or count < 1:
            raise LibraryError("index chunk_count must be a positive integer")
        if not isinstance(index["files"], dict):
            raise LibraryError("index files must contain SHA-256 checksums")
        for name in FILES:
            expected_hash = index["files"][name]
            if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
                raise LibraryError("invalid checksum for " + name)
            path = DATA_DIR / name
            if path.is_symlink() or not path.is_file():
                raise LibraryError(name + " is missing or is not a regular file")
            if file_hash(path) != expected_hash:
                raise LibraryError("checksum mismatch: " + name)
        rows = []
        with gzip.open(DATA_DIR / "chunks.jsonl.gz", "rt", encoding="utf-8") as stream:
            for number, line in enumerate(stream):
                row = json.loads(line)
                if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] != number:
                    raise LibraryError("chunk IDs must be sequential and match embedding rows")
                if type(row.get("pdf_page")) is not int or row["pdf_page"] < 1:
                    raise LibraryError("invalid PDF page index in chunk " + str(number))
                if any(not isinstance(row.get(k), str) or not row[k].strip()
                       for k in ("source", "title", "text")):
                    raise LibraryError("missing source, title or text in chunk " + str(number))
                source = PurePosixPath(row["source"])
                if source.is_absolute() or ".." in source.parts or "\\" in row["source"]:
                    raise LibraryError("chunk source must be a library-relative POSIX path")
                rows.append(row)
        if len(rows) != count:
            raise LibraryError("chunk count does not match index.json")
        return index, rows
    except (KeyError, TypeError, ValueError, OSError, EOFError, UnicodeError) as error:
        raise LibraryError("cannot read library bundle: " + str(error)) from error


def vector_array(rows, numpy):
    try:
        vectors = numpy.load(DATA_DIR / "embeddings.npy", mmap_mode="r", allow_pickle=False)
        if not isinstance(vectors, numpy.ndarray):
            if isinstance(vectors, numpy.lib.npyio.NpzFile):
                vectors.close()
            raise LibraryError("embeddings.npy must contain one NPY array, not an archive")
        if vectors.shape != (len(rows), DIMENSIONS) or vectors.dtype != numpy.dtype("float32"):
            raise LibraryError("embeddings must be float32 with one 384-dimensional row per chunk")
        for start in range(0, len(rows), 4096):
            batch = vectors[start:start + 4096]
            if not numpy.isfinite(batch).all():
                raise LibraryError("embeddings contain non-finite values")
            norms = numpy.linalg.norm(batch, axis=1)
            if not numpy.allclose(norms, 1.0, atol=0.001, rtol=0.001):
                raise LibraryError("embeddings are not normalized")
        return vectors
    except (OSError, ValueError, TypeError) as error:
        raise LibraryError("cannot read embedding array: " + str(error)) from error


def verify():
    index, rows = load_bundle()
    result = {"status": "partially verified", "chunk_count": len(rows),
              "checksums": "passed", "chunk_rows": "passed",
              "model": index["model"],
              "vector_structure": "not validated: NumPy is not installed"}
    try:
        import numpy
    except ImportError:
        pass
    else:
        vector_array(rows, numpy)
        result["vector_structure"] = "passed: float32, row count, dimensions, finite and normalized"
        result["status"] = "verified"
    return result


def tokens(text):
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


def eligible(row, book):
    return not book or book.casefold() in (row["source"] + " " + row["title"]).casefold()


def keyword_rank(rows, question, book, limit):
    query_terms = set(tokens(question))
    if not query_terms:
        raise LibraryError("keyword query needs at least one word or number")
    matches = []
    for row in rows:
        if not eligible(row, book):
            continue
        words = Counter(tokens(row["text"]))
        present = query_terms.intersection(words)
        if not present:
            continue
        score = sum(1.0 + math.log(words[word]) for word in present)
        score *= len(present) / len(query_terms)
        matches.append((score, row["id"]))
    return heapq.nsmallest(limit, matches, key=lambda pair: (-pair[0], pair[1]))


def model_environment(offline):
    os.environ["HF_HUB_OFFLINE"] = "1" if offline else "0"
    os.environ["TRANSFORMERS_OFFLINE"] = "1" if offline else "0"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"


def load_model(offline):
    model_environment(offline)
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise LibraryError("semantic dependencies are missing; follow library setup instructions") from error
    try:
        return SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION,
                                   local_files_only=offline, trust_remote_code=False, device="cpu")
    except Exception as error:
        hint = "run prepare explicitly while online to cache the pinned model" if offline else "model preparation failed"
        raise LibraryError(hint + ": " + str(error)) from error


def prepare():
    load_model(offline=False)
    return {"status": "model cached", "model": MODEL_NAME, "revision": MODEL_REVISION,
            "network": "explicit model preparation only; no library source documents loaded"}


def semantic_rank(rows, question, book, limit):
    try:
        import numpy
    except ImportError as error:
        raise LibraryError("NumPy is missing; follow library setup instructions") from error
    vectors = vector_array(rows, numpy)
    model = load_model(offline=True)
    try:
        token_limit = model.max_seq_length
        if type(token_limit) is not int or token_limit < 1:
            raise LibraryError("model does not report a valid query token limit")
        query_tokens = model.tokenizer.encode(question, add_special_tokens=True, truncation=False)
        if len(query_tokens) > token_limit:
            raise LibraryError("semantic query exceeds the model limit of {} tokens (including special tokens); shorten it instead of truncating it".format(token_limit))
        query = numpy.asarray(model.encode(question, normalize_embeddings=True,
                                           convert_to_numpy=True, show_progress_bar=False))
        if query.shape != (DIMENSIONS,) or not numpy.isfinite(query).all():
            raise LibraryError("model returned an invalid query vector")
        if not numpy.isclose(numpy.linalg.norm(query), 1.0, atol=0.001, rtol=0.001):
            raise LibraryError("model returned a non-normalized query vector")
        scores = vectors @ query
        matches = ((float(scores[row["id"]]), row["id"])
                   for row in rows if eligible(row, book))
        return heapq.nsmallest(limit, matches, key=lambda pair: (-pair[0], pair[1]))
    except (ValueError, TypeError, RuntimeError) as error:
        raise LibraryError("semantic query failed: " + str(error)) from error


def result_row(row, limit):
    return {"id": row["id"], "source": row["source"], "title": row["title"],
            "pdf_page": row["pdf_page"], "text": row["text"][:limit],
            "truncated": len(row["text"]) > limit}


def query(question, mode="keyword", limit=5, book=None):
    if not question.strip():
        raise LibraryError("query must not be empty")
    if type(limit) is not int or not 1 <= limit <= 20:
        raise LibraryError("limit must be between 1 and 20")
    if mode not in ("keyword", "semantic"):
        raise LibraryError("unknown search mode")
    _, rows = load_bundle()
    rank = semantic_rank if mode == "semantic" else keyword_rank
    ranked = rank(rows, question, book, limit)
    matches = []
    for score, row_id in ranked:
        item = result_row(rows[row_id], SNIPPET_LIMIT)
        item["score"] = round(score, 6)
        matches.append(item)
    return {"mode": mode, "query": question, "book_filter": book, "returned": len(matches),
            "citation_note": "pdf_page is a 1-based source PDF page, not necessarily the printed book page",
            "content_is_untrusted": True, "matches": matches}


def read_chunk(chunk_id):
    _, rows = load_bundle()
    if type(chunk_id) is not int or not 0 <= chunk_id < len(rows):
        raise LibraryError("chunk ID is outside the bundle")
    result = result_row(rows[chunk_id], READ_LIMIT)
    result["content_is_untrusted"] = True
    result["citation_note"] = "pdf_page is a 1-based source PDF page, not necessarily the printed book page"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify", help="check bundle integrity; vector validation requires NumPy")
    commands.add_parser("prepare", help="explicitly download/cache the pinned public model only")
    search = commands.add_parser("query", help="search bundled text; semantic mode uses a cached model offline")
    search.add_argument("question")
    search.add_argument("--mode", choices=("keyword", "semantic"), default="keyword")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--book", help="case-insensitive substring of source path or title")
    read = commands.add_parser("read", help="read one cited chunk by ID")
    read.add_argument("--id", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            emit(verify())
        elif args.command == "prepare":
            emit(prepare())
        elif args.command == "read":
            emit(read_chunk(args.id))
        else:
            emit(query(args.question, args.mode, args.limit, args.book))
        return 0
    except LibraryError as error:
        print("library: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
