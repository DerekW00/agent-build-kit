#!/usr/bin/env python3
"""Install the portable kit into an existing project without changing global settings."""

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys


KIT_ROOT = Path(__file__).resolve().parent
PROVIDERS = {"claude": (".claude/skills",), "codex": (".agents/skills",),
             "both": (".claude/skills", ".agents/skills")}
PROFILES = ("build", "long-session", "manual")
SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class KitError(Exception):
    pass


@dataclass
class FileEntry:
    relative: Path
    content: bytes
    mode: int = 0o644


@dataclass
class InstallPlan:
    project: Path
    directories: list
    files: list
    exclusive: list
    conflicts: list


def project_directory(value):
    requested = Path(value).expanduser()
    if requested.is_symlink():
        raise KitError("refusing symlink project directory: {}".format(requested))
    try:
        project = requested.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise KitError("project directory must already exist: {} ({})".format(requested, error))
    if not project.is_dir():
        raise KitError("project is not a directory: {}".format(requested))
    return project


def source_stat(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise KitError("source path escapes kit: {}".format(relative))
    current = root
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as error:
            raise KitError("cannot read kit source {}: {}".format(current, error))
        if stat.S_ISLNK(metadata.st_mode):
            raise KitError("refusing source symlink: {}".format(current))
        if not stat.S_ISREG(metadata.st_mode) and not stat.S_ISDIR(metadata.st_mode):
            raise KitError("source is not a regular file or directory: {}".format(current))
    return metadata


def source_file(root, relative):
    metadata = source_stat(root, relative)
    if not stat.S_ISREG(metadata.st_mode):
        raise KitError("source is not a regular file: {}".format(root / relative))
    return (root / relative).read_bytes(), stat.S_IMODE(metadata.st_mode) & 0o777


def add_skill(root, name, destination, directories, files):
    source = Path("skills") / name
    if not stat.S_ISDIR(source_stat(root, source).st_mode):
        raise KitError("skill source is not a directory: {}".format(source))
    source_file(root, source / "SKILL.md")

    def visit(relative, target):
        directories.add(target)
        for child in sorted((root / relative).iterdir(), key=lambda path: path.name):
            child_source = relative / child.name
            child_target = target / child.name
            metadata = source_stat(root, child_source)
            if stat.S_ISDIR(metadata.st_mode) and child.name == "__pycache__":
                continue
            if stat.S_ISREG(metadata.st_mode) and (child.suffix in (".pyc", ".pyo") or
                                                  child.name == ".DS_Store"):
                continue
            if stat.S_ISDIR(metadata.st_mode):
                visit(child_source, child_target)
            else:
                content, mode = source_file(root, child_source)
                files.append(FileEntry(child_target, content, mode))

    visit(source, destination)


def destination_conflict(project, relative, directory=False, exclusive=False):
    if relative.is_absolute() or ".." in relative.parts:
        return "destination escapes project: {}".format(relative)
    current = project
    for index, part in enumerate(relative.parts):
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            return None
        except OSError as error:
            return "cannot inspect {}: {}".format(current, error)
        if stat.S_ISLNK(metadata.st_mode):
            return "refusing destination symlink: {}".format(current)
        is_leaf = index == len(relative.parts) - 1
        if is_leaf and (exclusive or not directory):
            return "already exists: {}".format(current)
        if not stat.S_ISDIR(metadata.st_mode):
            return "not a directory: {}".format(current)
    return None


def preflight(plan):
    conflicts = set()
    if plan.project.is_symlink() or not plan.project.is_dir():
        conflicts.add("project is no longer a real directory: {}".format(plan.project))
    for relative in plan.directories:
        conflict = destination_conflict(plan.project, relative, directory=True,
                                        exclusive=relative in plan.exclusive)
        if conflict:
            conflicts.add(conflict)
    for entry in plan.files:
        conflict = destination_conflict(plan.project, entry.relative)
        if conflict:
            conflicts.add(conflict)
    return sorted(conflicts)


def build_plan(project, provider, profile, with_instructions=False, source_root=None):
    if provider not in PROVIDERS or profile not in PROFILES:
        raise KitError("unknown provider or profile")
    if profile == "manual" and with_instructions:
        raise KitError("manual profile forbids --with-instructions")
    project = project_directory(project)
    root = KIT_ROOT if source_root is None else Path(source_root).resolve()
    try:
        profiles = json.loads(source_file(root, Path("profiles.json"))[0].decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise KitError("invalid profiles.json: {}".format(error))
    names = profiles.get(profile) if isinstance(profiles, dict) else None
    if not isinstance(names, list) or any(not isinstance(name, str) or
                                          not SKILL_NAME.fullmatch(name) for name in names):
        raise KitError("profile must contain a list of safe lowercase skill names")
    if len(set(names)) != len(names):
        raise KitError("profile contains duplicate skill names")
    if profile == "manual" and names:
        raise KitError("manual profile must not contain AI skills")
    version = source_file(root, Path("VERSION"))[0].decode("utf-8").strip()
    if not version or "\n" in version or "\r" in version:
        raise KitError("VERSION must contain one nonempty line")

    directories = {Path(".agent-kit")}
    exclusive = [Path(".agent-kit")]
    files = []
    for provider_root in PROVIDERS[provider]:
        for name in names:
            destination = Path(provider_root) / name
            exclusive.append(destination)
            add_skill(root, name, destination, directories, files)
    templates = [("LOCAL-SETUP.md", ".agent-kit/SETUP.md"),
                 ("MANUAL.md", ".agent-kit/MANUAL.md")]
    if profile == "long-session":
        templates.append(("SESSION.md", ".agent-kit/SESSION.template.md"))
    if with_instructions:
        templates.extend((("AGENTS.md", "AGENTS.md"), ("CLAUDE.md", "CLAUDE.md")))
    for source, destination in templates:
        content, mode = source_file(root, Path("templates") / source)
        files.append(FileEntry(Path(destination), content, mode))
    manifest = {"version": version, "profile": profile, "provider": provider,
                "files": {entry.relative.as_posix(): hashlib.sha256(entry.content).hexdigest()
                          for entry in sorted(files, key=lambda item: item.relative.as_posix())}}
    files.append(FileEntry(Path(".agent-kit/installed.json"),
                           (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")))
    for path in list(directories) + [entry.relative for entry in files]:
        directories.update(parent for parent in path.parents if parent != Path("."))
    plan = InstallPlan(project, sorted(directories, key=lambda path: (len(path.parts), str(path))),
                       sorted(files, key=lambda entry: str(entry.relative)), exclusive, [])
    plan.conflicts = preflight(plan)
    return plan


def record_created(path, created):
    metadata = path.lstat()
    created.append((path, metadata.st_dev, metadata.st_ino))


def rollback(created):
    errors = []
    for path, device, inode in reversed(created):
        try:
            metadata = path.lstat()
            if (metadata.st_dev, metadata.st_ino) != (device, inode):
                errors.append("preserved changed path: {}".format(path))
            elif stat.S_ISDIR(metadata.st_mode):
                path.rmdir()
            else:
                path.unlink()
        except FileNotFoundError:
            pass
        except OSError as error:
            errors.append("could not remove {}: {}".format(path, error))
    return errors


def apply_plan(plan):
    conflicts = preflight(plan)
    if conflicts:
        raise KitError("install refused:\n" + "\n".join(conflicts))
    created = []
    try:
        for relative in plan.directories:
            conflict = destination_conflict(plan.project, relative, directory=True,
                                            exclusive=relative in plan.exclusive)
            if conflict:
                raise KitError(conflict)
            path = plan.project / relative
            if not path.exists():
                path.mkdir()
                record_created(path, created)
        for entry in plan.files:
            conflict = destination_conflict(plan.project, entry.relative)
            if conflict:
                raise KitError(conflict)
            path = plan.project / entry.relative
            descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, entry.mode)
            record_created(path, created)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(entry.content)
            path.chmod(entry.mode)
    except BaseException as error:
        errors = rollback(created)
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        detail = "\nRollback: " + "; ".join(errors) if errors else "\nCreated paths rolled back."
        raise KitError("install failed: {}{}".format(error, detail)) from error


def install(args):
    plan = build_plan(args.project, args.provider, args.profile, args.with_instructions)
    print("{}: {}".format("APPLY" if args.apply else "DRY RUN (no writes)", plan.project))
    for relative in plan.directories:
        if not (plan.project / relative).exists():
            print("  create directory {}".format(relative.as_posix()))
    for entry in plan.files:
        print("  create file {}".format(entry.relative.as_posix()))
    if plan.conflicts:
        print("Conflicts; no files written:")
        for conflict in plan.conflicts:
            print("  {}".format(conflict))
        return 1
    if args.apply:
        apply_plan(plan)
        print("Installed {} files. Manifest: .agent-kit/installed.json".format(len(plan.files)))
    else:
        print("No conflicts. Re-run with --apply to create these paths.")
    return 0


def doctor():
    print("Python: {}".format(platform.python_version()))
    for command in ("git", "gh", "uv", "rg", "node", "claude", "codex"):
        executable = shutil.which(command)
        if executable is None:
            print("{}: not found (optional)".format(command))
            continue
        try:
            result = subprocess.run([executable, "--version"], capture_output=True, text=True,
                                    timeout=3, check=False)
            lines = (result.stdout or "").strip().splitlines()
            if result.returncode == 0 and lines:
                version = "".join(character for character in lines[0] if character.isprintable())[:160]
                print("{}: {}".format(command, version))
            else:
                print("{}: available; version unavailable (exit {})".format(command, result.returncode))
        except subprocess.TimeoutExpired:
            print("{}: available; version check timed out".format(command))
        except (OSError, UnicodeError):
            print("{}: available; version check failed".format(command))
    print("Read-only availability check; this is not a full readiness guarantee.")
    print("No authentication, permissions, network access, or project behavior was checked.")
    return 0


def parser():
    result = argparse.ArgumentParser(description=__doc__, epilog=(
        "Python 3.9+; standard library only. No global configuration, authentication, network, "
        "package installation, hooks, or Git changes. Existing files are never overwritten."))
    commands = result.add_subparsers(dest="command", required=True)
    install_parser = commands.add_parser("install", help="preview or apply a project-local install",
                                        description="Default: dry run, no writes. Existing destinations are refused.")
    install_parser.add_argument("--project", required=True, help="existing project directory; leaf symlinks refused")
    install_parser.add_argument("--provider", choices=tuple(PROVIDERS), required=True,
                                help="Claude .claude/skills, Codex .agents/skills, or both")
    install_parser.add_argument("--profile", choices=PROFILES, required=True,
                                help="manual creates documents only, with no AI skills")
    install_parser.add_argument("--apply", action="store_true", help="create planned paths after conflict checks")
    install_parser.add_argument("--with-instructions", action="store_true",
                                help="also create AGENTS.md and CLAUDE.md; forbidden for manual; refuse existing files")
    commands.add_parser("doctor", help="read-only tool availability/version checks; missing tools are optional")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if sys.version_info < (3, 9):
        print("Error: Python 3.9 or newer is required.", file=sys.stderr)
        return 1
    try:
        return install(args) if args.command == "install" else doctor()
    except (KitError, OSError, UnicodeError) as error:
        print("Error: {}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
