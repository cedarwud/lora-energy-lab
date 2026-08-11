from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_lab


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class RecoveryCommandTests(unittest.TestCase):
    def _isolated_package(self) -> Path:
        temporary = tempfile.TemporaryDirectory(prefix="lora-energy-recovery-")
        isolated = Path(temporary.name) / PACKAGE_ROOT.name
        shutil.copytree(
            PACKAGE_ROOT,
            isolated,
            ignore=shutil.ignore_patterns(".venv", "artifacts", "__pycache__", "*.pyc"),
        )
        artifacts = isolated / "artifacts"
        artifacts.mkdir()
        shutil.copyfile(PACKAGE_ROOT / "artifacts" / ".gitkeep", artifacts / ".gitkeep")
        self.addCleanup(temporary.cleanup)
        return isolated

    def _run_cli(self, package_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, "run_lab.py", *arguments],
            cwd=package_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def _assert_json_success(self, process: subprocess.CompletedProcess[str]) -> dict:
        self.assertEqual(
            process.returncode,
            0,
            f"command failed\nstdout={process.stdout}\nstderr={process.stderr}",
        )
        return json.loads(process.stdout)

    def _artifact_snapshot(self, package_root: Path) -> dict[str, bytes]:
        artifacts = package_root / "artifacts"
        return {
            path.relative_to(artifacts).as_posix(): path.read_bytes()
            for path in artifacts.rglob("*")
            if path.is_file()
        }

    def _replace_policy_value(self, package_root: Path, before: str, after: str) -> None:
        policy = package_root / "student_policy.py"
        source = policy.read_text(encoding="utf-8")
        self.assertEqual(source.count(before), 1)
        policy.write_bytes(source.replace(before, after).encode("utf-8"))

    def _prepare_lab_a_freeze(self, package_root: Path) -> tuple[Path, dict]:
        self._replace_policy_value(
            package_root, "REST_DURING_GAP = SLEEP", "REST_DURING_GAP = WAIT"
        )

        process = self._run_cli(package_root, "run", "--lab", "A", "--case", "candidate", "--freeze")
        self._assert_json_success(process)

        checkpoint = package_root / "artifacts" / "checkpoints" / "lab-a-frozen.json"
        receipt = json.loads(checkpoint.read_text(encoding="utf-8"))
        archive = package_root / "artifacts" / "receipts" / f"{receipt['receipt_sha256'].replace(':', '_')}.json"
        self.assertTrue(archive.is_file())
        return checkpoint, receipt

    def _prepare_lab_c_candidate(self, package_root: Path) -> Path:
        self._prepare_lab_a_freeze(package_root)
        self._replace_policy_value(package_root, "STABLE_STEPS = 2", "STABLE_STEPS = 1")
        self._assert_json_success(
            self._run_cli(
                package_root,
                "run",
                "--lab",
                "B",
                "--case",
                "trace-a-candidate",
                "--freeze",
            )
        )
        self._replace_policy_value(package_root, "URGENT_MARGIN_S = 20", "URGENT_MARGIN_S = 5")
        self._assert_json_success(
            self._run_cli(package_root, "run", "--lab", "C", "--case", "candidate")
        )
        return package_root / "artifacts" / "checkpoints" / "lab-c-candidate.py"

    def test_status_reports_clean_release_checkpoint_without_touching_artifacts(self) -> None:
        package_root = self._isolated_package()
        before = self._artifact_snapshot(package_root)

        result = self._assert_json_success(self._run_cli(package_root, "status"))

        self.assertEqual(result["command"], "status")
        self.assertEqual(result["policy_api_version"], "lora-energy-policy-v1")
        self.assertTrue(result["current_policy_valid"])
        self.assertEqual(result["available_checkpoint_roles"], ["release-default"])
        self.assertTrue(result["artifacts_untouched"])
        self.assertEqual(self._artifact_snapshot(package_root), before)

    def test_reset_policy_restores_release_default_and_leaves_artifacts_untouched(self) -> None:
        package_root = self._isolated_package()
        policy = package_root / "student_policy.py"
        source = policy.read_text(encoding="utf-8")
        policy.write_bytes(source.replace("REST_DURING_GAP = SLEEP", "REST_DURING_GAP = WAIT").encode("utf-8"))
        before = self._artifact_snapshot(package_root)

        result = self._assert_json_success(self._run_cli(package_root, "reset-policy"))

        self.assertEqual(result["checkpoint"], "release-default")
        self.assertEqual(policy.read_bytes(), (package_root / "student_policy.baseline.py").read_bytes())
        self.assertEqual(self._artifact_snapshot(package_root), before)

    def test_allowed_freeze_checkpoint_restore_does_not_rewrite_artifacts(self) -> None:
        package_root = self._isolated_package()
        checkpoint, receipt = self._prepare_lab_a_freeze(package_root)
        policy = package_root / "student_policy.py"
        policy.write_bytes((package_root / "student_policy.baseline.py").read_bytes())
        before = self._artifact_snapshot(package_root)

        result = self._assert_json_success(
            self._run_cli(package_root, "restore", "--checkpoint", "lab-a-frozen")
        )

        self.assertEqual(result["checkpoint"], "lab-a-frozen")
        self.assertEqual(result["receipt_sha256"], receipt["receipt_sha256"])
        self.assertEqual(policy.read_bytes(), (package_root / "artifacts" / "checkpoints" / "lab-a-frozen.py").read_bytes())
        self.assertEqual(policy.read_bytes(), checkpoint.with_suffix(".py").read_bytes())
        self.assertEqual(self._artifact_snapshot(package_root), before)

    def test_tampered_or_missing_content_addressed_receipt_fails_closed(self) -> None:
        for mode in ("tampered", "missing"):
            with self.subTest(mode=mode):
                package_root = self._isolated_package()
                _checkpoint, receipt = self._prepare_lab_a_freeze(package_root)
                policy = package_root / "student_policy.py"
                active_before = policy.read_bytes()
                archive = package_root / "artifacts" / "receipts" / f"{receipt['receipt_sha256'].replace(':', '_')}.json"
                if mode == "tampered":
                    tampered = json.loads(archive.read_text(encoding="utf-8"))
                    tampered["lab_id"] = "B"
                    archive.write_text(json.dumps(tampered), encoding="utf-8")
                else:
                    archive.unlink()
                before = self._artifact_snapshot(package_root)

                process = self._run_cli(package_root, "restore", "--checkpoint", "lab-a-frozen")

                self.assertEqual(process.returncode, 2)
                self.assertIn("ERROR", process.stderr)
                self.assertEqual(policy.read_bytes(), active_before)
                self.assertEqual(self._artifact_snapshot(package_root), before)

    def test_lab_c_candidate_requires_full_api_and_frozen_predecessor_validation(self) -> None:
        for mode in ("invalid-api", "outside-lab-c"):
            with self.subTest(mode=mode):
                package_root = self._isolated_package()
                checkpoint = self._prepare_lab_c_candidate(package_root)
                source = checkpoint.read_text(encoding="utf-8")
                if mode == "invalid-api":
                    self.assertEqual(source.count("URGENT_MARGIN_S = 5"), 1)
                    source = source.replace("URGENT_MARGIN_S = 5", "URGENT_MARGIN_S = 61")
                else:
                    self.assertEqual(source.count("REST_DURING_GAP = WAIT"), 1)
                    source = source.replace("REST_DURING_GAP = WAIT", "REST_DURING_GAP = SLEEP")
                checkpoint.write_bytes(source.encode("utf-8"))
                policy = package_root / "student_policy.py"
                policy.write_bytes((package_root / "student_policy.baseline.py").read_bytes())
                active_before = policy.read_bytes()
                artifacts_before = self._artifact_snapshot(package_root)

                status = self._assert_json_success(self._run_cli(package_root, "status"))
                candidate = next(
                    item
                    for item in status["available_checkpoints"]
                    if item["role"] == "lab-c-candidate"
                )
                self.assertFalse(candidate["available"])
                process = self._run_cli(
                    package_root, "restore", "--checkpoint", "lab-c-candidate"
                )

                self.assertEqual(process.returncode, 2)
                self.assertTrue(process.stderr.startswith("ERROR PolicyError:"))
                self.assertNotIn("Traceback", process.stderr)
                self.assertEqual(policy.read_bytes(), active_before)
                self.assertEqual(self._artifact_snapshot(package_root), artifacts_before)

    def test_unknown_checkpoint_uses_error_contract_without_writing(self) -> None:
        package_root = self._isolated_package()
        policy = package_root / "student_policy.py"
        active_before = policy.read_bytes()
        artifacts_before = self._artifact_snapshot(package_root)

        process = self._run_cli(
            package_root, "restore", "--checkpoint", "arbitrary-local-file"
        )

        self.assertEqual(process.returncode, 2)
        self.assertTrue(process.stderr.startswith("ERROR PolicyError:"))
        self.assertNotIn("Traceback", process.stderr)
        self.assertEqual(policy.read_bytes(), active_before)
        self.assertEqual(self._artifact_snapshot(package_root), artifacts_before)

    def test_non_object_freeze_receipt_uses_error_contract_without_writing(self) -> None:
        package_root = self._isolated_package()
        checkpoint, _receipt = self._prepare_lab_a_freeze(package_root)
        checkpoint.write_bytes(b"null\n")
        policy = package_root / "student_policy.py"
        active_before = policy.read_bytes()
        artifacts_before = self._artifact_snapshot(package_root)

        process = self._run_cli(
            package_root, "restore", "--checkpoint", "lab-a-frozen"
        )

        self.assertEqual(process.returncode, 2)
        self.assertTrue(process.stderr.startswith("ERROR PolicyError:"))
        self.assertNotIn("Traceback", process.stderr)
        self.assertEqual(policy.read_bytes(), active_before)
        self.assertEqual(self._artifact_snapshot(package_root), artifacts_before)

    def test_restore_rolls_back_active_policy_when_post_write_validation_fails(self) -> None:
        package_root = self._isolated_package()
        self._prepare_lab_a_freeze(package_root)
        policy = package_root / "student_policy.py"
        policy.write_bytes((package_root / "student_policy.baseline.py").read_bytes())
        active_before = policy.read_bytes()
        artifacts_before = self._artifact_snapshot(package_root)

        with mock.patch.object(run_lab, "PACKAGE_ROOT", package_root):
            with mock.patch.object(
                run_lab,
                "_policy_api_validation",
                side_effect=run_lab.PolicyError("injected post-write validation failure"),
            ):
                with self.assertRaises(run_lab.PolicyError):
                    run_lab.restore_policy("lab-a-frozen")

        self.assertEqual(policy.read_bytes(), active_before)
        self.assertEqual(self._artifact_snapshot(package_root), artifacts_before)


if __name__ == "__main__":
    unittest.main()
