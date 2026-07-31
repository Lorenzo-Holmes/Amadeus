import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess

import pytest

from tools.stage0c_fixtures.io import (
    FixtureInputError,
    canonical_bytes,
    load_strict_json_bytes,
    read_repo_regular_file,
    sha256_upper,
    tree_entries,
    tree_sha256,
)


def _assert_error_code(
    code: str,
    operation: object,
    *args: object,
    **kwargs: object,
) -> None:
    assert callable(operation)
    with pytest.raises(FixtureInputError) as captured:
        operation(*args, **kwargs)
    assert captured.value.code == code


def _is_reparse(metadata: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & reparse_flag
    )


def _remove_windows_link(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if _is_reparse(metadata) or stat.S_ISDIR(metadata.st_mode):
        os.rmdir(path)
    else:
        path.unlink()


def _create_windows_junction_or_skip(target: Path, link: Path) -> None:
    failures: list[str] = []
    try:
        import _winapi
    except ImportError as error:
        failures.append(f"_winapi.CreateJunction unavailable: {error!r}")
    else:
        try:
            _winapi.CreateJunction(str(target), str(link))
        except OSError as error:
            failures.append(f"_winapi.CreateJunction failed: {error!r}")
            _remove_windows_link(link)
        else:
            metadata = link.lstat()
            assert _is_reparse(metadata)
            assert getattr(metadata, "st_reparse_tag", None) == getattr(
                stat,
                "IO_REPARSE_TAG_MOUNT_POINT",
                getattr(metadata, "st_reparse_tag", None),
            )
            return

    completed = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/c",
            "mklink",
            "/J",
            str(link),
            str(target),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        failures.append(
            "mklink /J failed: "
            f"returncode={completed.returncode}, "
            f"stdout={completed.stdout!r}, stderr={completed.stderr!r}"
        )
        _remove_windows_link(link)
        pytest.skip("real Windows junction unavailable; " + "; ".join(failures))
    metadata = link.lstat()
    assert _is_reparse(metadata)
    assert getattr(metadata, "st_reparse_tag", None) == getattr(
        stat,
        "IO_REPARSE_TAG_MOUNT_POINT",
        getattr(metadata, "st_reparse_tag", None),
    )


def test_canonical_bytes_are_exact() -> None:
    value = {"z": [None, True, 3], "中文": {"b": 2, "a": 1}}
    expected = '{"z":[null,true,3],"中文":{"a":1,"b":2}}\n'.encode("utf-8")
    assert canonical_bytes(value) == expected
    assert sha256_upper(expected) == hashlib.sha256(expected).hexdigest().upper()


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b"\xef\xbb\xbf{}", "json_bom_forbidden"),
        (b'{"a":1,"a":2}', "json_duplicate_key"),
        (b'{"x":1.5}', "json_float_forbidden"),
        (b'{"x":NaN}', "json_non_finite_forbidden"),
        (b'{"x":Infinity}', "json_non_finite_forbidden"),
        (b"\xff", "json_non_utf8"),
        (b"{}\r\n", "json_non_canonical"),
    ],
)
def test_strict_decoder_rejects_invalid_bytes(raw: bytes, code: str) -> None:
    _assert_error_code(
        code,
        load_strict_json_bytes,
        raw,
        source="fixture.json",
    )


def test_bool_and_int_are_validated_recursively() -> None:
    value = {"values": [None, False, True, 0, 1, {"answer": 42}]}
    assert canonical_bytes(value) == (
        b'{"values":[null,false,true,0,1,{"answer":42}]}\n'
    )


@pytest.mark.parametrize(
    ("value", "code"),
    [
        (1.5, "json_float_forbidden"),
        ({"nested": [1.5]}, "json_float_forbidden"),
        (b"bytes", "json_type_forbidden"),
        ((1, 2), "json_type_forbidden"),
        ({1: "non-string-key"}, "json_type_forbidden"),
        (type("ListSubclass", (list,), {})([1]), "json_type_forbidden"),
        (
            type("DictSubclass", (dict,), {})({"x": 1}),
            "json_type_forbidden",
        ),
        (type("IntSubclass", (int,), {})(1), "json_type_forbidden"),
    ],
)
def test_canonical_bytes_rejects_programmatic_types(
    value: object,
    code: str,
) -> None:
    _assert_error_code(code, canonical_bytes, value)


def test_canonical_bytes_rejects_cyclic_list() -> None:
    value: list[object] = []
    value.append(value)
    _assert_error_code("json_type_forbidden", canonical_bytes, value)


def test_canonical_bytes_rejects_cyclic_dict() -> None:
    value: dict[str, object] = {}
    value["self"] = value
    _assert_error_code("json_type_forbidden", canonical_bytes, value)


def test_strict_decoder_round_trips_and_rejects_syntax() -> None:
    value = {"a": [1, True, None], "b": "中文"}
    raw = canonical_bytes(value)
    assert load_strict_json_bytes(raw, source="fixture.json") == value
    _assert_error_code(
        "json_invalid",
        load_strict_json_bytes,
        b'{"a":}\n',
        source="fixture.json",
    )
    _assert_error_code(
        "json_invalid",
        load_strict_json_bytes,
        b'"\\ud800"\n',
        source="fixture.json",
    )


def test_strict_decoder_normalizes_integer_digit_limit() -> None:
    _assert_error_code(
        "json_invalid",
        load_strict_json_bytes,
        (b"1" * 5000) + b"\n",
        source="fixture.json",
    )


def test_canonical_bytes_are_written_closed_reread_and_hashed(tmp_path: Path) -> None:
    output = tmp_path / "fixture.json"
    expected = canonical_bytes({"value": [3, 2, 1]})
    with output.open("wb") as handle:
        handle.write(expected)
    reread = output.read_bytes()
    assert reread == expected
    assert sha256_upper(reread) == hashlib.sha256(reread).hexdigest().upper()


@pytest.mark.parametrize(
    ("relative", "code"),
    [
        ("C:/absolute.json", "repo_path_absolute"),
        ("/absolute.json", "repo_path_absolute"),
        (r"fixtures\stage0c\x.json", "repo_path_backslash"),
        ("fixtures/./x.json", "repo_path_dot_segment"),
        ("fixtures/../x.json", "repo_path_parent_segment"),
    ],
)
def test_repo_path_lexical_contract(
    tmp_path: Path,
    relative: str,
    code: str,
) -> None:
    _assert_error_code(code, read_repo_regular_file, tmp_path, relative)


def test_repo_reader_returns_exact_regular_file_bytes(tmp_path: Path) -> None:
    nested = tmp_path / "fixtures" / "stage0c"
    nested.mkdir(parents=True)
    expected = b"\x00fixture\xff\n"
    (nested / "x.bin").write_bytes(expected)
    assert read_repo_regular_file(tmp_path, "fixtures/stage0c/x.bin") == expected


def test_repo_reader_propagates_unrelated_leaf_open_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leaf = tmp_path / "leaf.bin"
    leaf.write_bytes(b"data")
    original_open = Path.open

    def denied(path: Path, *args: object, **kwargs: object) -> object:
        if path == leaf:
            raise PermissionError("leaf denied")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(PermissionError, match="leaf denied"):
        read_repo_regular_file(tmp_path, "leaf.bin")


@pytest.mark.parametrize("relative", ["missing.bin", "missing/leaf.bin"])
def test_repo_reader_rejects_missing_leaf_or_ancestor(
    tmp_path: Path,
    relative: str,
) -> None:
    _assert_error_code("repo_path_missing", read_repo_regular_file, tmp_path, relative)


def test_repo_reader_rejects_directory_leaf(tmp_path: Path) -> None:
    (tmp_path / "directory").mkdir()
    _assert_error_code(
        "repo_path_not_regular_file",
        read_repo_regular_file,
        tmp_path,
        "directory",
    )


def test_repo_reader_rejects_ordinary_file_ancestor(tmp_path: Path) -> None:
    (tmp_path / "ordinary").write_bytes(b"file")
    _assert_error_code(
        "repo_path_not_regular_file",
        read_repo_regular_file,
        tmp_path,
        "ordinary/leaf.bin",
    )


def test_repo_reader_rejects_real_fifo_when_supported(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("os.mkfifo is unavailable")
    fifo = tmp_path / "pipe"
    try:
        os.mkfifo(fifo)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"real FIFO unavailable: {error!r}")
    _assert_error_code(
        "repo_path_not_regular_file",
        read_repo_regular_file,
        tmp_path,
        "pipe",
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
@pytest.mark.parametrize("position", ["terminal", "ancestor"])
@pytest.mark.parametrize("dangling", [False, True])
def test_repo_reader_rejects_real_windows_junction_component(
    tmp_path: Path,
    position: str,
    dangling: bool,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "payload.bin").write_bytes(b"target")
    link = tmp_path / "linked"
    _create_windows_junction_or_skip(target, link)
    try:
        if dangling:
            shutil.rmtree(target)
        _assert_error_code(
            "repo_path_reparse",
            read_repo_regular_file,
            tmp_path,
            "linked" if position == "terminal" else "linked/payload.bin",
        )
    finally:
        _remove_windows_link(link)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_windows_junction_helper_uses_real_cmd_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import _winapi

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "linked"

    def fail_create_junction(_target: str, _link: str) -> None:
        raise OSError("forced _winapi failure")

    monkeypatch.setattr(_winapi, "CreateJunction", fail_create_junction)
    _create_windows_junction_or_skip(target, link)
    try:
        assert _is_reparse(link.lstat())
    finally:
        _remove_windows_link(link)


def _write_tree(root: Path, files: list[tuple[str, bytes]]) -> None:
    root.mkdir()
    for relative, data in files:
        path = root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (root / "empty-directory").mkdir()


def test_tree_propagates_unrelated_listdir_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "tree"
    root.mkdir()

    def denied(_path: object) -> list[str]:
        raise PermissionError("list denied")

    monkeypatch.setattr(os, "listdir", denied)
    with pytest.raises(PermissionError, match="list denied"):
        tree_entries(root)


def test_tree_propagates_unrelated_leaf_open_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    leaf = root / "leaf.bin"
    leaf.write_bytes(b"data")
    original_open = Path.open

    def denied(path: Path, *args: object, **kwargs: object) -> object:
        if path == leaf:
            raise PermissionError("tree leaf denied")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(PermissionError, match="tree leaf denied"):
        tree_entries(root)


def test_tree_entries_and_hash_ignore_creation_order_and_empty_directories(
    tmp_path: Path,
) -> None:
    files = [
        ("a.json", b"a\n"),
        ("B.json", b"B\n"),
        ("nested/中文.json", b"nested\n"),
    ]
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_tree(first, files)
    _write_tree(second, list(reversed(files)))
    expected = [
        {
            "path": "B.json",
            "size": 2,
            "sha256": sha256_upper(b"B\n"),
        },
        {
            "path": "a.json",
            "size": 2,
            "sha256": sha256_upper(b"a\n"),
        },
        {
            "path": "nested/中文.json",
            "size": 7,
            "sha256": sha256_upper(b"nested\n"),
        },
    ]
    assert tree_entries(first) == expected
    assert tree_entries(second) == expected
    assert tree_sha256(first) == tree_sha256(second)
    assert tree_sha256(first) == sha256_upper(canonical_bytes(expected))


def test_empty_tree_hash_is_frozen(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert tree_entries(empty) == []
    assert tree_sha256(empty) == (
        "37517E5F3DC66819F61F5A7BB8ACE1921282415F10551D2DEFA5C3EB0985B570"
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_tree_rejects_real_windows_junction(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    (target / "payload.bin").write_bytes(b"target")
    link = root / "linked"
    _create_windows_junction_or_skip(target, link)
    try:
        _assert_error_code("repo_path_reparse", tree_entries, root)
    finally:
        _remove_windows_link(link)


def test_tree_rejects_nonregular_entry_when_supported(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("os.mkfifo is unavailable")
    root = tmp_path / "tree"
    root.mkdir()
    try:
        os.mkfifo(root / "pipe")
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"real FIFO unavailable: {error!r}")
    _assert_error_code("repo_path_not_regular_file", tree_entries, root)
