"""Content-addressed result, freeze, and checkpoint storage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .canonical_json import hash_bytes, load_file, write_file
from .contracts import FREEZE_VERSION, SCENARIO_ID, WRAPPER_VERSION, UPSTREAM_COMMIT
from .validation import validate_freeze_receipt, validate_result


def safe_hash_name(value: str) -> str:
    return value.replace(":", "_")


def artifacts_root(package_root: str | Path) -> Path:
    return Path(package_root) / "artifacts"


def write_result(package_root: str | Path, result: dict[str, Any]) -> Path:
    validate_result(result)
    root = artifacts_root(package_root)
    target = root / safe_hash_name(result["run_id"]) / "result.json"
    write_file(target, result)
    return target


def receipt_path(package_root: str | Path, receipt_sha256: str) -> Path:
    return artifacts_root(package_root) / "receipts" / f"{safe_hash_name(receipt_sha256)}.json"


def checkpoint_path(package_root: str | Path, role: str) -> Path:
    return artifacts_root(package_root) / "checkpoints" / f"{role}.json"


def checkpoint_policy_path(package_root: str | Path, role: str) -> Path:
    return artifacts_root(package_root) / "checkpoints" / f"{role}.py"


def make_freeze_receipt(
    scenario: dict[str, Any],
    lab_id: str,
    frozen_case_id: str,
    active_block_id: str,
    policy_sha256: str,
    predecessor_policy_sha256: str,
    lock_sha256: str,
    seed_role: str,
    seed: int,
) -> dict[str, Any]:
    receipt = {
        "schema_version": FREEZE_VERSION,
        "scenario_id": SCENARIO_ID,
        "scenario_sha256": scenario["scenario_sha256"],
        "scenario_anchor_sha256": scenario["scenario_anchor_sha256"],
        "lab_id": lab_id,
        "frozen_case_id": frozen_case_id,
        "active_block_id": active_block_id,
        "policy_api_version": "lora-energy-policy-v1",
        "policy_sha256": policy_sha256,
        "predecessor_policy_sha256": predecessor_policy_sha256,
        "upstream_commit": UPSTREAM_COMMIT,
        "wrapper_version": WRAPPER_VERSION,
        "lock_sha256": lock_sha256,
        "seed_role": seed_role,
        "seed": seed,
        "canonicalization": "RFC8785",
        "receipt_sha256": "sha256:" + "0" * 64,
    }
    from .canonical_json import hash_value

    receipt["receipt_sha256"] = hash_value({key: value for key, value in receipt.items() if key != "receipt_sha256"})
    validate_freeze_receipt(receipt)
    return receipt


def write_freeze(
    package_root: str | Path,
    receipt: dict[str, Any],
    policy_bytes: bytes,
    role: str,
) -> tuple[Path, Path]:
    validate_freeze_receipt(receipt)
    root = artifacts_root(package_root)
    target = receipt_path(package_root, receipt["receipt_sha256"])
    write_file(target, receipt)
    policy_target = checkpoint_policy_path(package_root, role)
    policy_target.parent.mkdir(parents=True, exist_ok=True)
    policy_target.write_bytes(policy_bytes)
    checkpoint = checkpoint_path(package_root, role)
    write_file(checkpoint, receipt)
    return target, policy_target


def read_receipt(package_root: str | Path, role: str) -> dict[str, Any]:
    path = checkpoint_path(package_root, role)
    try:
        receipt = load_file(path)
    except OSError as exc:
        raise FileNotFoundError(f"missing {role} freeze receipt; run the named --freeze command first") from exc
    return validate_freeze_receipt(receipt)


def read_policy_checkpoint(package_root: str | Path, role: str) -> bytes:
    path = checkpoint_policy_path(package_root, role)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise FileNotFoundError(f"missing {role} policy checkpoint") from exc


def write_candidate_checkpoint(package_root: str | Path, role: str, policy_bytes: bytes) -> Path:
    path = checkpoint_policy_path(package_root, role)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(policy_bytes)
    return path
