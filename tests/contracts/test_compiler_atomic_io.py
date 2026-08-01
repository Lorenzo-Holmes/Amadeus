import os
from pathlib import Path

import pytest


def test_atomic_write_preserves_previous_file_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.atomic_io import atomic_write_bytes

    destination = tmp_path / "artifact.json"
    destination.write_bytes(b"old")

    def fail_replace(source: str | bytes, target: str | bytes) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected replace failure"):
        atomic_write_bytes(destination, b"new")

    assert destination.read_bytes() == b"old"
    assert tuple(tmp_path.iterdir()) == (destination,)
