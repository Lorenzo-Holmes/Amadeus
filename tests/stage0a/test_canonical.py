import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from tools.stage0a_sources.canonical import canonical_bytes, verify_documents


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "fixtures" / "stage0a" / "source_config_v0_1.json"


def test_canonical_bytes_ignore_key_order() -> None:
    assert canonical_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}'


def test_canonical_bytes_preserve_unicode_and_json_scalars() -> None:
    value = {"布尔": True, "空值": None, "中文": "记忆"}

    assert canonical_bytes(value) == (
        b'{"\xe4\xb8\xad\xe6\x96\x87":"\xe8\xae\xb0\xe5\xbf\x86",'
        b'"\xe5\xb8\x83\xe5\xb0\x94":true,"\xe7\xa9\xba\xe5\x80\xbc":null}'
    )


def test_verify_documents_accepts_five_frozen_inputs() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    verified = verify_documents(ROOT, config)

    expected_keys = [
        "adr_006",
        "baseline",
        "core_spec",
        "increment",
        "plan_review",
    ]
    assert list(verified) == expected_keys
    configured = {document["key"]: document for document in config["documents"]}
    assert verified == {
        key: {
            "path": configured[key]["path"],
            "source_group": configured[key]["source_group"],
            "expected_sha256": configured[key]["sha256"],
            "actual_sha256": configured[key]["sha256"],
        }
        for key in expected_keys
    }


@pytest.mark.parametrize(
    "document_key",
    ["adr_006", "baseline", "core_spec", "increment", "plan_review"],
)
def test_verify_documents_rejects_single_byte_document_drift(
    tmp_path: Path,
    document_key: str,
) -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    configured = {document["key"]: document for document in config["documents"]}
    for document in config["documents"]:
        source = ROOT / document["path"]
        target = tmp_path / document["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    changed_path = tmp_path / configured[document_key]["path"]
    with changed_path.open("ab") as stream:
        stream.write(b"\x00")
    expected_sha256 = configured[document_key]["sha256"]
    actual_sha256 = hashlib.sha256(changed_path.read_bytes()).hexdigest().upper()

    with pytest.raises(ValueError, match="document drift") as error:
        verify_documents(tmp_path, config)
    message = str(error.value)
    assert document_key in message
    assert expected_sha256 in message
    assert actual_sha256 in message


def test_verify_documents_rejects_configuration_contract_mutations() -> None:
    original = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    mutations = []

    changed = copy.deepcopy(original)
    changed["schema_version"] = "0.2"
    mutations.append(changed)

    changed = copy.deepcopy(original)
    changed["documents"][0]["key"] = "adr_007"
    mutations.append(changed)

    changed = copy.deepcopy(original)
    changed["documents"][0]["path"] += ".changed"
    mutations.append(changed)

    changed = copy.deepcopy(original)
    changed["documents"][0]["source_group"] = "adr"
    mutations.append(changed)

    changed = copy.deepcopy(original)
    changed["documents"][0]["sha256"] = "0" * 64
    mutations.append(changed)

    changed = copy.deepcopy(original)
    changed["unexpected"] = True
    mutations.append(changed)

    changed = copy.deepcopy(original)
    changed["documents"][0]["unexpected"] = True
    mutations.append(changed)

    changed = copy.deepcopy(original)
    changed["documents"][0]["path"] = None
    mutations.append(changed)

    mutations.extend([None, {"schema_version": "0.1", "documents": {}}])

    for changed in mutations:
        with pytest.raises(ValueError, match="configuration contract"):
            verify_documents(ROOT, changed)


def test_verify_documents_preserves_missing_root_error(tmp_path: Path) -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    with pytest.raises(FileNotFoundError):
        verify_documents(tmp_path / "missing-root", config)
