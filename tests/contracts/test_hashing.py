from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, localcontext

import pytest


def _hashing():
    from amadeus_core.contracts import hashing

    return hashing


def test_canonical_json_normalizes_keys_and_values_to_nfc() -> None:
    hashing = _hashing()
    left = {"e\u0301": "Cafe\u0301", "tags": ["core", "vault"]}
    right = {"é": "Café", "tags": ["core", "vault"]}

    assert hashing.canonical_json(left) == hashing.canonical_json(right)
    assert hashing.canonical_json(left) == '{"tags":["core","vault"],"é":"Café"}'.encode("utf-8")


def test_canonical_json_normalizes_aware_datetime_to_utc_rfc3339() -> None:
    hashing = _hashing()
    offset = timezone(timedelta(hours=8))
    left = {"at": datetime(2026, 7, 28, 8, 0, 0, 120000, tzinfo=offset)}
    right = {"at": datetime(2026, 7, 28, 0, 0, 0, 120000, tzinfo=UTC)}

    assert hashing.canonical_json(left) == hashing.canonical_json(right)
    assert hashing.canonical_json(left) == b'{"at":"2026-07-28T00:00:00.12Z"}'


def test_canonical_json_uses_shortest_decimal() -> None:
    hashing = _hashing()

    assert hashing.canonical_json([1.0, Decimal("1.000"), -0.0, Decimal("1000")]) == b"[1,1,0,1e3]"


def test_canonical_json_decimal_is_independent_of_decimal_context() -> None:
    hashing = _hashing()
    value = Decimal("123456789012345678901234567890")

    with localcontext() as context:
        context.prec = 5
        low_precision = hashing.canonical_json(value)
    with localcontext() as context:
        context.prec = 50
        high_precision = hashing.canonical_json(value)

    expected = b"123456789012345678901234567890"
    assert low_precision == expected
    assert high_precision == expected


def test_canonical_json_equivalent_numeric_types_have_identical_bytes() -> None:
    hashing = _hashing()

    expected = b"1e3"
    assert hashing.canonical_json(1000) == expected
    assert hashing.canonical_json(1000.0) == expected
    assert hashing.canonical_json(Decimal("1000.000")) == expected


def test_canonical_json_rejects_ambiguous_inputs() -> None:
    hashing = _hashing()

    with pytest.raises(ValueError, match="NFC key collision"):
        hashing.canonical_json({"é": 1, "e\u0301": 2})
    with pytest.raises(ValueError, match="timezone-aware"):
        hashing.canonical_json(datetime(2026, 7, 28))
    with pytest.raises(ValueError, match="finite"):
        hashing.canonical_json(float("nan"))
    with pytest.raises(TypeError, match="object keys"):
        hashing.canonical_json({1: "value"})


def test_sha256_hex_is_lowercase_and_key_order_independent() -> None:
    hashing = _hashing()
    left = {"name": "Amadeus", "version": 1}
    right = {"version": 1, "name": "Amadeus"}

    digest = hashing.sha256_hex(hashing.canonical_json(left))
    assert digest == hashing.sha256_hex(hashing.canonical_json(right))
    assert len(digest) == 64
    assert digest == digest.lower()
