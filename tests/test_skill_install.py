from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from install_skill import validate_target_location  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_skill.py"


class SkillInstallTests(unittest.TestCase):
    def run_installer(self, target: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(INSTALLER), str(target), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def test_clean_install_excludes_repository_and_cache_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "research-paper-suite"

            result = self.run_installer(target)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((target / "SKILL.md").exists())
            self.assertTrue((target / "skill_manifest.yml").exists())
            self.assertFalse((target / ".git").exists())
            self.assertFalse((target / ".pytest_cache").exists())
            self.assertEqual(list(target.rglob("__pycache__")), [])

    def test_existing_target_is_rejected_without_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "research-paper-suite"
            target.mkdir(parents=True)
            (target / "old-file.txt").write_text("old", encoding="utf-8")

            result = self.run_installer(target)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to merge", result.stdout + result.stderr)
            self.assertTrue((target / "old-file.txt").exists())

    def test_replace_creates_backup_and_removes_stale_files_from_new_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            target = parent / "research-paper-suite"
            target.mkdir(parents=True)
            (target / "old-file.txt").write_text("old", encoding="utf-8")

            result = self.run_installer(target, "--replace")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((target / "SKILL.md").exists())
            self.assertFalse((target / "old-file.txt").exists())
            backups = list(parent.glob("research-paper-suite.backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertTrue((backups[0] / "old-file.txt").exists())

    def test_rejects_install_targets_that_overlap_the_package_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            validate_target_location(ROOT, ROOT / "nested-install")
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            validate_target_location(ROOT, ROOT.parent)


if __name__ == "__main__":
    unittest.main()
