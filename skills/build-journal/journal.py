#!/usr/bin/env python3
"""Create and inspect portable Markdown engineering journals."""

import argparse
import datetime as dt
import os
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import quote, unquote, urlsplit


BUILD_SECTIONS = (
    "Goal", "Constraints", "Success criteria", "Design and request trace",
    "Scope and cuts", "Verification", "Current state",
)
DECISION_SECTIONS = (
    "Context and constraints", "Options", "Choice", "Rationale",
    "Consequences", "Evidence", "Revisit when",
)
OPTION_COLUMNS = ("Option", "State", "Benefits", "Costs and risks", "Fit and rejection reason")
KINDS = ("observation", "hypothesis", "experiment", "result", "change", "blocker", "next")
STATUSES = {"proposed", "accepted", "superseded"}
PROVENANCES = {"contemporaneous", "retrospective", "AI-suggested"}
OPTION_STATES = {"considered", "chosen", "rejected", "deferred", "unexplored"}
IMPLEMENTATION_STATES = {"planned", "implemented", "partially implemented", "not implemented", "unverified"}
PLACEHOLDER = re.compile(r"\bTODO\b|\{\{[^{}]+\}\}", re.IGNORECASE)
DECISION_ID = re.compile(r"^D(\d+)")


class JournalError(Exception):
    pass


def read_text(path):
    return path.read_text(encoding="utf-8")


def title_value(value):
    value = value.strip()
    if not value or "\n" in value or "\r" in value or "\x00" in value:
        raise JournalError("title must be nonempty and on one line")
    return value


def absolute_path(value):
    return Path(os.path.abspath(os.path.expanduser(str(value))))


def reject_symlinks(path, root):
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise JournalError("path escapes journal: {}".format(path))
    current = root
    for part in (None,) + relative.parts:
        if part is not None:
            current = current / part
        if current.is_symlink():
            raise JournalError("refusing symlink: {}".format(current))


def journal_path(value):
    requested = absolute_path(value)
    if requested.is_symlink():
        raise JournalError("refusing symlink journal: {}".format(requested))
    root = requested.resolve()
    if not root.is_dir():
        raise JournalError("journal directory does not exist: {}".format(requested))
    for name in ("BUILD.md", "PROCESS.md", "decisions"):
        path = root / name
        reject_symlinks(path, root)
        valid = path.is_dir() if name == "decisions" else path.is_file()
        if not valid:
            raise JournalError("not a recognizable journal; missing {}".format(path))
    return root


def create_text(path, text):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def template(name, replacements):
    text = read_text(Path(__file__).resolve().parent / "templates" / name)
    return re.sub(r"\{\{(\w+)\}\}", lambda match: replacements.get(match[1], match[0]), text)


def init_journal(args):
    title = title_value(args.title)
    requested = absolute_path(args.path)
    if requested.is_symlink():
        raise JournalError("refusing symlink journal: {}".format(requested))
    root = requested.resolve()
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise JournalError("init requires a new or empty directory: {}".format(requested))
    replacements = {"TITLE": title, "DATE": dt.datetime.now(dt.timezone.utc).date().isoformat()}
    build = template("BUILD.md", replacements)
    process = template("PROCESS.md", replacements)
    root.mkdir(parents=True, exist_ok=True)
    (root / "decisions").mkdir()
    create_text(root / "BUILD.md", build)
    create_text(root / "PROCESS.md", process)
    print("Created journal: {}".format(root))
    return 0


def decision_files(root):
    paths = list((root / "decisions").glob("D*.md"))
    for path in paths:
        reject_symlinks(path, root)
        if not path.is_file():
            raise JournalError("decision is not a regular file: {}".format(path))
    return sorted(paths, key=lambda path: (
        int(DECISION_ID.match(path.name).group(1)) if DECISION_ID.match(path.name) else -1,
        path.name,
    ))


def new_decision(args):
    root = journal_path(args.path)
    title = title_value(args.title)
    numbers = [int(match.group(1)) for path in decision_files(root)
               for match in [DECISION_ID.match(path.name)] if match]
    identifier = "D{:03d}".format(max(numbers, default=0) + 1)
    slug = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")[:64].rstrip("-") or "decision"
    path = root / "decisions" / "{}-{}.md".format(identifier, slug)
    text = template("DECISION.md", {
        "ID": identifier, "TITLE": title,
        "DATE": dt.datetime.now(dt.timezone.utc).date().isoformat(),
    })
    reject_symlinks(path, root)
    create_text(path, text)
    print("Created decision: {}".format(path))
    return 0


def log_event(args):
    root = journal_path(args.path)
    supplied = sys.stdin.read() if args.text == "-" else args.text
    if not supplied.strip():
        raise JournalError("log text must not be empty")
    path = root / "PROCESS.md"
    previous = read_text(path)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    separator = "" if not previous else "\n" if previous.endswith("\n") else "\n\n"
    entry = "{}## {} — {}\n\n{}\n".format(separator, timestamp, args.kind, supplied.rstrip("\n"))
    reject_symlinks(path, root)
    flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(str(path), flags), "w", encoding="utf-8", newline="\n") as stream:
        stream.write(entry)
    print("Appended {} to {}".format(args.kind, path))
    return 0


def markdown_lines(text):
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        fenced = fence is not None
        if marker:
            run, suffix = marker.groups()
            if fence is None:
                fence = (run[0], len(run))
                fenced = True
            elif run[0] == fence[0] and len(run) >= fence[1] and not suffix.strip():
                fence = None
        yield number, line, fenced


def sections(text):
    result = {}
    duplicates = []
    current = None
    for number, line, fenced in markdown_lines(text):
        if not fenced and line.startswith("## "):
            current = line[3:].strip()
            if current in result:
                duplicates.append((number, current))
            else:
                result[current] = [number, []]
        elif current is not None:
            result[current][1].append(line)
    return {name: (number, "\n".join(body).strip()) for name, (number, body) in result.items()}, duplicates


def metadata(text):
    result = {}
    duplicates = []
    for number, line, fenced in markdown_lines(text):
        if fenced:
            continue
        if line.startswith("## "):
            break
        match = re.match(r"^(Status|Recorded|Author|Provenance|Supersedes|Superseded by):\s*(.*?)\s*$", line)
        if match:
            key, value = match.groups()
            if key in result:
                duplicates.append((number, key))
            else:
                result[key] = (number, value)
    return result, duplicates


def preamble(text):
    lines = []
    for _, line, fenced in markdown_lines(text):
        if not fenced and line.startswith("## "):
            break
        lines.append(line)
    return "\n".join(lines)


def table_cells(line):
    return [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def inspect_journal(root):
    issues = []
    records = []

    def warn(path, line, message):
        issues.append("{}:{}: {}".format(path.relative_to(root).as_posix(), line, message))

    def inspect_document(path, required):
        text = read_text(path)
        parsed, duplicates = sections(text)
        if required:
            for line, name in duplicates:
                warn(path, line, "duplicate section: {}".format(name))
        for name in required:
            if name not in parsed:
                warn(path, 1, "missing section: {}".format(name))
            elif not parsed[name][1]:
                warn(path, parsed[name][0], "empty section: {}".format(name))
        for line, content, fenced in markdown_lines(text):
            if PLACEHOLDER.search(content):
                warn(path, line, "unresolved placeholder")
            if not fenced and re.match(r"^#{1,6}[^#\s]", content):
                warn(path, line, "malformed Markdown heading (add a space after #)")
        return text, parsed

    build_text, build_sections = inspect_document(root / "BUILD.md", BUILD_SECTIONS)
    process_text, _ = inspect_document(root / "PROCESS.md", ())
    paths = decision_files(root)
    identifiers = {}
    for path in paths:
        match = DECISION_ID.match(path.name)
        if match:
            identifier = int(match.group(1))
            if identifier in identifiers:
                warn(path, 1, "duplicate decision ID: D{:03d}".format(identifier))
            identifiers[identifier] = path
        else:
            warn(path, 1, "decision filename needs a numeric D identifier")
    for path in paths:
        text, parsed = inspect_document(path, DECISION_SECTIONS)
        fields, duplicates = metadata(text)
        for line, name in duplicates:
            warn(path, line, "duplicate metadata: {}".format(name))
        for name in ("Status", "Recorded", "Author", "Provenance", "Supersedes"):
            if name not in fields or not fields[name][1]:
                warn(path, 1, "missing or empty metadata: {}".format(name))
        status_line, status = fields.get("Status", (1, ""))
        if status not in STATUSES:
            warn(path, status_line, "unsupported decision status: {}".format(status or "(empty)"))
        elif status == "proposed":
            warn(path, status_line, "proposed decision is incomplete; choice remains open")
        provenance_line, provenance = fields.get("Provenance", (1, ""))
        if provenance not in PROVENANCES:
            warn(path, provenance_line, "unsupported provenance: {}".format(provenance or "(empty)"))
        recorded_line, recorded = fields.get("Recorded", (1, ""))
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", recorded):
                raise ValueError()
            dt.date.fromisoformat(recorded)
        except ValueError:
            warn(path, recorded_line, "Recorded must be a valid YYYY-MM-DD date")
        for name in ("Supersedes", "Superseded by"):
            line, value = fields.get(name, (1, "none"))
            if value == "none":
                continue
            reference = re.fullmatch(r"D(\d+)", value)
            if not reference or int(reference.group(1)) not in identifiers:
                warn(path, line, "{} must reference an existing decision ID or none".format(name))
            elif identifiers[int(reference.group(1))] == path:
                warn(path, line, "{} cannot reference this decision itself".format(name))
        if status == "superseded" and fields.get("Superseded by", (1, "none"))[1] in ("", "none"):
            warn(path, status_line, "superseded decision needs Superseded by: D### linkage")

        option_line, option_text = parsed.get("Options", (1, ""))
        table = [(option_line + offset, table_cells(line)) for offset, line in enumerate(option_text.splitlines(), 1)
                 if line.strip().startswith("|")]
        options = {}
        if len(table) < 2 or tuple(table[0][1]) != OPTION_COLUMNS:
            warn(path, option_line, "Options needs the five contract table columns")
        else:
            if len(table[1][1]) != 5 or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in table[1][1]):
                warn(path, table[1][0], "malformed options table separator")
            for line, cells in table[2:]:
                if len(cells) != 5:
                    warn(path, line, "option row must contain five cells")
                    continue
                identifier_match = re.fullmatch(r"([A-Z])(?:\s*:\s*\S.*)?", cells[0])
                if not identifier_match:
                    warn(path, line, "option ID must be a letter, optionally followed by : name")
                    continue
                identifier = identifier_match.group(1)
                if identifier in options:
                    warn(path, line, "duplicate option ID: {}".format(identifier))
                    continue
                options[identifier] = (line, cells)
                if cells[1] not in OPTION_STATES:
                    warn(path, line, "unsupported option state: {}".format(cells[1] or "(empty)"))
                if not all(cells[2:]):
                    warn(path, line, "option needs benefits, costs and risks, and fit/rejection reason")
        if not options:
            warn(path, option_line, "no credible option rows recorded")
        if len(options) == 1:
            rationale_line, rationale = parsed.get("Rationale", (1, ""))
            if not rationale or PLACEHOLDER.search(rationale):
                warn(path, rationale_line, "a single option needs a rationale explaining constraints on alternatives")

        choice_line, choice = parsed.get("Choice", (1, ""))
        chosen = re.findall(r"^Option:\s*(.*?)\s*$", choice, re.MULTILINE)
        implementation = re.findall(r"^Implementation:\s*(.*?)\s*$", choice, re.MULTILINE)
        if len(chosen) != 1:
            warn(path, choice_line, "Choice needs exactly one Option: <ID> line")
        selected = chosen[0] if len(chosen) == 1 else ""
        if selected not in options and selected != "TODO":
            warn(path, choice_line, "chosen option is absent from Options: {}".format(selected or "(empty)"))
        if status == "accepted" and selected not in options:
            warn(path, choice_line, "accepted decision needs a selected option")
        if len(implementation) != 1 or implementation[0] not in IMPLEMENTATION_STATES:
            warn(path, choice_line, "Choice needs one Implementation: line with a supported implementation state")
        chosen_rows = [identifier for identifier, (_, cells) in options.items() if cells[1] == "chosen"]
        if len(chosen_rows) > 1 or (chosen_rows and chosen_rows != [selected]):
            warn(path, option_line, "chosen table rows contradict Choice")
        if status == "accepted" and selected in options and chosen_rows != [selected]:
            warn(path, option_line, "accepted selected option must be the sole chosen table row")
        records.append({"path": path, "text": text, "sections": parsed, "metadata": fields})
    by_id = {int(DECISION_ID.match(record["path"].name).group(1)): record
             for record in records if DECISION_ID.match(record["path"].name)}

    def reference(record, field):
        value = record["metadata"].get(field, (1, "none"))[1]
        match = re.fullmatch(r"D(\d+)", value)
        return int(match.group(1)) if match else None

    for name in ("Design and request trace", "Current state"):
        line, content = build_sections.get(name, (1, ""))
        for identifier in sorted({int(value) for value in re.findall(r"\bD(\d+)\b", content)}):
            record = by_id.get(identifier)
            if record and record["metadata"].get("Status", (1, ""))[1] == "superseded":
                replacement = reference(record, "Superseded by")
                message = "{} references superseded decision D{:03d}; reconcile the current BUILD record".format(name, identifier)
                if replacement is not None:
                    message += " (replacement: D{:03d})".format(replacement)
                warn(root / "BUILD.md", line, message)

    for identifier, record in by_id.items():
        fields = record["metadata"]
        status = fields.get("Status", (1, ""))[1]
        old = by_id.get(reference(record, "Supersedes"))
        if old and status in {"accepted", "superseded"}:
            if (old["metadata"].get("Status", (1, ""))[1] != "superseded"
                    or reference(old, "Superseded by") != identifier):
                warn(record["path"], fields["Supersedes"][0],
                     "supersession requires the older decision to be superseded and link back with Superseded by")
        replacement = by_id.get(reference(record, "Superseded by"))
        if replacement and status == "superseded":
            if (replacement["metadata"].get("Status", (1, ""))[1] not in {"accepted", "superseded"}
                    or reference(replacement, "Supersedes") != identifier):
                warn(record["path"], fields["Superseded by"][0],
                     "replacement must be accepted or superseded and link back with Supersedes")
        seen = set()
        current = identifier
        while current in by_id:
            if current in seen:
                warn(record["path"], fields.get("Superseded by", (1, ""))[0], "supersession linkage contains a cycle")
                break
            seen.add(current)
            current = reference(by_id[current], "Superseded by")
    return issues, build_text, build_sections, process_text, records


def check_journal(args):
    root = journal_path(args.path)
    issues, *_ = inspect_journal(root)
    for issue in issues:
        print("WARNING: " + issue)
    if issues:
        print("{} journal gap(s). Completeness does not establish correctness or readiness.".format(len(issues)))
        return 1
    print("No structural gaps found. Claims are unverified; completeness does not establish correctness or readiness.")
    return 0


def source_link(path, output):
    relative = Path(os.path.relpath(str(path), str(output.parent))).as_posix()
    return "[{}]({})".format(path.name.replace("[", r"\[").replace("]", r"\]"), quote(relative, safe="/._-"))


def quoted(text):
    return "\n".join("> " + line if line else ">" for line in text.splitlines()) or "> (No text recorded.)"


def excerpt(text, source, output):
    def destination(target):
        angle = target.startswith("<") and target.endswith(">")
        value = target[1:-1] if angle else target
        if value.startswith("/") or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value):
            return target
        url = urlsplit(value)
        source_target = source.parent / unquote(url.path) if url.path else source
        relative = Path(os.path.relpath(str(source_target), str(output.parent))).as_posix()
        value = quote(relative, safe="/._-")
        if url.query:
            value += "?" + url.query
        if url.fragment:
            value += "#" + url.fragment
        return "<" + value + ">" if angle else value

    inline = re.compile(
        r"(?P<code>`+).*?(?P=code)|(?P<prefix>\]\(\s*)"
        r"(?P<target><[^>\n]*>|(?:\\.|[^()\s]|\([^()\n]*\))+)"
        r"(?P<tail>\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\)"
    )
    reference = re.compile(r"^( {0,3}\[[^\]]+\]:\s*)(<[^>\n]*>|\S+)(.*)$")

    def replace(match):
        if match.group("code"):
            return match.group(0)
        return match.group("prefix") + destination(match.group("target")) + (match.group("tail") or "") + ")"

    lines = []
    for _, line, fenced in markdown_lines(text):
        if not fenced:
            definition = reference.match(line)
            if definition:
                line = definition.group(1) + destination(definition.group(2)) + definition.group(3)
            else:
                line = inline.sub(replace, line)
        lines.append(line)
    return quoted("\n".join(lines))


def presentation_text(root, output, inspection):
    issues, build_text, build_sections, process_text, records = inspection
    title = next((line[2:] for line in build_text.splitlines() if line.startswith("# ")), root.name)
    lines = ["# Presentation: {}".format(title), "",
             "This is an uncurated review draft and deterministic scaffold of recorded author assertions, not independent verification. "
             "An accepted choice does not establish implementation. Plans, hypotheses, and reported results retain their source labels.", "",
             "## Project and recorded state", "", "Source: " + source_link(root / "BUILD.md", output), ""]
    lines.extend(["### Source preamble (author supplied)", "",
                  excerpt(preamble(build_text), root / "BUILD.md", output), ""])
    for name in BUILD_SECTIONS:
        lines.extend(["### " + name, "", excerpt(build_sections.get(name, (0, ""))[1], root / "BUILD.md", output), ""])
    lines.extend(["## Decisions and tradeoffs", ""])
    if not records:
        lines.extend(["No decision records found.", ""])
    for record in records:
        record_title = next((line[2:] for line in record["text"].splitlines() if line.startswith("# ")), record["path"].stem)
        lines.extend(["### " + record_title, "", "Source: " + source_link(record["path"], output), ""])
        lines.extend(["**Source preamble (author supplied)**", "",
                      excerpt(preamble(record["text"]), record["path"], output), ""])
        for name in DECISION_SECTIONS:
            label = "Evidence (author supplied; not independently verified)" if name == "Evidence" else name
            lines.extend(["**{}**".format(label), "", excerpt(record["sections"].get(name, (0, ""))[1], record["path"], output), ""])
    lines.extend(["## Process history (author supplied; not independently verified)", "",
                  "Source: {}. The full process source is quoted in its original order; the source retains the full history.".format(source_link(root / "PROCESS.md", output)), ""])
    lines.extend([excerpt(process_text, root / "PROCESS.md", output), ""])
    lines.extend(["## Gaps and uncertainty", ""])
    if issues:
        lines.extend("- " + issue for issue in issues)
    else:
        lines.append("- No structural gaps found. The tool cannot validate truth, implementation, test results, or readiness.")
    lines.extend(["", "## Q&A prompts", "",
                  "- Which constraints drove the recorded choice, and why were the alternatives not selected?",
                  "- What evidence supports the reported results, and what remains planned or unverified?",
                  "- What costs, risks, scope cuts, and revisit triggers should the audience understand?", ""])
    return "\n".join(lines)


def present_journal(args):
    root = journal_path(args.path)
    output = absolute_path(args.output) if args.output else root / "PRESENTATION.md"
    requested_root = absolute_path(args.path)
    if output.is_relative_to(requested_root):
        output = root / output.relative_to(requested_root)
    if output.is_relative_to(root):
        reject_symlinks(output, root)
    else:
        if output.is_symlink():
            raise JournalError("refusing symlink output: {}".format(output))
        output = output.parent.resolve() / output.name
    if not output.parent.is_dir():
        raise JournalError("output parent directory does not exist: {}".format(output.parent))
    if output.exists():
        raise JournalError("output already exists; choose a new filename: {}".format(output))
    inspection = inspect_journal(root)
    create_text(output, presentation_text(root, output, inspection))
    print("Created presentation scaffold: {}".format(output))
    print("Recorded claims remain unverified; {} structural gap(s).".format(len(inspection[0])))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="create a new or empty journal directory")
    init.add_argument("path")
    init.add_argument("--title", required=True)
    init.set_defaults(handler=init_journal)
    decision = commands.add_parser("decision", help="create the next decision record")
    decision.add_argument("path")
    decision.add_argument("title")
    decision.set_defaults(handler=new_decision)
    log = commands.add_parser("log", help="append supplied text to the process log")
    log.add_argument("path")
    log.add_argument("--kind", required=True, choices=KINDS)
    log.add_argument("--text", required=True, help="text to record, or - to read standard input")
    log.set_defaults(handler=log_event)
    check = commands.add_parser("check", help="inspect structure and unresolved gaps")
    check.add_argument("path")
    check.set_defaults(handler=check_journal)
    present = commands.add_parser("present", help="create an attributed presentation scaffold")
    present.add_argument("path")
    present.add_argument("--output", help="new output path, relative to the current directory")
    present.set_defaults(handler=present_journal)
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (JournalError, OSError, UnicodeError) as error:
        print("ERROR: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
