"""Core canonical JSON v1 and lowercase SHA-256 helpers."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


def _string_text(value: str) -> str:
    return json.dumps(unicodedata.normalize("NFC", value), ensure_ascii=False)


def _datetime_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    utc = value.astimezone(UTC)
    if utc.microsecond:
        text = utc.isoformat(timespec="microseconds").replace("+00:00", "Z")
        head, suffix = text.split(".", 1)
        fraction = suffix[:-1].rstrip("0")
        return f"{head}.{fraction}Z"
    return utc.isoformat(timespec="seconds").replace("+00:00", "Z")


def _decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("numbers must be finite")
    if value.is_zero():
        return "0"

    parts = value.as_tuple()
    digits = list(parts.digits)
    while digits and digits[0] == 0:
        digits.pop(0)
    exponent = parts.exponent
    if not isinstance(exponent, int):  # pragma: no cover - finite values always use int
        raise ValueError("numbers must be finite")
    while digits[-1] == 0:
        digits.pop()
        exponent += 1

    sign = "-" if parts.sign else ""
    coefficient = "".join(str(digit) for digit in digits)
    decimal_point = len(coefficient) + exponent
    if exponent >= 0:
        fixed_length = len(sign) + len(coefficient) + exponent
    elif decimal_point > 0:
        fixed_length = len(sign) + len(coefficient) + 1
    else:
        fixed_length = len(sign) + 2 - decimal_point + len(coefficient)

    scientific_exponent = decimal_point - 1
    exponent_text = str(scientific_exponent)
    mantissa_length = 1 if len(coefficient) == 1 else len(coefficient) + 1
    scientific_length = len(sign) + mantissa_length + 1 + len(exponent_text)

    if fixed_length <= scientific_length:
        if exponent >= 0:
            return sign + coefficient + ("0" * exponent)
        if decimal_point > 0:
            return sign + coefficient[:decimal_point] + "." + coefficient[decimal_point:]
        return sign + "0." + ("0" * -decimal_point) + coefficient

    mantissa = coefficient[0]
    if len(coefficient) > 1:
        mantissa += "." + coefficient[1:]
    return f"{sign}{mantissa}e{exponent_text}"


def _emit(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return _decimal_text(Decimal(value))
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("numbers must be finite")
        return _decimal_text(Decimal(repr(value)))
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, datetime):
        return _string_text(_datetime_text(value))
    if isinstance(value, str):
        return _string_text(value)
    if isinstance(value, Mapping):
        normalized_items: list[tuple[str, Any]] = []
        seen: set[str] = set()
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise TypeError("object keys must be strings")
            key = unicodedata.normalize("NFC", raw_key)
            if key in seen:
                raise ValueError("NFC key collision")
            seen.add(key)
            normalized_items.append((key, item))
        normalized_items.sort(key=lambda item: item[0])
        return "{" + ",".join(
            f"{_string_text(key)}:{_emit(item)}" for key, item in normalized_items
        ) + "}"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "[" + ",".join(_emit(item) for item in value) + "]"
    raise TypeError(f"unsupported canonical JSON type: {type(value).__qualname__}")


def canonical_json(value: Any) -> bytes:
    return _emit(value).encode("utf-8")


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


__all__ = ["canonical_json", "sha256_hex"]
