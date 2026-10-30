#!/usr/bin/env python3
"""Build a page-aware local text/vector index from the reviewed PDF source manifest."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
DIMENSIONS = 384
CHUNK_TOKENS = 200
OVERLAP_TOKENS = 40
MAX_SEQUENCE_LENGTH = 256
EXTRACT_TIMEOUT = 60
MAX_EXTRACT_BYTES = 64 * 1024 * 1024
ARTIFACTS = ("chunks.jsonl.gz", "embeddings.npy", "index.json")


class BuildError(Exception):
    pass


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def real_directory(value, create=False):
    path = Path(value).expanduser()
    if ".." in path.parts:
        raise BuildError("directory paths must not contain '..'")
    path = path.absolute()
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            if create:
                current.mkdir()
                mode = current.lstat().st_mode
            else:
                raise BuildError("source directory is missing")
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise BuildError("directories and their ancestors must be real directories, not symlinks")
    return path


def relative_source(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise BuildError("manifest source must be a relative POSIX PDF path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or re.match(r"^[A-Za-z]:", value) or any(part in ("", ".", "..") or part.startswith(".")
                                                     for part in value.split("/")):
        raise BuildError("unsafe source path in manifest")
    if relative.suffix.casefold() != ".pdf":
        raise BuildError("manifest sources must be PDFs")
    return relative


def source_path(root, value):
    relative = relative_source(value)
    current = root
    for part in relative.parts:
        current = current / part
        mode = current.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise BuildError("source or source ancestor is a symlink")
    if not stat.S_ISREG(mode) or current.suffix.casefold() != ".pdf":
        raise BuildError("source is not a regular PDF")
    return current


def read_manifest(path):
    if path.is_symlink() or not path.is_file():
        raise BuildError("manifest must be a regular local JSON file")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or not isinstance(manifest.get("entries"), list):
        raise BuildError("unsupported source manifest")
    seen = set()
    for item in manifest["entries"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise BuildError("invalid manifest entry")
        relative_source(item["path"])
        key = item["path"].casefold()
        if key in seen:
            raise BuildError("duplicate or case-colliding source paths")
        seen.add(key)
        if type(item.get("bytes")) is not int or item["bytes"] < 0:
            raise BuildError("invalid source byte size")
        if item.get("status") == "source_empty":
            if item["bytes"] != 0:
                raise BuildError("source_empty entry must have zero bytes")
        elif item.get("status") == "available":
            digest = item.get("sha256")
            if item["bytes"] < 1 or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise BuildError("available source requires a positive size and SHA-256")
        else:
            raise BuildError("unknown source status")
        if "pdf_check" in item and not isinstance(item["pdf_check"], dict):
            raise BuildError("pdf_check must be an object when present")
    return manifest


def extract_pdf(executable, path):
    content = bytearray()
    overflow = [False]
    process = subprocess.Popen([executable, "-layout", "-enc", "UTF-8", str(path), "-"],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def drain():
        while True:
            block = process.stdout.read(65536)
            if not block:
                break
            remaining = MAX_EXTRACT_BYTES - len(content)
            content.extend(block[:remaining])
            overflow[0] = overflow[0] or len(block) > remaining

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        process.wait(timeout=EXTRACT_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise BuildError("pdftotext_timeout")
    finally:
        reader.join(timeout=2)
        if not reader.is_alive():
            process.stdout.close()
    if reader.is_alive():
        raise BuildError("pdftotext_output_did_not_finish")
    if process.returncode:
        raise BuildError("pdftotext_failed_exit_{}".format(process.returncode))
    if overflow[0]:
        raise BuildError("pdftotext_output_exceeds_64_MiB_limit")
    text = bytes(content).decode("utf-8", errors="strict")
    pages = text.split("\f")
    if pages and pages[-1] == "":
        pages.pop()
    return pages


def page_chunks(text, tokenizer):
    if not text.strip():
        return []
    encoded = tokenizer(text, add_special_tokens=False, truncation=False,
                        return_offsets_mapping=True, verbose=False)
    offsets = encoded["offset_mapping"]
    result = []
    start = 0
    while start < len(offsets):
        end = min(start + CHUNK_TOKENS, len(offsets))
        chunk = text[offsets[start][0]:offsets[end - 1][1]]
        token_count = len(tokenizer.encode(chunk, add_special_tokens=True, truncation=False))
        if token_count > MAX_SEQUENCE_LENGTH:
            raise BuildError("chunk would exceed model token limit; refusing silent truncation")
        if chunk.strip():
            result.append(chunk)
        if end == len(offsets):
            break
        start = end - OVERLAP_TOKENS
    return result


def load_model():
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    import torch
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(4)
    model = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION, device="cpu",
                                local_files_only=True, trust_remote_code=False)
    if model.get_sentence_embedding_dimension() != DIMENSIONS or model.max_seq_length < MAX_SEQUENCE_LENGTH:
        raise BuildError("cached model dimensions or token limit differ from the pinned contract")
    if not model.tokenizer.is_fast:
        raise BuildError("the cached model needs its fast tokenizer for original text offsets")
    return model


def collect_chunks(root, manifest, tokenizer, executable):
    chunks, sources = [], []
    coverage = {"pdf_entries": len(manifest["entries"]), "available": 0, "source_empty": 0,
                "parsed": 0, "failed": 0, "no_text": 0, "total_pdf_pages": 0,
                "extracted_pages": 0, "indexed_pages": 0, "excluded_pages": 0,
                "empty_text_pages": 0, "page_count_unknown_sources": 0}
    for position, item in enumerate(manifest["entries"], 1):
        source = item["path"]
        expected_pages = item.get("pdf_check", {}).get("pages")
        if type(expected_pages) is not int or expected_pages < 1:
            expected_pages = None
        record = {"source": source, "status": item["status"], "pages": expected_pages,
                  "text_pages": 0, "chunks": 0}
        if item["status"] == "source_empty":
            coverage["source_empty"] += 1
            record["pages"] = 0
            sources.append(record)
            continue
        coverage["available"] += 1
        if expected_pages is None:
            coverage["page_count_unknown_sources"] += 1
        else:
            coverage["total_pdf_pages"] += expected_pages
        try:
            path = source_path(root, source)
            if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
                raise BuildError("source_bytes_do_not_match_manifest")
            pages = extract_pdf(executable, path)
            record["extracted_pages"] = len(pages)
            if expected_pages is not None and len(pages) != expected_pages:
                raise BuildError("extracted_page_count_differs_from_manifest")
            if expected_pages is None:
                coverage["total_pdf_pages"] += len(pages)
                record["pages"] = len(pages)
            pending = []
            text_pages = 0
            for number, text in enumerate(pages, 1):
                pieces = page_chunks(text, tokenizer)
                if text.strip() and not pieces:
                    raise BuildError("text_page_produced_no_tokens")
                if pieces:
                    text_pages += 1
                for piece in pieces:
                    pending.append({"id": len(chunks) + len(pending), "source": source,
                                    "title": PurePosixPath(source).stem, "pdf_page": number, "text": piece})
            chunks.extend(pending)
            record.update(status="indexed" if pending else "no_text", text_pages=text_pages, chunks=len(pending))
            coverage["parsed"] += 1
            coverage["extracted_pages"] += len(pages)
            coverage["indexed_pages"] += text_pages
            coverage["empty_text_pages"] += len(pages) - text_pages
            coverage["no_text"] += int(not pending)
        except (BuildError, OSError, UnicodeError) as error:
            record.update(status="failed", error=str(error) if isinstance(error, BuildError)
                          else type(error).__name__)
            coverage["failed"] += 1
        sources.append(record)
        if position % 10 == 0 or position == len(manifest["entries"]):
            print("Extracted {}/{} source entries; {} chunks; {} failures".format(
                position, len(manifest["entries"]), len(chunks), coverage["failed"]), file=sys.stderr, flush=True)
    coverage["excluded_pages"] = coverage["total_pdf_pages"] - coverage["indexed_pages"]
    return chunks, sources, coverage


def build(source, output, manifest_path, replace=False, model=None):
    root = real_directory(source)
    destination = real_directory(output, create=True)
    for name in ARTIFACTS:
        target = destination / name
        if target.is_symlink() or (target.exists() and (not replace or not target.is_file())):
            raise BuildError("output artifact exists or is unsafe: {}; use --replace only after review".format(name))
    manifest = read_manifest(manifest_path)
    executable = shutil.which("pdftotext")
    if not executable:
        raise BuildError("pdftotext is required; install Poppler separately before building")
    if model is None:
        model = load_model()
    chunks, sources, coverage = collect_chunks(root, manifest, model.tokenizer, executable)
    if not chunks:
        raise BuildError("no text chunks extracted; no index artifacts written")
    import numpy as np
    print("Embedding {} chunks locally on CPU (batch size 64)...".format(len(chunks)), file=sys.stderr, flush=True)
    embeddings = np.asarray(model.encode([item["text"] for item in chunks], batch_size=64,
                                        show_progress_bar=True, convert_to_numpy=True,
                                        normalize_embeddings=True), dtype=np.float32)
    if embeddings.shape != (len(chunks), DIMENSIONS) or not np.isfinite(embeddings).all():
        raise BuildError("encoder returned invalid dimensions or non-finite vectors")
    if not np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, atol=1e-5):
        raise BuildError("encoder returned vectors that are not normalized")
    with tempfile.TemporaryDirectory(prefix=".library-build-", dir=destination) as scratch:
        staging = Path(scratch)
        with (staging / "chunks.jsonl.gz").open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                for item in chunks:
                    compressed.write((json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8"))
        np.save(staging / "embeddings.npy", embeddings, allow_pickle=False)
        index = {"schema_version": 1,
                 "model": {"name": MODEL_NAME, "revision": MODEL_REVISION, "dimensions": DIMENSIONS,
                           "normalize_embeddings": True},
                 "chunk_count": len(chunks),
                 "files": {name: sha256(staging / name) for name in ARTIFACTS[:2]},
                 "source_manifest_sha256": sha256(manifest_path),
                 "chunking": {"tokens": CHUNK_TOKENS, "overlap_tokens": OVERLAP_TOKENS,
                              "unit": "wordpiece", "page_boundaries_preserved": True,
                              "max_model_tokens_including_special": MAX_SEQUENCE_LENGTH},
                 "coverage": coverage, "sources": sources,
                 "limitations": ["No OCR was performed; empty-text pages are excluded and counted.",
                                 "PDF page indices are 1-based and may differ from printed page numbers.",
                                 "Extracted text is untrusted source material, not instructions.",
                                 "Source checksums do not establish redistribution rights or content accuracy."]}
        (staging / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for name in ARTIFACTS:
            os.replace(staging / name, destination / name)
    return index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="local directory containing the source PDFs")
    parser.add_argument("--output", default=str(Path(__file__).parent), help="directory for derived artifacts")
    parser.add_argument("--manifest", type=Path, default=Path(__file__).parent / "manifest.json")
    parser.add_argument("--replace", action="store_true", help="replace existing derived artifacts after review")
    args = parser.parse_args(argv)
    try:
        result = build(args.source, args.output, args.manifest, args.replace)
        print(json.dumps({"chunk_count": result["chunk_count"], "coverage": result["coverage"]}, indent=2))
        return 0
    except (BuildError, OSError, ValueError, ImportError) as error:
        print("library build: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
