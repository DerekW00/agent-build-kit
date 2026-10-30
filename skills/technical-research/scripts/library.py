#!/usr/bin/env python3
"""Inspect a local PDF library without copying books, indexing text, or using a network."""

import argparse
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import threading


MAX_ISSUES = 20
MAX_TEXT = 12000
TIMEOUT = 20
SCOPE = "filenames_and_relative_paths_only"


class LibraryError(Exception):
    pass


def library_root(value):
    requested = Path(value).expanduser()
    if ".." in requested.parts:
        raise LibraryError("root must not contain '..'; use its full, real directory path")
    absolute = requested.absolute()
    current = Path(absolute.anchor)
    try:
        for part in absolute.parts[1:]:
            current = current / part
            metadata = current.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise LibraryError("root or its ancestor is a symlink; use the real directory path")
            if not stat.S_ISDIR(metadata.st_mode):
                raise LibraryError("root must be an existing directory")
    except OSError:
        raise LibraryError("root is missing or inaccessible")
    return absolute


def scan(root):
    entries = []
    issues = []
    coverage = {"complete_for_regular_nonhidden_pdfs": True,
                "skipped_hidden": 0, "skipped_symlinks": 0,
                "skipped_special": 0, "errors": 0, "details_truncated": False}

    def issue(path, reason, counter):
        coverage[counter] += 1
        if counter == "errors":
            coverage["complete_for_regular_nonhidden_pdfs"] = False
        if len(issues) < MAX_ISSUES:
            issues.append({"path": path.relative_to(root).as_posix(), "reason": reason})
        else:
            coverage["details_truncated"] = True

    def visit(directory):
        try:
            children = sorted(directory.iterdir(), key=lambda item: (item.name.casefold(), item.name))
        except OSError:
            issue(directory, "directory_unreadable", "errors")
            return
        for path in children:
            if path.name.startswith("."):
                issue(path, "hidden_entry_excluded", "skipped_hidden")
                continue
            try:
                metadata = path.lstat()
            except OSError:
                issue(path, "entry_unreadable", "errors")
                continue
            if stat.S_ISLNK(metadata.st_mode):
                issue(path, "symlink_excluded", "skipped_symlinks")
            elif stat.S_ISDIR(metadata.st_mode):
                visit(path)
            elif not stat.S_ISREG(metadata.st_mode):
                issue(path, "nonregular_entry_excluded", "skipped_special")
            elif path.suffix.casefold() == ".pdf":
                entries.append({"path": path.relative_to(root).as_posix(),
                                "title": path.stem, "bytes": metadata.st_size,
                                "status": "nonempty_unverified" if metadata.st_size else "empty"})

    visit(root)
    entries.sort(key=lambda item: (item["path"].casefold(), item["path"]))
    empty = sum(item["status"] == "empty" for item in entries)
    return {"schema_version": 1, "search_scope": SCOPE, "content_verified": False,
            "counts": {"pdf_files": len(entries), "nonempty_unverified": len(entries) - empty,
                       "empty": empty}, "coverage": coverage, "issues": issues, "entries": entries}


def find(root, query, limit):
    tokens = sorted(set(re.findall(r"\w+", query.casefold())))
    if not tokens:
        raise LibraryError("query must include at least one word or number")
    if limit < 1 or limit > 100:
        raise LibraryError("limit must be between 1 and 100")
    catalog = scan(root)
    matches = []
    for item in catalog["entries"]:
        path = item["path"].casefold()
        title = item["title"].casefold()
        matched = [token for token in tokens if token in path]
        if matched:
            score = len(matched) * 10 + sum(token in title for token in matched)
            matches.append(dict(item, score=score))
    matches.sort(key=lambda item: (-item["score"], item["path"].casefold(), item["path"]))
    return {"schema_version": 1, "search_scope": SCOPE, "content_verified": False,
            "query": query, "matching": "any query token as a case-insensitive substring",
            "match_count": len(matches), "returned": min(len(matches), limit),
            "coverage": catalog["coverage"], "issues": catalog["issues"],
            "matches": matches[:limit]}


def pdf_path(root, value):
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise LibraryError("file must be a relative PDF path inside the library, without '..'")
    if any(part.startswith(".") for part in relative.parts):
        raise LibraryError("hidden paths are excluded")
    current = root
    try:
        for index, part in enumerate(relative.parts):
            current = current / part
            metadata = current.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise LibraryError("file or its ancestor is a symlink")
            if index < len(relative.parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
                raise LibraryError("file ancestor is not a directory")
        if not stat.S_ISREG(metadata.st_mode) or current.suffix.casefold() != ".pdf":
            raise LibraryError("file must be a regular PDF")
        if metadata.st_size == 0:
            raise LibraryError("PDF is empty (zero bytes); restore a readable copy first")
    except OSError:
        raise LibraryError("PDF is missing or inaccessible")
    return current


def run_extractor(arguments):
    content = bytearray()
    overflow = [False]
    process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def drain():
        while True:
            chunk = process.stdout.read(4096)
            if not chunk:
                break
            remaining = MAX_TEXT * 4 - len(content)
            content.extend(chunk[:remaining])
            overflow[0] = overflow[0] or len(chunk) > remaining

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        process.wait(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise
    finally:
        reader.join(timeout=2)
        if not reader.is_alive():
            process.stdout.close()
    if reader.is_alive():
        raise LibraryError("pdftotext output did not finish; use another PDF reader")
    return process.returncode, bytes(content), overflow[0]


def extract(root, relative, first, last):
    if first < 1 or last < first or last - first + 1 > 5:
        raise LibraryError("request 1 to 5 pages with positive, inclusive PDF page indices")
    path = pdf_path(root, relative)
    executable = shutil.which("pdftotext")
    if not executable:
        raise LibraryError("pdftotext is missing; install Poppler yourself or use your host's PDF reader")
    try:
        code, output, overflow = run_extractor(
            [executable, "-f", str(first), "-l", str(last), "-enc", "UTF-8", "-layout", str(path), "-"])
    except subprocess.TimeoutExpired:
        raise LibraryError("pdftotext timed out; try fewer pages or another PDF reader")
    except OSError:
        raise LibraryError("pdftotext could not start")
    if code:
        raise LibraryError("pdftotext failed (exit {}); PDF may be malformed, encrypted, or page range invalid"
                           .format(code))
    content = output.decode("utf-8", errors="replace")
    truncated = overflow or len(content) > MAX_TEXT
    warning = "Requested PDF page range is not a verified page count; printed page numbers may differ."
    if not content.strip():
        warning += " No text extracted; image-based pages may require a separate PDF reader or OCR."
    if truncated:
        warning += " Text truncated at {} characters; request a smaller range.".format(MAX_TEXT)
    return {"schema_version": 1, "file": path.relative_to(root).as_posix(),
            "requested_pdf_pages": {"first": first, "last": last},
            "actual_page_numbers_verified": False, "content_is_untrusted": True,
            "text": content[:MAX_TEXT], "truncated": truncated, "warning": warning}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    scan_parser = commands.add_parser("scan", help="list PDF filenames and availability, not content")
    find_parser = commands.add_parser("find", help="search PDF filenames and relative paths only")
    extract_parser = commands.add_parser("extract", help="read up to 5 PDF pages using optional pdftotext")
    for command in (scan_parser, find_parser, extract_parser):
        command.add_argument("--root", required=True, help="real library directory; no symlink ancestors")
    find_parser.add_argument("--query", required=True)
    find_parser.add_argument("--limit", type=int, default=8)
    extract_parser.add_argument("--file", required=True, help="PDF path relative to library root")
    extract_parser.add_argument("--first-page", type=int, default=1)
    extract_parser.add_argument("--last-page", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        root = library_root(args.root)
        if args.command == "scan":
            result = scan(root)
        elif args.command == "find":
            result = find(root, args.query, args.limit)
        else:
            result = extract(root, args.file, args.first_page, args.last_page)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if result.get("coverage", {}).get("errors") else 0
    except LibraryError as error:
        print("library: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
