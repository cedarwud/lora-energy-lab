from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class SetupLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.posix = (PACKAGE_ROOT / "setup.sh").read_text(encoding="utf-8")
        cls.windows = (PACKAGE_ROOT / "setup.cmd").read_text(encoding="utf-8")
        cls.english = (PACKAGE_ROOT / "README.en.md").read_text(encoding="utf-8")
        cls.chinese = (PACKAGE_ROOT / "README.zh-TW.md").read_text(encoding="utf-8")

    def test_posix_requires_311_before_venv(self) -> None:
        self.assertIn('PYTHON_BIN="${PYTHON_BIN:-python3.11}"', self.posix)
        self.assertIn("3.11.*", self.posix)
        self.assertIn('"$PYTHON_BIN" -m venv', self.posix)
        self.assertIn("requirements-lock.txt", self.posix)
        self.assertNotIn('PYTHON_BIN="${PYTHON_BIN:-python3}"', self.posix)
        self.assertFalse(any(line.strip().startswith("uv python install") for line in self.posix.splitlines()))

    def test_windows_prefers_py311_and_checks_existing_venv(self) -> None:
        self.assertIn('set "PYTHON_BIN=py -3.11"', self.windows)
        self.assertIn("sys.version_info[:2] == (3, 11)", self.windows)
        self.assertIn('existing %ROOT_DIR%.venv', self.windows)
        self.assertNotIn('set "PYTHON_BIN=py -3"', [line.strip() for line in self.windows.splitlines()])
        self.assertFalse(any(line.strip().startswith("uv python install") for line in self.windows.splitlines()))

    def test_docs_show_explicit_uv_recovery(self) -> None:
        for document in (self.english, self.chinese):
            self.assertIn("uv python install 3.11", document)
            self.assertIn("uv python find 3.11", document)
            self.assertIn("bash setup.sh", document)

    def test_posix_setup_has_valid_shell_syntax_without_running_it(self) -> None:
        subprocess.run(["bash", "-n", str(PACKAGE_ROOT / "setup.sh")], check=True)


if __name__ == "__main__":
    unittest.main()
