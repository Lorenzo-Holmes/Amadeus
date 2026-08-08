from __future__ import annotations

import pytest

from amadeus_core.contracts.requests import MemoryRequest


@pytest.mark.parametrize(
    ("request_type", "expected_event_type", "request_id", "event_id"),
    (
        (
            "confidentiality_request",
            "confidentiality_request_submitted",
            "req-a2",
            "evt-a2",
        ),
        (
            "correction_request",
            "correction_request_submitted",
            "req-a3",
            "evt-a3",
        ),
        (
            "non_mention_request",
            "non_mention_request_submitted",
            "req-a4",
            "evt-a4",
        ),
    ),
    ids=("confidentiality", "correction", "non-mention"),
)
def test_request_submit_records_only_request_and_bound_event(
    request_service,
    authority_probe,
    request_factory,
    request_command_factory,
    request_type: str,
    expected_event_type: str,
    request_id: str,
    event_id: str,
) -> None:
    request = request_factory(
        request_type,
        request_id=request_id,
        event_id=event_id,
    )
    command = request_command_factory(request, event_id=event_id)

    result = request_service.submit(command, request)

    assert result.error is None
    assert isinstance(result.value, MemoryRequest)
    assert result.value.status == "submitted"
    assert result.value.resulting_proposal_ids == ()
    assert result.value.resulting_decision_ids == ()
    assert result.event_ids == (event_id,)

    stored = authority_probe.request(request_id)
    assert stored == result.value
    event_type, event_payload = authority_probe.semantic_event(event_id)
    assert event_type == expected_event_type
    assert event_payload["request_id"] == request_id
    assert event_payload["request_type"] == request_type

    assert authority_probe.count("Proposal") == 0
    assert authority_probe.count("AutobiographicalMemory") == 0
    assert authority_probe.count("GovernorDecision") == 0
    assert authority_probe.receipt_event_ids(command.command_id) == (event_id,)

    replay = request_service.submit(command, request)
    assert replay.replayed is True
    assert replay.error is None
    assert isinstance(replay.value, MemoryRequest)
    assert replay.value == stored
    assert replay.event_ids == (event_id,)
    assert authority_probe.count("Proposal") == 0
    assert authority_probe.count("AutobiographicalMemory") == 0
    assert authority_probe.count("GovernorDecision") == 0
