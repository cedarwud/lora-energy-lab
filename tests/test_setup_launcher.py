from __future__ import annotations

import os
import re
import shutil
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

    def test_docs_show_manual_platform_specific_venv_flow(self) -> None:
        for document in (self.english, self.chinese):
            for marker in (
                "### Windows",
                "### Linux",
                "### macOS",
                "& $python311 -m venv .venv",
                "Activate.ps1",
                "source .venv/bin/activate",
                "requirements-lock.txt",
                "verify_setup.py",
                "course.cmd",
                "Ubuntu 24.04",
            ):
                self.assertIn(marker, document)

            create_at = document.index("& $python311 -m venv .venv")
            activate_at = document.index("Activate.ps1", create_at)
            install_at = document.index("python -m pip install", activate_at)
            self.assertLess(create_at, activate_at)
            self.assertLess(activate_at, install_at)

            setup_at = document.index("\n## 1.") + 1
            next_section_at = document.index("\n## 2.", setup_at) + 1
            setup = document[setup_at:next_section_at]
            windows_at = setup.index("### Windows")
            linux_at = setup.index("### Linux")
            macos_at = setup.index("### macOS")
            shortcut_at = setup.index("### Setup", macos_at)
            windows = setup[windows_at:linux_at]
            linux = setup[linux_at:macos_at]
            macos = setup[macos_at:shortcut_at]

            def assert_in_order(text: str, *items: str) -> None:
                position = -1
                for item in items:
                    position = text.find(item, position + 1)
                    self.assertNotEqual(position, -1, item)

            assert_in_order(
                windows,
                "py -3.11 --version",
                "uv python install 3.11",
                "& $python311 --version",
                "& $python311 -m venv .venv",
                "Activate.ps1",
                "python -m pip install",
            )
            assert_in_order(
                linux,
                "command -v python3.11",
                "python3.11 --version",
                "uv python install 3.11",
                'PYTHON_BIN="$(uv python find 3.11)"',
                '"$PYTHON_BIN" -m venv .venv',
                "source .venv/bin/activate",
                "python -m pip install",
            )
            assert_in_order(
                macos,
                "python3.11 --version",
                '"$PYTHON_BIN" -m venv .venv',
                "source .venv/bin/activate",
                "python -m pip install",
            )
            self.assertNotRegex(
                linux,
                r"(?m)^\s*(?:sudo\s+)?apt(?:-get)?\s+install\b[^\n]*python3\.11",
            )

    def test_docs_omit_checksum_and_role_based_prose(self) -> None:
        for document in (self.english, self.chinese):
            self.assertNotIn(".sha256", document)
            self.assertNotIn("checksum", document.lower())
            self.assertNotIn("apt-cache policy python3.11", document)

        def markdown_prose(document: str) -> str:
            without_fences = re.sub(r"```.*?```", "", document, flags=re.DOTALL)
            return re.sub(r"`[^`\n]*`", "", without_fences)

        self.assertNotRegex(
            markdown_prose(self.english).lower(),
            r"\b(?:learner|instructor|teacher|student)s?\b",
        )
        for word in ("老師", "教師", "學生", "學員"):
            self.assertNotIn(word, markdown_prose(self.chinese))

    def test_docs_explain_verify_and_do_not_repeat_it_after_setup(self) -> None:
        for document in (self.english, self.chinese):
            shortcut_at = document.index("### Setup")
            purpose_at = document.index("\n### ", shortcut_at + 1)
            shortcut = document[shortcut_at:purpose_at]

            self.assertNotIn("course.cmd verify", shortcut)
            self.assertNotIn("course.sh verify", shortcut)
            self.assertIn("verify-receipt.json", document[purpose_at:])
            self.assertIn("verify_setup.py", document[purpose_at:])
            self.assertIn("result.json", document[purpose_at:])
            self.assertIn("endpoint-replay.json", document[purpose_at:])

    def test_posix_setup_has_valid_shell_syntax_without_running_it(self) -> None:
        if os.name == "nt":
            self.skipTest("POSIX shell syntax is checked on POSIX environments")

        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("Bash is not installed")

        probe = subprocess.run(
            [bash, "-c", ":"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if probe.returncode != 0:
            self.skipTest("Bash is installed but unavailable in this environment")

        subprocess.run([bash, "-n", str(PACKAGE_ROOT / "setup.sh")], check=True)


if __name__ == "__main__":
    unittest.main()
