#!/usr/bin/env python3
"""LoRa energy lab runner command surface."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from lora_energy_lab.canonical_json import CanonicalJSONError, hash_bytes, hash_file, load_file, write_file
from lora_energy_lab.contracts import (
    BLOCK_IDS,
    CLAIM_BOUNDARY,
    ContractError,
    ENGINE_MODE,
    POLICY_API_VERSION,
    SCENARIO_ID,
    WRAPPER_VERSION,
    case_for,
    load_scenario,
)
from lora_energy_lab.engine import SimulationError, run_simulation
from lora_energy_lab.replay import make_endpoint_replay, write_endpoint_replay
from lora_energy_lab.policy_api import (
    BASELINE_POLICY_SHA256,
    PolicyError,
    active_block_for_lab,
    compare_outside,
    load_policy,
    parse_policy_source,
    policy_path,
    read_policy,
    baseline_policy_path,
)
from lora_energy_lab.result_writer import (
    checkpoint_policy_path,
    make_freeze_receipt,
    read_policy_checkpoint,
    read_receipt,
    receipt_path,
    write_candidate_checkpoint,
    write_freeze,
    write_result,
)
from lora_energy_lab.validation import ResultError, validate_freeze_receipt, validate_result


def _python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _lock_sha256() -> str:
    return hash_file(PACKAGE_ROOT / "requirements-lock.txt")


def _scenario() -> dict[str, Any]:
    return load_scenario(PACKAGE_ROOT / "scenarios" / f"{SCENARIO_ID}.json")


# Recovery targets are deliberately a closed set. A command can return to a
# known policy stage, but cannot copy an arbitrary path into the active policy
# file.
RECOVERY_CHECKPOINT_ROLES = (
    "release-default",
    "lab-a-frozen",
    "lab-b-frozen",
    "lab-c-candidate",
    "lab-c-frozen",
)
_FROZEN_ROLE_EXPECTATIONS = {
    "lab-a-frozen": ("A", "candidate", BLOCK_IDS["A"]),
    "lab-b-frozen": ("B", "trace-a-candidate", BLOCK_IDS["B"]),
    "lab-c-frozen": ("C", "revision", BLOCK_IDS["C"]),
}


def _validated_policy_surface_at_path(path: Path):
    """Load one policy through every active-block entry point."""
    surface = None
    for block in BLOCK_IDS.values():
        loaded, _function = load_policy(path, block)
        if surface is None:
            surface = loaded
        elif loaded.policy_sha256 != surface.policy_sha256:
            raise PolicyError("policy API returned inconsistent source hashes")
    if surface is None:  # pragma: no cover - BLOCK_IDS is a fixed contract
        raise PolicyError("policy API has no editable blocks")
    return surface


def _policy_api_validation(path: Path):
    """Validate the active policy path after an atomic replacement."""
    return _validated_policy_surface_at_path(path)


def _policy_source_api_validation(source: bytes, label: str):
    """Validate checkpoint bytes completely before replacing the active policy."""
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="lora-energy-policy-validation-", suffix=".py"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(source)
        try:
            return _validated_policy_surface_at_path(temporary)
        except PolicyError as exc:
            raise PolicyError(f"{label} failed policy API validation: {exc}") from exc
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _receipt_archive(package_root: Path, receipt: dict[str, Any]) -> None:
    """Require the content-addressed receipt copy to match its checkpoint."""
    archived_path = receipt_path(package_root, receipt["receipt_sha256"])
    try:
        archived = load_file(archived_path)
    except OSError as exc:
        raise FileNotFoundError(
            f"missing content-addressed receipt for {archived_path.name}"
        ) from exc
    if not isinstance(archived, dict):
        raise PolicyError("content-addressed freeze receipt is not an object")
    if archived != receipt:
        raise PolicyError("freeze receipt checkpoint differs from its content-addressed receipt")
    validate_freeze_receipt(archived)


def _validated_recovery_checkpoint(role: str) -> dict[str, Any]:
    """Return a validated recovery source without changing student_policy.py."""
    if role not in RECOVERY_CHECKPOINT_ROLES:
        raise PolicyError(
            f"unknown recovery checkpoint {role!r}; choose one of {', '.join(RECOVERY_CHECKPOINT_ROLES)}"
        )

    if role == "release-default":
        path = baseline_policy_path(PACKAGE_ROOT)
        try:
            source = path.read_bytes()
        except OSError as exc:
            raise FileNotFoundError("missing packaged student_policy.baseline.py") from exc
        surface = _policy_source_api_validation(source, path.name)
        if surface.policy_sha256 != BASELINE_POLICY_SHA256:
            raise PolicyError("packaged student_policy.baseline.py has been modified")
        return {
            "role": role,
            "kind": "packaged-baseline",
            "source": source,
            "surface": surface,
            "receipt": None,
        }

    if role == "lab-c-candidate":
        path = checkpoint_policy_path(PACKAGE_ROOT, role)
        try:
            source = path.read_bytes()
        except OSError as exc:
            raise FileNotFoundError(f"missing {role} policy checkpoint") from exc
        surface = _policy_source_api_validation(source, path.name)
        predecessor = _validated_recovery_checkpoint("lab-b-frozen")
        compare_outside(surface, predecessor["surface"], BLOCK_IDS["C"])
        if surface.policy_sha256 == predecessor["surface"].policy_sha256:
            raise PolicyError("lab-c-candidate must differ from lab-b-frozen in the marked Lab C block")
        return {
            "role": role,
            "kind": "candidate-policy-checkpoint",
            "source": source,
            "surface": surface,
            "receipt": None,
        }

    expected = _FROZEN_ROLE_EXPECTATIONS[role]
    try:
        receipt = read_receipt(PACKAGE_ROOT, role)
    except FileNotFoundError:
        raise
    except (CanonicalJSONError, ResultError, OSError, TypeError, KeyError) as exc:
        raise PolicyError(f"invalid {role} freeze receipt: {exc}") from exc
    scenario = _scenario()
    if receipt["scenario_sha256"] != scenario["scenario_sha256"]:
        raise PolicyError(f"{role} receipt scenario hash does not match the packaged scenario")
    if receipt["scenario_anchor_sha256"] != scenario["scenario_anchor_sha256"]:
        raise PolicyError(f"{role} receipt anchor hash does not match the packaged scenario")
    if receipt["lock_sha256"] != _lock_sha256():
        raise PolicyError(f"{role} receipt lock hash does not match requirements-lock.txt")
    if (receipt["lab_id"], receipt["frozen_case_id"], receipt["active_block_id"]) != expected:
        raise PolicyError(f"{role} receipt role metadata does not match its checkpoint role")
    _receipt_archive(PACKAGE_ROOT, receipt)

    policy_path_for_role = checkpoint_policy_path(PACKAGE_ROOT, role)
    try:
        source = policy_path_for_role.read_bytes()
    except OSError as exc:
        raise FileNotFoundError(f"missing {role} policy checkpoint") from exc
    surface = _policy_source_api_validation(source, policy_path_for_role.name)
    if surface.policy_sha256 != receipt["policy_sha256"]:
        raise PolicyError(f"{role} policy checkpoint hash does not match its freeze receipt")
    return {
        "role": role,
        "kind": "freeze-checkpoint",
        "source": source,
        "surface": surface,
        "receipt": receipt,
    }


def _fsync_directory(directory: Path) -> None:
    """Best-effort directory sync for POSIX; harmless on unsupported filesystems."""
    flags = getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(str(directory), os.O_RDONLY | flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _atomic_write_bytes(path: Path, source: bytes) -> None:
    """Write bytes through a same-directory temporary file and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(source)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def restore_policy(checkpoint: str) -> dict[str, Any]:
    """Restore a validated checkpoint and leave all result evidence untouched."""
    selected = _validated_recovery_checkpoint(checkpoint)
    target = policy_path(PACKAGE_ROOT)
    try:
        previous = target.read_bytes()
    except FileNotFoundError:
        previous = None
    except OSError as exc:
        raise PolicyError(f"cannot read current student_policy.py: {exc}") from exc

    _atomic_write_bytes(target, selected["source"])
    try:
        restored = _policy_api_validation(target)
        if restored.policy_sha256 != selected["surface"].policy_sha256:
            raise PolicyError("restored policy hash changed during policy API validation")
    except Exception as exc:
        try:
            if previous is None:
                target.unlink(missing_ok=True)
            else:
                _atomic_write_bytes(target, previous)
        except Exception as rollback_exc:
            raise PolicyError(f"restored policy failed validation and rollback failed: {rollback_exc}") from exc
        if isinstance(exc, PolicyError):
            raise
        raise PolicyError(f"restored policy failed validation: {exc}") from exc

    receipt = selected["receipt"]
    result = {
        "status": "OK",
        "command": "restore",
        "checkpoint": checkpoint,
        "checkpoint_kind": selected["kind"],
        "policy_sha256": restored.policy_sha256,
        "policy_path": str(target.relative_to(PACKAGE_ROOT)),
        "receipt_sha256": receipt["receipt_sha256"] if receipt else None,
        "artifacts_untouched": True,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return result


def _current_policy_status() -> dict[str, Any]:
    target = policy_path(PACKAGE_ROOT)
    try:
        source = target.read_bytes()
    except OSError as exc:
        return {"sha256": None, "valid": False, "error": f"{type(exc).__name__}: {exc}"}
    digest = hash_bytes(source)
    try:
        surface = _policy_api_validation(target)
    except Exception as exc:
        return {
            "sha256": digest,
            "valid": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"sha256": surface.policy_sha256, "valid": True, "error": None}


def _checkpoint_status(role: str) -> dict[str, Any]:
    try:
        selected = _validated_recovery_checkpoint(role)
    except Exception as exc:
        return {
            "role": role,
            "available": False,
            "kind": "packaged-baseline" if role == "release-default" else (
                "candidate-policy-checkpoint" if role == "lab-c-candidate" else "freeze-checkpoint"
            ),
            "policy_sha256": None,
            "receipt_sha256": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    receipt = selected["receipt"]
    return {
        "role": role,
        "available": True,
        "kind": selected["kind"],
        "policy_sha256": selected["surface"].policy_sha256,
        "receipt_sha256": receipt["receipt_sha256"] if receipt else None,
        "error": None,
    }


def recovery_status() -> int:
    """Print a stable JSON recovery inventory for support and tooling."""
    current = _current_policy_status()
    checkpoints = [_checkpoint_status(role) for role in RECOVERY_CHECKPOINT_ROLES]
    available_roles = [entry["role"] for entry in checkpoints if entry["available"]]
    next_recovery_commands = [
        f"bash course.sh restore --checkpoint {role}" for role in available_roles
    ] + [
        f"course.cmd restore --checkpoint {role}" for role in available_roles
    ]
    if current["valid"]:
        next_recovery_commands.insert(0, "bash course.sh status")
        next_recovery_commands.insert(1, "course.cmd status")
    else:
        for command in (
            "bash course.sh restore --checkpoint release-default",
            "course.cmd restore --checkpoint release-default",
        ):
            if command in next_recovery_commands:
                next_recovery_commands.remove(command)
        if "release-default" in available_roles:
            next_recovery_commands[0:0] = [
                "bash course.sh restore --checkpoint release-default",
                "course.cmd restore --checkpoint release-default",
            ]
    output = {
        "status": "OK",
        "command": "status",
        "policy_api_version": POLICY_API_VERSION,
        "current_policy_sha256": current["sha256"],
        "current_policy_valid": current["valid"],
        "current_policy_error": current["error"],
        "available_checkpoint_roles": available_roles,
        "available_checkpoints": checkpoints,
        "next_recovery_suggestions": next_recovery_commands,
        "next_recovery_actions": [
            {
                "checkpoint": role,
                "posix": f"bash course.sh restore --checkpoint {role}",
                "windows": f"course.cmd restore --checkpoint {role}",
            }
            for role in available_roles
        ],
        "artifacts_untouched": True,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


def _surface_from_checkpoint(role: str):
    return parse_policy_source(read_policy_checkpoint(PACKAGE_ROOT, role), f"{role}.py")


def _exact_policy(current, reference, description: str) -> None:
    if current.policy_sha256 != reference.policy_sha256:
        raise PolicyError(f"{description} requires policy {reference.policy_sha256}; current policy is {current.policy_sha256}")


def _load_required_freeze(role: str, allow_active_block: str | None = None) -> dict[str, Any]:
    receipt = read_receipt(PACKAGE_ROOT, role)
    policy_bytes = read_policy_checkpoint(PACKAGE_ROOT, role)
    policy = read_policy(PACKAGE_ROOT / "student_policy.py")
    if allow_active_block is None:
        if policy.policy_sha256 != receipt["policy_sha256"] or policy.source != policy_bytes:
            raise PolicyError(f"current policy differs from frozen {role}; restore the frozen source before withheld execution")
    else:
        reference = parse_policy_source(policy_bytes, f"{role}.py")
        compare_outside(policy, reference, allow_active_block)
    return receipt


def verify_setup() -> int:
    if sys.version_info[:2] != (3, 11):
        raise ContractError(
            f"Python 3.11.x is required by the frozen result schema; found {_python_version()}"
        )
    scenario = _scenario()
    current = read_policy(policy_path(PACKAGE_ROOT))
    baseline = read_policy(baseline_policy_path(PACKAGE_ROOT))
    if baseline.policy_sha256 != BASELINE_POLICY_SHA256:
        raise PolicyError("packaged student_policy.baseline.py has been modified")
    if current.blocks != baseline.blocks:
        raise PolicyError("student_policy.py markers differ from the packaged baseline")
    lock_sha = _lock_sha256()
    receipt = {
        "status": "READY",
        "scenario_id": SCENARIO_ID,
        "scenario_sha256": scenario["scenario_sha256"],
        "scenario_anchor_sha256": scenario["scenario_anchor_sha256"],
        "policy_sha256": current.policy_sha256,
        "policy_api_version": POLICY_API_VERSION,
        "lock_sha256": lock_sha,
        "python_version": _python_version(),
        "engine_mode": ENGINE_MODE,
        "upstream_execution": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    write_file(PACKAGE_ROOT / "artifacts" / "verify-receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


def _predecessor_and_reference(lab_id: str, case_id: str, current):
    baseline = read_policy(baseline_policy_path(PACKAGE_ROOT))
    if baseline.policy_sha256 != BASELINE_POLICY_SHA256:
        raise PolicyError("packaged student_policy.baseline.py has been modified")
    if lab_id == "A":
        if case_id == "baseline":
            _exact_policy(current, baseline, "Lab A baseline")
            return None, baseline
        if case_id == "candidate":
            compare_outside(current, baseline, BLOCK_IDS["A"])
            if current.policy_sha256 == baseline.policy_sha256:
                raise PolicyError("Lab A candidate requires a changed marked Lab A block")
            return baseline.policy_sha256, baseline
        receipt = _load_required_freeze("lab-a-frozen")
        return receipt["predecessor_policy_sha256"], _surface_from_checkpoint("lab-a-frozen")

    if lab_id == "B":
        a_receipt = _load_required_freeze("lab-a-frozen", BLOCK_IDS["B"])
        a_surface = _surface_from_checkpoint("lab-a-frozen")
        if case_id == "trace-a-baseline":
            _exact_policy(current, a_surface, "Lab B Trace A baseline")
        elif case_id == "trace-a-candidate":
            compare_outside(current, a_surface, BLOCK_IDS["B"])
            if current.policy_sha256 == a_surface.policy_sha256:
                raise PolicyError("Lab B candidate requires a changed marked Lab B block")
        else:
            b_receipt = _load_required_freeze("lab-b-frozen")
            return b_receipt["predecessor_policy_sha256"], _surface_from_checkpoint("lab-b-frozen")
        return a_receipt["policy_sha256"], a_surface

    b_receipt = _load_required_freeze("lab-b-frozen", BLOCK_IDS["C"])
    b_surface = _surface_from_checkpoint("lab-b-frozen")
    if case_id == "baseline":
        _exact_policy(current, b_surface, "Lab C baseline")
        return b_receipt["policy_sha256"], b_surface
    if case_id == "candidate":
        compare_outside(current, b_surface, BLOCK_IDS["C"])
        if current.policy_sha256 == b_surface.policy_sha256:
            raise PolicyError("Lab C candidate requires a changed marked Lab C block")
        return b_receipt["policy_sha256"], b_surface
    if case_id == "revision":
        candidate_surface = _surface_from_checkpoint("lab-c-candidate")
        compare_outside(current, b_surface, BLOCK_IDS["C"])
        if current.policy_sha256 == candidate_surface.policy_sha256:
            raise PolicyError("Lab C revision requires one changed marked Lab C block")
        return candidate_surface.policy_sha256, candidate_surface
    c_receipt = _load_required_freeze("lab-c-frozen")
    return c_receipt["predecessor_policy_sha256"], _surface_from_checkpoint("lab-c-frozen")


def run_case(lab_id: str, case_id: str, freeze: bool = False, artifact_source: str = "student-run") -> dict[str, Any]:
    if artifact_source == "student-run" and sys.version_info[:2] != (3, 11):
        raise ContractError(
            f"Python 3.11.x is required by the frozen result schema; found {_python_version()}"
        )
    scenario = _scenario()
    case = case_for(scenario, lab_id, case_id)
    current, policy_function = load_policy(policy_path(PACKAGE_ROOT), active_block_for_lab(lab_id))
    predecessor, _reference = _predecessor_and_reference(lab_id, case_id, current) if artifact_source == "student-run" else (None, current)

    freeze_cases = {("A", "candidate"): "lab-a-frozen", ("B", "trace-a-candidate"): "lab-b-frozen", ("C", "revision"): "lab-c-frozen"}
    if freeze and (lab_id, case_id) not in freeze_cases:
        raise PolicyError("--freeze is allowed only for Lab A candidate, Lab B Trace A candidate, or Lab C revision")
    if case["withheld"] and freeze:
        raise PolicyError("withheld cases cannot create a new freeze receipt")

    receipt = None
    if case["withheld"]:
        withheld_freeze_roles = {
            ("A", "hidden"): "lab-a-frozen",
            ("B", "trace-b"): "lab-b-frozen",
            ("C", "surprise"): "lab-c-frozen",
        }
        try:
            receipt = read_receipt(PACKAGE_ROOT, withheld_freeze_roles[(lab_id, case_id)])
        except KeyError as exc:
            raise ContractError(f"withheld case has no freeze-role mapping: {lab_id}/{case_id}") from exc
    if freeze:
        if predecessor is None:
            raise PolicyError("cannot freeze without predecessor policy")
        receipt = make_freeze_receipt(
            scenario, lab_id, case_id, active_block_for_lab(lab_id), current.policy_sha256,
            predecessor, _lock_sha256(), case["seed_role"], case["seed"],
        )

    result = run_simulation(
        scenario, case, current.policy_sha256, policy_function,
        artifact_source=artifact_source,
        freeze_receipt_sha256=receipt["receipt_sha256"] if receipt else None,
        predecessor_policy_sha256=predecessor,
        lock_sha256=_lock_sha256(),
        python_version=_python_version(),
    )
    validate_result(result)
    if freeze and receipt:
        role = freeze_cases[(lab_id, case_id)]
        write_freeze(PACKAGE_ROOT, receipt, current.source, role)
    if lab_id == "C" and case_id == "candidate" and artifact_source == "student-run":
        write_candidate_checkpoint(PACKAGE_ROOT, "lab-c-candidate", current.source)
    path = write_result(PACKAGE_ROOT, result)
    write_endpoint_replay(path, make_endpoint_replay(result, scenario))
    output = {
        "status": "OK",
        "run_id": result["run_id"],
        "result_path": str(path.relative_to(PACKAGE_ROOT)),
        "artifact_source": artifact_source,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return result


def generate_fallback_artifacts() -> int:
    """Generate all ten same-scenario fallback results from fixed policy stages."""
    scenario = _scenario()
    baseline_bytes = baseline_policy_path(PACKAGE_ROOT).read_bytes()

    def policy_from_bytes(source: bytes):
        surface = parse_policy_source(source, "fallback-policy.py")
        namespace = {
            "__builtins__": {}, "WAIT": "WAIT", "SLEEP": "SLEEP",
            "SEND_ONE": "SEND_ONE", "SEND_URGENT": "SEND_URGENT",
            "FLUSH_BATCH": "FLUSH_BATCH",
        }
        exec(compile(surface.source_text, "fallback-policy.py", "exec"), namespace, namespace)
        return surface, namespace["choose_action"]

    a_candidate_bytes = baseline_bytes.replace(b"REST_DURING_GAP = SLEEP", b"REST_DURING_GAP = WAIT")
    b_candidate_bytes = a_candidate_bytes.replace(b"STABLE_STEPS = 2", b"STABLE_STEPS = 1")
    c_candidate_bytes = b_candidate_bytes.replace(b"URGENT_MARGIN_S = 20", b"URGENT_MARGIN_S = 5")
    c_revision_bytes = c_candidate_bytes.replace(b"URGENT_MARGIN_S = 5", b"URGENT_MARGIN_S = 30")
    stages = {}
    for name, source in {
        "release": baseline_bytes,
        "a-candidate": a_candidate_bytes,
        "b-candidate": b_candidate_bytes,
        "c-candidate": c_candidate_bytes,
        "c-revision": c_revision_bytes,
    }.items():
        stages[name] = policy_from_bytes(source)

    labels = {
        "baseline-A": ("A", "baseline", "release"),
        "candidate-A": ("A", "candidate", "a-candidate"),
        "hidden-A": ("A", "hidden", "a-candidate"),
        "trace-a-baseline-B": ("B", "trace-a-baseline", "a-candidate"),
        "trace-a-candidate-B": ("B", "trace-a-candidate", "b-candidate"),
        "trace-b-B": ("B", "trace-b", "b-candidate"),
        "baseline-C": ("C", "baseline", "b-candidate"),
        "candidate-C": ("C", "candidate", "c-candidate"),
        "revision-C": ("C", "revision", "c-revision"),
        "surprise-C": ("C", "surprise", "c-revision"),
    }
    lock_sha = _lock_sha256()
    release_surface, _ = stages["release"]
    a_surface, _ = stages["a-candidate"]
    b_surface, _ = stages["b-candidate"]
    c_candidate_surface, _ = stages["c-candidate"]
    c_revision_surface, _ = stages["c-revision"]
    # Fallback lineage mirrors the learner sequence. Withheld artifacts echo
    # the receipt from the corresponding frozen stage; baseline/C-candidate
    # retain the contract's nullable freeze field because no freeze is created
    # by their exact learner commands.
    receipt_specs = {
        "a": ("A", "candidate", "lab-a-pace-rest", a_surface.policy_sha256, release_surface.policy_sha256, "lab-a-frozen", "lab-a-primary", 12001),
        "b": ("B", "trace-a-candidate", "lab-b-enter-exit-hold", b_surface.policy_sha256, a_surface.policy_sha256, "lab-b-frozen", "lab-b-trace-a", 12002),
        "c": ("C", "revision", "lab-c-batch-urgent", c_revision_surface.policy_sha256, c_candidate_surface.policy_sha256, "lab-c-frozen", "lab-c-primary", 12003),
    }
    receipts = {}
    for name, spec in receipt_specs.items():
        lab_id, frozen_case_id, block_id, policy_sha, predecessor_sha, role, seed_role, seed = spec
        receipt = make_freeze_receipt(
            scenario, lab_id, frozen_case_id, block_id, policy_sha, predecessor_sha,
            lock_sha, seed_role, seed,
        )
        receipts[name] = receipt
        write_file(PACKAGE_ROOT / "fallback_artifacts" / "receipts" / f"{name}.json", receipt)

    lineage = {
        "baseline-A": (None, None),
        "candidate-A": (release_surface.policy_sha256, receipts["a"]["receipt_sha256"]),
        "hidden-A": (release_surface.policy_sha256, receipts["a"]["receipt_sha256"]),
        "trace-a-baseline-B": (a_surface.policy_sha256, None),
        "trace-a-candidate-B": (a_surface.policy_sha256, receipts["b"]["receipt_sha256"]),
        "trace-b-B": (a_surface.policy_sha256, receipts["b"]["receipt_sha256"]),
        "baseline-C": (b_surface.policy_sha256, None),
        "candidate-C": (b_surface.policy_sha256, None),
        "revision-C": (c_candidate_surface.policy_sha256, receipts["c"]["receipt_sha256"]),
        "surprise-C": (c_candidate_surface.policy_sha256, receipts["c"]["receipt_sha256"]),
    }
    manifest = {
        "scenario_id": SCENARIO_ID,
        "scenario_sha256": scenario["scenario_sha256"],
        "scenario_anchor_sha256": scenario["scenario_anchor_sha256"],
        "engine_mode": ENGINE_MODE,
        "upstream_execution": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "lock_sha256": lock_sha,
        "freeze_receipts": {name: receipt["receipt_sha256"] for name, receipt in receipts.items()},
        "freeze_receipt_paths": {name: f"fallback_artifacts/receipts/{name}.json" for name in receipts},
        "artifacts": [],
    }
    for label, (lab_id, case_id, stage_name) in labels.items():
        case = case_for(scenario, lab_id, case_id)
        surface, function = stages[stage_name]
        predecessor_sha, freeze_sha = lineage[label]
        result = run_simulation(
            scenario, case, surface.policy_sha256, function,
            artifact_source="same-scenario-fallback", predecessor_policy_sha256=predecessor_sha,
            freeze_receipt_sha256=freeze_sha,
            lock_sha256=_lock_sha256(), python_version="3.11.9",
        )
        validate_result(result)
        target = PACKAGE_ROOT / "fallback_artifacts" / label / "result.json"
        write_file(target, result)
        write_endpoint_replay(target, make_endpoint_replay(result, scenario))
        manifest["artifacts"].append({
            "label": label, "path": str(target.relative_to(PACKAGE_ROOT)),
            "replay_path": str((target.parent / "endpoint-replay.json").relative_to(PACKAGE_ROOT)),
            "run_id": result["run_id"],
            "policy_sha256": result["policy"]["policy_sha256"],
            "predecessor_policy_sha256": result["policy"]["predecessor_policy_sha256"],
            "freeze_receipt_sha256": result["policy"]["freeze_receipt_sha256"],
        })
    write_file(PACKAGE_ROOT / "fallback_artifacts" / "manifest.json", manifest)
    print(json.dumps({"status": "OK", "fallback_count": len(labels), "scenario_id": SCENARIO_ID}, sort_keys=True, separators=(",", ":")))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_lab.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("verify")
    subparsers.add_parser("status")
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("--checkpoint", required=True)
    subparsers.add_parser("reset-policy")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--lab", choices=("A", "B", "C"), required=True)
    run_parser.add_argument("--case", required=True)
    run_parser.add_argument("--freeze", action="store_true")
    subparsers.add_parser("_make-fallbacks")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "verify":
            return verify_setup()
        if args.command == "status":
            return recovery_status()
        if args.command == "restore":
            restore_policy(args.checkpoint)
            return 0
        if args.command == "reset-policy":
            restore_policy("release-default")
            return 0
        if args.command == "_make-fallbacks":
            return generate_fallback_artifacts()
        run_case(args.lab, args.case, args.freeze)
        return 0
    except (CanonicalJSONError, ContractError, PolicyError, SimulationError, ResultError, FileNotFoundError, OSError) as exc:
        print(f"ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
