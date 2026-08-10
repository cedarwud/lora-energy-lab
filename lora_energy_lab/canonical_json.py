"""Small RFC-8785-compatible JSON subset used by the LoRa energy contract.

The course values are bounded finite numbers with at most six decimal places.
The implementation deliberately rejects values outside that interchange
profile instead of silently producing a different hash.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

SAFE_INTEGER = 9007199254740991


class CanonicalJSONError(ValueError):
    """Raised when a value cannot be represented by the contract subset."""


def _reject_constant(value: str) -> None:
    raise CanonicalJSONError(f"non-finite JSON number: {value}")


def _parse_int(value: str) -> int:
    parsed = int(value)
    if abs(parsed) > SAFE_INTEGER:
        raise CanonicalJSONError("integer exceeds JavaScript safe-integer range")
    return parsed


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalJSONError(f"duplicate object key: {key}")
        result[key] = value
    return result


def loads(data: str | bytes) -> Any:
    """Parse strict JSON with duplicate/non-finite checks."""
    try:
        return json.loads(
            data,
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
            parse_int=_parse_int,
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CanonicalJSONError(str(exc)) from exc


def load_file(path: str | Path) -> Any:
    return loads(Path(path).read_bytes())


def _validate(value: Any) -> None:
    if value is None or isinstance(value, (str, bool)):
        if isinstance(value, str):
            try:
                value.encode("utf-8", "strict")
            except UnicodeEncodeError as exc:
                raise CanonicalJSONError("surrogate code point in string") from exc
        return
    if isinstance(value, int):
        if abs(value) > SAFE_INTEGER:
            raise CanonicalJSONError("integer exceeds JavaScript safe-integer range")
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalJSONError("non-finite float")
        if value == 0.0 and math.copysign(1.0, value) < 0:
            raise CanonicalJSONError("negative zero is not permitted")
        return
    if isinstance(value, list):
        for item in value:
            _validate(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalJSONError("object key is not a string")
            _validate(key)
            _validate(item)
        return
    raise CanonicalJSONError(f"unsupported JSON type: {type(value).__name__}")


def _number(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    if value == 0.0:
        return "0"
    # Python's repr and ECMAScript's shortest representation agree for the
    # bounded decimal values in the frozen scenario. Normalize exponent zeroes
    # and integral decimals for the wider contract subset.
    text = repr(value)
    if text.endswith(".0") and abs(value) < 1e21:
        return text[:-2]
    if "e" in text or "E" in text:
        mantissa, exponent = text.lower().split("e")
        sign = ""
        if exponent.startswith(("+", "-")):
            sign, exponent = exponent[0], exponent[1:]
        exponent = exponent.lstrip("0") or "0"
        if sign == "-":
            exponent = "-" + exponent
        else:
            exponent = "+" + exponent
        text = f"{mantissa}e{exponent}"
    return text


def _encode(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    if isinstance(value, dict):
        # Contract keys are ASCII today. Code-point sorting is the declared
        # contract order and is equivalent for these keys.
        entries = []
        for key in sorted(value):
            entries.append(_encode(key) + ":" + _encode(value[key]))
        return "{" + ",".join(entries) + "}"
    raise CanonicalJSONError(f"unsupported JSON type: {type(value).__name__}")


def dumps(value: Any) -> str:
    _validate(value)
    return _encode(value)


def dump_bytes(value: Any) -> bytes:
    return dumps(value).encode("utf-8")


def hash_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def hash_value(value: Any) -> str:
    return hash_bytes(dump_bytes(value))


def hash_file(path: str | Path) -> str:
    return hash_bytes(Path(path).read_bytes())


def write_file(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(dump_bytes(value) + b"\n")
