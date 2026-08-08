"""Governor command authentication binds every mutation-command authority input."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from amadeus_core.contracts.commands import (
    Actor,
    ExpectedVersion,
    MutationCommandEnvelope,
    idempotency_address,
)
from amadeus_core.governance.governor_command_auth import (
    GovernorCommandSigner,
    GovernorCommandVerifier,
)


_KEY_ID = "primary-2026"
_ACTOR_ID = "governor-core-a1"
_SECRET = b"a-fixed-test-secret-with-at-least-32-bytes"
_OTHER_SECRET = b"another-fixed-test-secret-of-32-bytes"


def _unsigned_command(
    *,
    command_id: str = "cmd-a1",
    issued_at: datetime = datetime(2026, 8, 3, 4, 5, tzinfo=UTC),
) -> MutationCommandEnvelope:
    return MutationCommandEnvelope(
        command_id=command_id,
        command_type="memory_proposal.decide",
        actor=Actor(actor_type="governor", actor_id=_ACTOR_ID),
        actor_capability_id="unsigned",
        expected_versions=(
            ExpectedVersion(target_record_ref="mem-a1", expected_version="absent"),
            ExpectedVersion(target_record_ref="mpp-a1", expected_version=2),
        ),
        audit_context_id="aud-a1",
        idempotency_key="idem-a1",
        issued_at=issued_at,
        target_record_refs=("mem-a1", "mpp-a1"),
        payload={
            "proposal_id": "mpp-a1",
            "scope_refs": ("idn-a1", "lin-a1", "brn-a1", "vlt-a1"),
            "decision_context": {
                "evidence_refs": ("evd-a1", "evd-a2"),
                "weights": {"semantic": 3, "temporal": 2},
            },
        },
    )


@pytest.fixture
def signer() -> GovernorCommandSigner:
    return GovernorCommandSigner(
        key_id=_KEY_ID,
        actor_id=_ACTOR_ID,
        secret=_SECRET,
    )


@pytest.fixture
def verifier() -> GovernorCommandVerifier:
    return GovernorCommandVerifier(
        {_KEY_ID: (_ACTOR_ID, _SECRET), "secondary": (_ACTOR_ID, _OTHER_SECRET)}
    )


def test_valid_signature_uses_stable_capability_and_closed_attestation_format(
    signer: GovernorCommandSigner,
    verifier: GovernorCommandVerifier,
) -> None:
    signed = signer.sign(_unsigned_command())

    prefix, key_id, digest = signed.payload["actor_attestation"].split(":")
    assert (prefix, key_id) == ("govcmd-v1", _KEY_ID)
    assert signed.actor_capability_id == f"govcap:{_KEY_ID}"
    assert len(digest) == 64
    assert digest == digest.lower()
    assert set(digest) <= set("0123456789abcdef")
    assert verifier.verify(signed) is True


def test_signed_command_preserves_deep_frozen_envelope(
    signer: GovernorCommandSigner,
) -> None:
    signed = signer.sign(_unsigned_command())

    with pytest.raises(TypeError):
        signed.payload["proposal_id"] = "mpp-tampered"  # type: ignore[index]


def test_signature_normalizes_target_version_and_payload_object_order(
    signer: GovernorCommandSigner,
    verifier: GovernorCommandVerifier,
) -> None:
    first = _unsigned_command()
    second = first.model_copy(
        update={
            "target_record_refs": tuple(reversed(first.target_record_refs)),
            "expected_versions": tuple(reversed(first.expected_versions)),
            "payload": {
                "decision_context": {
                    "weights": {"temporal": 2, "semantic": 3},
                    "evidence_refs": ("evd-a1", "evd-a2"),
                },
                "scope_refs": ("idn-a1", "lin-a1", "brn-a1", "vlt-a1"),
                "proposal_id": "mpp-a1",
            },
        }
    )

    first_signed = signer.sign(first)
    second_signed = signer.sign(second)

    assert first_signed.payload["actor_attestation"] == second_signed.payload[
        "actor_attestation"
    ]
    assert verifier.verify(first_signed) is True
    assert verifier.verify(second_signed) is True


def test_token_for_command_a_cannot_be_reused_for_command_b(
    signer: GovernorCommandSigner,
    verifier: GovernorCommandVerifier,
) -> None:
    signed_a = signer.sign(_unsigned_command(command_id="cmd-a1"))
    command_b_payload = _unsigned_command(command_id="cmd-b2").model_dump(
        mode="python"
    )["payload"]
    command_b_payload["actor_attestation"] = signed_a.payload["actor_attestation"]
    command_b = _unsigned_command(command_id="cmd-b2").model_copy(
        update={
            "actor_capability_id": signed_a.actor_capability_id,
            "payload": command_b_payload,
        }
    )

    assert verifier.verify(command_b) is False


def test_stable_capability_preserves_route_b_idempotency_partition(
    signer: GovernorCommandSigner,
) -> None:
    first = signer.sign(_unsigned_command(command_id="cmd-a1"))
    second = signer.sign(_unsigned_command(command_id="cmd-b2"))

    assert first.actor_capability_id == second.actor_capability_id == (
        f"govcap:{_KEY_ID}"
    )
    assert (
        idempotency_address(first).actor_capability_id
        == idempotency_address(second).actor_capability_id
        == f"govcap:{_KEY_ID}"
    )


def _tamper_actor_type(command: MutationCommandEnvelope) -> MutationCommandEnvelope:
    return command.model_copy(update={"actor": Actor(actor_type="llm", actor_id=_ACTOR_ID)})


def _tamper_actor_id(command: MutationCommandEnvelope) -> MutationCommandEnvelope:
    return command.model_copy(
        update={"actor": Actor(actor_type="governor", actor_id="governor-other")}
    )


def _tamper_command_id(command: MutationCommandEnvelope) -> MutationCommandEnvelope:
    return command.model_copy(update={"command_id": "cmd-b2"})


def _tamper_command_type(command: MutationCommandEnvelope) -> MutationCommandEnvelope:
    return command.model_copy(update={"command_type": "memory_proposal.submit"})


def _tamper_payload(command: MutationCommandEnvelope) -> MutationCommandEnvelope:
    payload = command.model_dump(mode="python")["payload"]
    payload["decision_context"]["weights"]["temporal"] = 999
    return command.model_copy(update={"payload": payload})


def _tamper_target_scope(command: MutationCommandEnvelope) -> MutationCommandEnvelope:
    return command.model_copy(
        update={
            "target_record_refs": ("mem-b2", "mpp-a1"),
            "expected_versions": (
                ExpectedVersion(target_record_ref="mem-b2", expected_version="absent"),
                ExpectedVersion(target_record_ref="mpp-a1", expected_version=2),
            ),
        }
    )


def _tamper_expected_version(command: MutationCommandEnvelope) -> MutationCommandEnvelope:
    return command.model_copy(
        update={
            "expected_versions": (
                ExpectedVersion(target_record_ref="mem-a1", expected_version="absent"),
                ExpectedVersion(target_record_ref="mpp-a1", expected_version=3),
            )
        }
    )


def _tamper_time(command: MutationCommandEnvelope) -> MutationCommandEnvelope:
    return command.model_copy(update={"issued_at": command.issued_at + timedelta(seconds=1)})


def _tamper_audit(command: MutationCommandEnvelope) -> MutationCommandEnvelope:
    return command.model_copy(update={"audit_context_id": "aud-b2"})


def _tamper_idempotency(command: MutationCommandEnvelope) -> MutationCommandEnvelope:
    return command.model_copy(update={"idempotency_key": "idem-b2"})


def _tamper_stable_capability(
    command: MutationCommandEnvelope,
) -> MutationCommandEnvelope:
    return command.model_copy(update={"actor_capability_id": "govcap:secondary"})


@pytest.mark.parametrize(
    "tamper",
    (
        _tamper_actor_type,
        _tamper_actor_id,
        _tamper_command_id,
        _tamper_command_type,
        _tamper_payload,
        _tamper_target_scope,
        _tamper_expected_version,
        _tamper_time,
        _tamper_audit,
        _tamper_idempotency,
        _tamper_stable_capability,
    ),
    ids=(
        "actor-type",
        "actor-id",
        "command-id",
        "command-type",
        "full-nested-payload",
        "target-scope",
        "expected-versions",
        "issued-at",
        "audit-context",
        "idempotency",
        "stable-capability",
    ),
)
def test_signature_rejects_every_authority_input_tamper(
    signer: GovernorCommandSigner,
    verifier: GovernorCommandVerifier,
    tamper: object,
) -> None:
    signed = signer.sign(_unsigned_command())

    assert verifier.verify(tamper(signed)) is False  # type: ignore[operator]


def test_unknown_key_and_wrong_key_material_fail_closed(
    signer: GovernorCommandSigner,
    verifier: GovernorCommandVerifier,
) -> None:
    signed = signer.sign(_unsigned_command())
    prefix, _, digest = signed.payload["actor_attestation"].split(":")
    payload = signed.model_dump(mode="python")["payload"]
    payload["actor_attestation"] = f"{prefix}:unknown:{digest}"
    unknown_key = signed.model_copy(
        update={"actor_capability_id": "govcap:unknown", "payload": payload}
    )
    mismatched_capability = signed.model_copy(
        update={"actor_capability_id": "govcap:secondary"}
    )
    wrong_key_verifier = GovernorCommandVerifier(
        {_KEY_ID: (_ACTOR_ID, _OTHER_SECRET)}
    )

    assert verifier.verify(unknown_key) is False
    assert verifier.verify(mismatched_capability) is False
    assert wrong_key_verifier.verify(signed) is False


@pytest.mark.parametrize(
    "attestation",
    (
        "",
        "unsigned",
        "govcmd-v1",
        "govcmd-v1:key",
        "govcmd-v1:key:abc",
        "govcmd-v1:key:" + ("A" * 64),
        "govcmd-v2:key:" + ("0" * 64),
        "govcmd-v1:key:extra:" + ("0" * 64),
        "govcmd-v1:key with space:" + ("0" * 64),
    ),
)
def test_malformed_capability_format_fails_closed(
    verifier: GovernorCommandVerifier,
    attestation: str,
) -> None:
    payload = _unsigned_command().model_dump(mode="python")["payload"]
    payload["actor_attestation"] = attestation
    malformed = _unsigned_command().model_copy(
        update={"actor_capability_id": f"govcap:{_KEY_ID}", "payload": payload}
    )

    assert verifier.verify(malformed) is False


@pytest.mark.parametrize(
    "update",
    (
        {"actor": Actor(actor_type="llm", actor_id=_ACTOR_ID)},
        {"actor": Actor(actor_type="governor", actor_id="governor-other")},
        {"command_type": "memory_proposal.submit"},
    ),
    ids=("actor-type", "actor-id", "command-type"),
)
def test_signer_only_issues_configured_governor_decision_authority(
    signer: GovernorCommandSigner,
    update: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        signer.sign(_unsigned_command().model_copy(update=update))


def test_configuration_has_no_default_allow_all_or_secret_repr() -> None:
    with pytest.raises(TypeError):
        GovernorCommandSigner()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        GovernorCommandVerifier()  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        GovernorCommandVerifier({})
    with pytest.raises(ValueError):
        GovernorCommandSigner(key_id=_KEY_ID, actor_id=_ACTOR_ID, secret=b"short")

    signer = GovernorCommandSigner(
        key_id=_KEY_ID,
        actor_id=_ACTOR_ID,
        secret=_SECRET,
    )
    verifier = GovernorCommandVerifier({_KEY_ID: (_ACTOR_ID, _SECRET)})
    secret_text = _SECRET.decode("ascii")
    assert secret_text not in repr(signer)
    assert secret_text not in repr(verifier)


def test_verifier_configuration_is_copied_immutable_and_final(
    signer: GovernorCommandSigner,
) -> None:
    source = {_KEY_ID: (_ACTOR_ID, _SECRET)}
    verifier = GovernorCommandVerifier(source)
    source.clear()

    assert verifier.verify(signer.sign(_unsigned_command())) is True
    with pytest.raises(AttributeError):
        setattr(verifier, "_authorities", {})
    with pytest.raises(TypeError):

        class _AllowAllVerifier(GovernorCommandVerifier):
            pass


def test_verifier_configuration_cannot_be_deleted_then_replaced() -> None:
    verifier = GovernorCommandVerifier({_KEY_ID: (_ACTOR_ID, _SECRET)})

    def delete_then_replace() -> None:
        delattr(verifier, "_authorities")
        setattr(verifier, "_authorities", {})

    with pytest.raises(AttributeError):
        delete_then_replace()
