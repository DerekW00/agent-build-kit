import compileall
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import kit


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.source = self.base / "kit source"
        self.project = self.base / "target project"
        self.source.mkdir()
        self.project.mkdir()
        self.write("VERSION", "0.1.0\n")
        self.write("profiles.json", json.dumps({"build": ["sample"],
                                               "long-session": ["sample", "handoff"], "manual": []}))
        for name in ("LOCAL-SETUP.md", "MANUAL.md", "SESSION.md", "AGENTS.md", "CLAUDE.md"):
            self.write("templates/" + name, "# " + name + "\n")
        for skill in ("sample", "handoff"):
            self.write("skills/{}/SKILL.md".format(skill), "# " + skill + "\n")
            self.write("skills/{}/references/detail.md".format(skill), "Bundled detail\n")
        helper = self.write("skills/sample/run.py", "#!/usr/bin/env python3\nprint('sample')\n")
        helper.chmod(0o755)
        (self.source / "skills/sample/empty").mkdir()

    def write(self, relative, content):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def plan(self, provider="both", profile="build", **kwargs):
        return kit.build_plan(self.project, provider, profile, source_root=self.source, **kwargs)

    def cli(self, *args):
        output = io.StringIO()
        with mock.patch.object(kit, "KIT_ROOT", self.source), contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(output):
            code = kit.main(["install", "--project", str(self.project), "--provider", "both",
                             "--profile", "build"] + list(args))
        return code, output.getvalue()

    def snapshot(self):
        return {str(path.relative_to(self.project)): path.read_bytes() if path.is_file() else None
                for path in self.project.rglob("*")}

    def test_dry_run_does_not_mutate_project(self):
        (self.project / "keep.txt").write_text("keep", encoding="utf-8")
        before = self.snapshot()
        code, output = self.cli()
        self.assertEqual(code, 0, output)
        self.assertIn("DRY RUN (no writes)", output)
        self.assertIn(".agents/skills/sample/SKILL.md", output)
        self.assertIn(".claude/skills/sample/SKILL.md", output)
        self.assertEqual(self.snapshot(), before)

    def test_both_providers_get_standalone_complete_contents(self):
        kit.apply_plan(self.plan())
        shutil.rmtree(self.source)
        for provider in (".agents", ".claude"):
            skill = self.project / provider / "skills/sample"
            self.assertEqual((skill / "SKILL.md").read_text(), "# sample\n")
            self.assertEqual((skill / "references/detail.md").read_text(), "Bundled detail\n")
            self.assertTrue((skill / "empty").is_dir())
            self.assertEqual((skill / "run.py").stat().st_mode & 0o777, 0o755)
            self.assertFalse(any(path.is_symlink() for path in skill.rglob("*")))
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertFalse((self.project / "CLAUDE.md").exists())

    def test_individual_provider_only_creates_selected_directory(self):
        for provider, expected, absent in (("claude", ".claude", ".agents"),
                                           ("codex", ".agents", ".claude")):
            with self.subTest(provider=provider):
                target = self.base / provider
                target.mkdir()
                plan = kit.build_plan(target, provider, "build", source_root=self.source)
                kit.apply_plan(plan)
                self.assertTrue((target / expected / "skills/sample/SKILL.md").is_file())
                self.assertFalse((target / absent).exists())

    def test_manifest_hashes_every_installed_payload(self):
        kit.apply_plan(self.plan(with_instructions=True))
        manifest_path = self.project / ".agent-kit/installed.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual((manifest["version"], manifest["profile"], manifest["provider"]),
                         ("0.1.0", "build", "both"))
        installed = {path.relative_to(self.project).as_posix() for path in self.project.rglob("*")
                     if path.is_file() and path != manifest_path}
        self.assertEqual(set(manifest["files"]), installed)
        for relative, digest in manifest["files"].items():
            self.assertEqual(digest, hashlib.sha256((self.project / relative).read_bytes()).hexdigest())

    def test_generated_caches_do_not_change_manifest_or_installed_contents(self):
        before = self.plan()
        with mock.patch.object(sys, "pycache_prefix", None):
            self.assertTrue(compileall.compile_dir(str(self.source / "skills"), quiet=1))
        self.assertTrue(list((self.source / "skills").rglob("*.pyc")))
        for relative in ("skills/sample/legacy.pyc", "skills/sample/legacy.pyo",
                         "skills/sample/.DS_Store", "skills/sample/references/.DS_Store",
                         "skills/sample/references/__pycache__/local-paths.txt"):
            self.write(relative, "generated cache bytes must not be copied")
        after = self.plan()
        self.assertEqual(after.directories, before.directories)
        self.assertEqual({entry.relative: entry.content for entry in after.files},
                         {entry.relative: entry.content for entry in before.files})
        kit.apply_plan(after)
        for path in self.project.rglob("*"):
            self.assertNotEqual(path.name, "__pycache__")
            self.assertNotEqual(path.name, ".DS_Store")
            self.assertNotIn(path.suffix, (".pyc", ".pyo"))
            if path.is_file():
                self.assertNotIn(b"generated cache bytes must not be copied", path.read_bytes())

    def test_manual_installs_documents_without_ai_directories(self):
        kit.apply_plan(self.plan(profile="manual"))
        self.assertEqual(set(path.name for path in self.project.iterdir()), {".agent-kit"})
        self.assertEqual(set(path.name for path in (self.project / ".agent-kit").iterdir()),
                         {"SETUP.md", "MANUAL.md", "installed.json"})
        self.assertNotIn("SESSION.template.md", self.snapshot())

    def test_manual_rejects_instructions_before_writes(self):
        with self.assertRaisesRegex(kit.KitError, "manual profile forbids"):
            self.plan(profile="manual", with_instructions=True)
        self.assertEqual(self.snapshot(), {})

    def test_manual_rejects_profile_with_ai_skills(self):
        self.write("profiles.json", '{"manual": ["sample"]}')
        with self.assertRaisesRegex(kit.KitError, "must not contain AI skills"):
            self.plan(profile="manual")
        self.assertEqual(self.snapshot(), {})

    def test_long_session_has_session_template_and_additional_skill(self):
        kit.apply_plan(self.plan(profile="long-session"))
        self.assertEqual((self.project / ".agent-kit/SESSION.template.md").read_text(), "# SESSION.md\n")
        self.assertTrue((self.project / ".agents/skills/handoff/SKILL.md").is_file())

    def test_instructions_are_opt_in_and_copied_exactly(self):
        kit.apply_plan(self.plan(with_instructions=True))
        for name in ("AGENTS.md", "CLAUDE.md"):
            self.assertEqual((self.project / name).read_bytes(), (self.source / "templates" / name).read_bytes())

    def test_instruction_conflict_preserves_all_project_files(self):
        (self.project / "AGENTS.md").write_text("existing instructions", encoding="utf-8")
        (self.project / "CLAUDE.md").mkdir()
        before = self.snapshot()
        code, output = self.cli("--apply", "--with-instructions")
        self.assertEqual(code, 1)
        self.assertIn("AGENTS.md", output)
        self.assertIn("CLAUDE.md", output)
        self.assertIn("Conflicts; no files written", output)
        self.assertEqual(self.snapshot(), before)

    def test_existing_instructions_do_not_block_default_install(self):
        for name in ("AGENTS.md", "CLAUDE.md"):
            (self.project / name).write_text("keep", encoding="utf-8")
        kit.apply_plan(self.plan())
        for name in ("AGENTS.md", "CLAUDE.md"):
            self.assertEqual((self.project / name).read_text(), "keep")

    def test_parent_alias_and_spaces_resolve_to_named_project(self):
        alias = self.base / "parent alias"
        alias.symlink_to(self.base, target_is_directory=True)
        plan = kit.build_plan(alias / self.project.name, "both", "build", source_root=self.source)
        self.assertEqual(plan.project, self.project)
        kit.apply_plan(plan)
        self.assertTrue((self.project / ".agent-kit/installed.json").is_file())

    def test_missing_file_and_leaf_symlink_projects_are_rejected(self):
        file_path = self.base / "file"
        file_path.write_text("file", encoding="utf-8")
        alias = self.base / "project link"
        alias.symlink_to(self.project, target_is_directory=True)
        for path in (self.base / "missing", file_path, alias):
            with self.subTest(path=path), self.assertRaises(kit.KitError):
                kit.build_plan(path, "both", "build", source_root=self.source)
        self.assertEqual(self.snapshot(), {})

    def test_destination_symlink_ancestors_are_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        for relative in (".agents", ".agents/skills", ".agents/skills/sample", ".agent-kit"):
            with self.subTest(relative=relative):
                link = self.project / relative
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(outside, target_is_directory=True)
                plan = self.plan()
                self.assertTrue(any("destination symlink" in item for item in plan.conflicts))
                with self.assertRaises(kit.KitError):
                    kit.apply_plan(plan)
                self.assertEqual(list(outside.iterdir()), [])
                link.unlink()
                shutil.rmtree(self.project / ".agents", ignore_errors=True)

    def test_broken_destination_symlink_is_a_conflict(self):
        (self.project / ".agent-kit").symlink_to(self.base / "does not exist")
        self.assertTrue(any("destination symlink" in item for item in self.plan().conflicts))

    def test_source_symlinks_are_rejected(self):
        outside = self.base / "outside.txt"
        outside.write_text("must not copy", encoding="utf-8")
        for relative in ("skills/sample/linked.txt", "templates/MANUAL.md", "VERSION"):
            with self.subTest(relative=relative):
                path = self.source / relative
                previous = path.read_bytes() if path.exists() else None
                if path.exists():
                    path.unlink()
                path.symlink_to(outside)
                with self.assertRaisesRegex(kit.KitError, "source symlink"):
                    self.plan()
                path.unlink()
                if previous is not None:
                    path.write_bytes(previous)
        self.assertEqual(self.snapshot(), {})

    def test_source_directory_symlinks_are_rejected(self):
        original = self.source / "skills/sample/references"
        outside = self.base / "external references"
        original.rename(outside)
        original.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(kit.KitError, "source symlink"):
            self.plan()

    def test_nonregular_source_is_rejected_without_opening(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO unavailable on this platform")
        os.mkfifo(self.source / "skills/sample/pipe")
        with self.assertRaisesRegex(kit.KitError, "not a regular file or directory"):
            self.plan()

    def test_unsafe_skill_names_and_duplicates_are_rejected(self):
        for names in (["../outside"], ["/absolute"], ["a/b"], ["a\\b"], [".."], [""],
                      ["bad name"], ["sample", "sample"], [42]):
            with self.subTest(names=names):
                self.write("profiles.json", json.dumps({"build": names}))
                with self.assertRaises(kit.KitError):
                    self.plan()
        self.assertEqual(self.snapshot(), {})

    def test_source_path_escape_is_rejected(self):
        for relative in (Path("../outside"), self.base / "absolute"):
            with self.subTest(relative=relative), self.assertRaisesRegex(kit.KitError, "escapes kit"):
                kit.source_file(self.source, relative)

    def test_existing_skill_and_metadata_are_all_preflighted(self):
        (self.project / ".agents/skills/sample").mkdir(parents=True)
        (self.project / ".claude/skills").mkdir(parents=True)
        (self.project / ".claude/skills/sample").write_text("keep", encoding="utf-8")
        (self.project / ".agent-kit").mkdir()
        before = self.snapshot()
        plan = self.plan()
        for relative in (".agents/skills/sample", ".claude/skills/sample", ".agent-kit"):
            self.assertTrue(any(relative in conflict for conflict in plan.conflicts))
        with self.assertRaises(kit.KitError):
            kit.apply_plan(plan)
        self.assertEqual(self.snapshot(), before)

    def test_partial_failure_rolls_back_and_preserves_existing_parents(self):
        keep = self.project / ".agents/skills/existing/keep.txt"
        keep.parent.mkdir(parents=True)
        keep.write_text("keep", encoding="utf-8")
        before = self.snapshot()
        plan = self.plan(with_instructions=True)
        original_chmod = Path.chmod
        calls = []

        def fail_second_chmod(path, mode, **kwargs):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("injected write failure")
            return original_chmod(path, mode, **kwargs)

        with mock.patch.object(Path, "chmod", fail_second_chmod):
            with self.assertRaisesRegex(kit.KitError, "injected write failure"):
                kit.apply_plan(plan)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.snapshot(), before)

    def test_apply_rechecks_conflict_added_after_plan(self):
        plan = self.plan()
        (self.project / ".agent-kit").write_text("created after plan", encoding="utf-8")
        before = self.snapshot()
        with self.assertRaises(kit.KitError):
            kit.apply_plan(plan)
        self.assertEqual(self.snapshot(), before)

    def test_repeat_install_is_refused_without_mutation(self):
        kit.apply_plan(self.plan())
        before = self.snapshot()
        code, output = self.cli("--apply")
        self.assertEqual(code, 1)
        self.assertIn("Conflicts", output)
        self.assertEqual(self.snapshot(), before)

    def test_actual_build_journal_bundle_runs_from_unrelated_directory(self):
        shutil.copytree(ROOT / "skills/build-journal", self.source / "skills/build-journal")
        self.write("profiles.json", json.dumps({"build": ["build-journal"]}))
        kit.apply_plan(self.plan())
        shutil.rmtree(self.source)
        unrelated = self.base / "unrelated cwd"
        unrelated.mkdir()
        for provider in (".claude", ".agents"):
            with self.subTest(provider=provider):
                helper = self.project / provider / "skills/build-journal/journal.py"
                journal = self.base / (provider + " journal")
                result = subprocess.run([sys.executable, str(helper), "init", str(journal),
                                         "--title", "Portable test"], cwd=str(unrelated),
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Portable test", (journal / "BUILD.md").read_text())
                self.assertTrue((journal / "PROCESS.md").is_file())
                self.assertTrue((journal / "decisions").is_dir())


class DoctorTests(unittest.TestCase):
    def test_missing_tools_are_optional_and_do_not_launch_commands(self):
        output = io.StringIO()
        with mock.patch.object(kit.shutil, "which", return_value=None), \
                mock.patch.object(kit.subprocess, "run") as run, contextlib.redirect_stdout(output):
            self.assertEqual(kit.main(["doctor"]), 0)
        run.assert_not_called()
        self.assertIn("Python:", output.getvalue())
        self.assertEqual(output.getvalue().count("not found (optional)"), 7)
        self.assertIn("not a full readiness guarantee", output.getvalue())

    def test_version_checks_are_bounded_and_hide_error_output(self):
        output = io.StringIO()
        result = subprocess.CompletedProcess([], 1, "", "private authentication error")
        with mock.patch.object(kit.shutil, "which", side_effect=lambda name: "/bin/" + name), \
                mock.patch.object(kit.subprocess, "run", return_value=result) as run, \
                contextlib.redirect_stdout(output):
            self.assertEqual(kit.doctor(), 0)
        self.assertEqual(run.call_count, 7)
        for call in run.call_args_list:
            self.assertEqual(call.args[0][1:], ["--version"])
            self.assertEqual(call.kwargs["timeout"], 3)
            self.assertNotIn("env", call.kwargs)
        self.assertNotIn("private authentication", output.getvalue())

    def test_version_timeout_does_not_fail_doctor(self):
        output = io.StringIO()
        with mock.patch.object(kit.shutil, "which", return_value="/bin/optional"), \
                mock.patch.object(kit.subprocess, "run", side_effect=subprocess.TimeoutExpired("tool", 3)), \
                contextlib.redirect_stdout(output):
            self.assertEqual(kit.doctor(), 0)
        self.assertEqual(output.getvalue().count("version check timed out"), 7)


if __name__ == "__main__":
    unittest.main()
