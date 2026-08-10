from __future__ import annotations

import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import run_lab


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class StudentWorkflowTests(unittest.TestCase):
    def test_all_withheld_results_echo_their_frozen_receipt_and_lineage(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lora-energy-workflow-") as directory:
            isolated = Path(directory) / "lora-energy-lab"
            shutil.copytree(
                PACKAGE_ROOT,
                isolated,
                ignore=shutil.ignore_patterns(".venv", "artifacts", "__pycache__", "*.pyc"),
            )
            (isolated / "artifacts").mkdir()

            original_root = run_lab.PACKAGE_ROOT
            run_lab.PACKAGE_ROOT = isolated
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_lab.run_case("A", "baseline")
                    self._replace(isolated, "REST_DURING_GAP = SLEEP", "REST_DURING_GAP = WAIT")
                    a_frozen = run_lab.run_case("A", "candidate", freeze=True)
                    a_withheld = run_lab.run_case("A", "hidden")

                    run_lab.run_case("B", "trace-a-baseline")
                    self._replace(isolated, "STABLE_STEPS = 2", "STABLE_STEPS = 1")
                    b_frozen = run_lab.run_case("B", "trace-a-candidate", freeze=True)
                    b_withheld = run_lab.run_case("B", "trace-b")

                    run_lab.run_case("C", "baseline")
                    self._replace(isolated, "URGENT_MARGIN_S = 20", "URGENT_MARGIN_S = 5")
                    run_lab.run_case("C", "candidate")
                    self._replace(isolated, "URGENT_MARGIN_S = 5", "URGENT_MARGIN_S = 30")
                    c_frozen = run_lab.run_case("C", "revision", freeze=True)
                    c_withheld = run_lab.run_case("C", "surprise")
            finally:
                run_lab.PACKAGE_ROOT = original_root

            for frozen, withheld in (
                (a_frozen, a_withheld),
                (b_frozen, b_withheld),
                (c_frozen, c_withheld),
            ):
                self.assertEqual(withheld["policy"]["policy_sha256"], frozen["policy"]["policy_sha256"])
                self.assertEqual(
                    withheld["policy"]["predecessor_policy_sha256"],
                    frozen["policy"]["predecessor_policy_sha256"],
                )
                self.assertEqual(
                    withheld["policy"]["freeze_receipt_sha256"],
                    frozen["policy"]["freeze_receipt_sha256"],
                )

    def _replace(self, package_root: Path, before: str, after: str) -> None:
        policy_path = package_root / "student_policy.py"
        source = policy_path.read_text(encoding="utf-8")
        self.assertEqual(source.count(before), 1)
        policy_path.write_text(source.replace(before, after), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
