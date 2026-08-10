"""Bounded local policy surface and source-line guard."""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

from .canonical_json import hash_bytes
from .contracts import BLOCK_IDS, LEGAL_ACTIONS, POLICY_API_VERSION

BASELINE_POLICY_SHA256 = "sha256:9917d2cde2e8c0eae8339b7eea2e358bf8577b4eb6aaf1e928674f6b8964ef68"

BEGIN_RE = re.compile(r"^# === LORA EDITABLE: (lab-[a-c]-[a-z0-9-]+) ===$")
END_RE = re.compile(r"^# === LORA END EDITABLE: (lab-[a-c]-[a-z0-9-]+) ===$")
BLOCK_FOR_LAB = {"A": BLOCK_IDS["A"], "B": BLOCK_IDS["B"], "C": BLOCK_IDS["C"]}
ALLOWED_OBSERVATION_FIELDS = {
    "contact_open", "quality_band", "stable_steps", "send_mode_active",
    "steps_since_send", "contact_remaining_s", "queue_size", "urgent_pending",
    "urgent_due_in_s", "previous_action", "elapsed_s",
}
ALLOWED_NAMES = {
    "WAIT", "SLEEP", "SEND_ONE", "SEND_URGENT", "FLUSH_BATCH", "observation",
    "PACE_GAP_STEPS", "REST_DURING_GAP", "ENTER_QUALITY", "EXIT_QUALITY",
    "STABLE_STEPS", "BATCH_SIZE", "URGENT_MARGIN_S", "quality_ready", "choose_action",
}
ALLOWED_ASSIGN_NAMES = {
    "WAIT", "SLEEP", "SEND_ONE", "SEND_URGENT", "FLUSH_BATCH",
    "PACE_GAP_STEPS", "REST_DURING_GAP", "ENTER_QUALITY", "EXIT_QUALITY",
    "STABLE_STEPS", "BATCH_SIZE", "URGENT_MARGIN_S", "quality_ready",
}


class PolicyError(ValueError):
    """A policy source, API, or action error."""


@dataclass(frozen=True)
class PolicyObservation:
    elapsed_s: int
    contact_open: bool
    quality_band: int
    stable_steps: int
    send_mode_active: bool
    steps_since_send: int
    contact_remaining_s: int
    queue_size: int
    urgent_pending: bool
    urgent_due_in_s: int | None
    previous_action: str | None


@dataclass(frozen=True)
class PolicySurface:
    source: bytes
    source_text: str
    policy_sha256: str
    blocks: dict[str, tuple[int, int]]


def policy_path(package_root: str | Path) -> Path:
    return Path(package_root) / "student_policy.py"


def baseline_policy_path(package_root: str | Path) -> Path:
    return Path(package_root) / "student_policy.baseline.py"


def read_policy(path: str | Path) -> PolicySurface:
    target = Path(path)
    try:
        source = target.read_bytes()
    except OSError as exc:
        raise PolicyError(f"cannot read policy: {exc}") from exc
    return parse_policy_source(source, str(target))


def parse_policy_source(source: bytes, label: str = "student_policy.py") -> PolicySurface:
    if source.startswith(b"\xef\xbb\xbf"):
        raise PolicyError("UTF-8 BOM is not permitted in student_policy.py")
    if b"\r" in source:
        raise PolicyError("CRLF/CR line endings are not permitted; use LF")
    if not source.endswith(b"\n"):
        raise PolicyError("student_policy.py must end with one LF")
    try:
        source_text = source.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise PolicyError("student_policy.py must be UTF-8") from exc
    blocks = _find_blocks(source_text)
    _validate_ast(source_text)
    return PolicySurface(source, source_text, hash_bytes(source), blocks)


def _find_blocks(source_text: str) -> dict[str, tuple[int, int]]:
    lines = source_text.splitlines(keepends=True)
    begins: dict[str, int] = {}
    ends: dict[str, int] = {}
    for index, line in enumerate(lines):
        stripped = line.rstrip("\n")
        begin = BEGIN_RE.match(stripped)
        end = END_RE.match(stripped)
        if begin:
            block = begin.group(1)
            if block in begins:
                raise PolicyError(f"duplicate editable marker: {block}")
            begins[block] = index
        if end:
            block = end.group(1)
            if block in ends:
                raise PolicyError(f"duplicate editable end marker: {block}")
            ends[block] = index
    expected = set(BLOCK_FOR_LAB.values())
    if set(begins) != expected or set(ends) != expected:
        raise PolicyError("student_policy.py must contain exactly the three LoRa energy editable blocks")
    result: dict[str, tuple[int, int]] = {}
    for block in sorted(expected):
        if begins[block] >= ends[block]:
            raise PolicyError(f"editable block is not closed: {block}")
        result[block] = (begins[block], ends[block])
    return result


def normalized_outside(source_text: str, active_block: str) -> bytes:
    """Return bytes with one editable block replaced by a stable sentinel."""
    blocks = _find_blocks(source_text)
    lines = source_text.splitlines(keepends=True)
    begin, end = blocks[active_block]
    replaced = lines[: begin + 1] + [f"# LORA EDITABLE CONTENT OMITTED: {active_block}\n"] + lines[end:]
    return "".join(replaced).encode("utf-8")


def outside_hash(source_text: str, active_block: str) -> str:
    return hash_bytes(normalized_outside(source_text, active_block))


def compare_outside(current: PolicySurface, reference: PolicySurface, active_block: str) -> None:
    if normalized_outside(current.source_text, active_block) != normalized_outside(reference.source_text, active_block):
        raise PolicyError(
            f"edit outside marked block {active_block}; restore the predecessor policy before editing"
        )


def _validate_ast(source_text: str) -> None:
    try:
        tree = ast.parse(source_text, filename="student_policy.py", mode="exec")
    except SyntaxError as exc:
        line = exc.lineno or 0
        raise PolicyError(f"syntax error on line {line}: {exc.msg}") from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.With, ast.AsyncWith, ast.Try, ast.While, ast.For, ast.AsyncFor, ast.ClassDef, ast.Lambda, ast.Global, ast.Nonlocal, ast.Delete, ast.Raise, ast.Assert, ast.Yield, ast.Await, ast.NamedExpr, ast.Match)):
            raise PolicyError(f"unsupported policy syntax on line {getattr(node, 'lineno', 0)}: {type(node).__name__}")
        if isinstance(node, ast.Call):
            raise PolicyError(f"function calls are not allowed in policy on line {node.lineno}")
        if isinstance(node, ast.Attribute):
            if not isinstance(node.value, ast.Name) or node.value.id != "observation" or node.attr not in ALLOWED_OBSERVATION_FIELDS:
                raise PolicyError(f"attribute is not an allowed observation field on line {node.lineno}")
        if isinstance(node, ast.Name) and node.id not in ALLOWED_NAMES:
            raise PolicyError(f"name is not in the policy API on line {node.lineno}: {node.id}")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name) or target.id not in ALLOWED_ASSIGN_NAMES:
                    raise PolicyError(f"assignment is not an editable policy constant on line {node.lineno}")
        if isinstance(node, ast.FunctionDef):
            if node.name != "choose_action" or len(node.args.args) != 1 or node.args.args[0].arg != "observation":
                raise PolicyError("policy must define choose_action(observation) only")
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1 or functions[0].name != "choose_action":
        raise PolicyError("policy must define exactly one choose_action function")


def _safe_namespace() -> dict[str, Any]:
    return {
        "__builtins__": {},
        "WAIT": "WAIT", "SLEEP": "SLEEP", "SEND_ONE": "SEND_ONE",
        "SEND_URGENT": "SEND_URGENT", "FLUSH_BATCH": "FLUSH_BATCH",
    }


def load_policy(path: str | Path, active_block: str) -> tuple[PolicySurface, Any]:
    surface = read_policy(path)
    if active_block not in surface.blocks:
        raise PolicyError(f"unknown active block: {active_block}")
    namespace = _safe_namespace()
    try:
        exec(compile(surface.source_text, str(path), "exec"), namespace, namespace)
    except Exception as exc:  # pragma: no cover - guarded syntax still has runtime failures
        raise PolicyError(f"policy could not be loaded: {exc}") from exc
    function = namespace.get("choose_action")
    if not callable(function):
        raise PolicyError("choose_action is missing")
    for name in (
        "WAIT", "SLEEP", "SEND_ONE", "SEND_URGENT", "FLUSH_BATCH",
        "PACE_GAP_STEPS", "REST_DURING_GAP", "ENTER_QUALITY", "EXIT_QUALITY",
        "STABLE_STEPS", "BATCH_SIZE", "URGENT_MARGIN_S",
    ):
        if name not in namespace:
            raise PolicyError(f"policy constant is missing: {name}")
    if namespace["REST_DURING_GAP"] not in ("WAIT", "SLEEP"):
        raise PolicyError("REST_DURING_GAP must be WAIT or SLEEP")
    for name in ("PACE_GAP_STEPS", "ENTER_QUALITY", "EXIT_QUALITY", "STABLE_STEPS", "BATCH_SIZE", "URGENT_MARGIN_S"):
        value = namespace[name]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 60:
            raise PolicyError(f"{name} must be an integer between 0 and 60")
    return surface, function


def call_policy(function: Any, observation: PolicyObservation, line_hint: int | None = None) -> str:
    try:
        action = function(observation)
    except Exception as exc:  # pragma: no cover - policy source failure path
        suffix = f" on line {line_hint}" if line_hint else ""
        raise PolicyError(f"policy decision failed{suffix}: {exc}") from exc
    if action not in LEGAL_ACTIONS:
        suffix = f" on line {line_hint}" if line_hint else ""
        raise PolicyError(f"illegal action{suffix}: {action!r}; legal actions: {', '.join(LEGAL_ACTIONS)}")
    return action


def active_block_for_lab(lab_id: str) -> str:
    try:
        return BLOCK_FOR_LAB[lab_id]
    except KeyError as exc:
        raise PolicyError(f"unknown lab: {lab_id}") from exc
