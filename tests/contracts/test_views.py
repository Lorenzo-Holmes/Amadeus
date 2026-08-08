from datetime import UTC, datetime, timedelta, timezone
from typing import Literal

import pytest
from pydantic import ValidationError

from amadeus_core.contracts.registry import AUTHORITATIVE_MODELS, TYPE_REGISTRY
from amadeus_core.contracts.validation import (
    compute_record_content_hash,
    validate_authoritative_record,
)
from amadeus_core.contracts.views import (
    ExpressionDecision,
    Instance,
    MaterializedViewManifest,
    RetrievalRequest,
)


NOW = datetime(2026, 8, 5, tzinfo=UTC)
ACTOR = {"actor_type": "amadeus", "actor_id": "amd-a"}


def _instance() -> Instance:
    return Instance(
        instance_id="ins-a",
        identity_id="idn-a",
        branch_id="brn-a",
        runtime_version="runtime-v1",
        governor_policy_version="policy-v1",
        model_backend_ref="model:test",
        terminal_refs=("terminal:main",),
        started_at=NOW,
        stopped_at=None,
    )


def _manifest() -> MaterializedViewManifest:
    return MaterializedViewManifest(
        view_id="viw-a",
        view_type="summary",
        identity_id="idn-a",
        branch_id="brn-a",
        vault_id="vlt-a",
        source_watermark_seq=0,
        source_root_hash="a" * 64,
        builder_version="view-builder-v1",
        built_at=NOW,
        view_hash="b" * 64,
    )


def _retrieval_request() -> RetrievalRequest:
    return RetrievalRequest(
        retrieval_id="ret-a",
        actor=ACTOR,
        intended_audience="user:test",
        identity_id="idn-a",
        lineage_id="lin-a",
        branch_id="brn-a",
        vault_id="vlt-a",
        principal_id="prn-a",
        capability_id="cap-a",
        operation="retrieve",
        query_ref="query:test",
        allowed_memory_states=("active",),
        max_results=20,
        purpose="response_context",
        policy_version="policy-v1",
        requested_at=NOW,
    )


def _expression_decision() -> ExpressionDecision:
    return ExpressionDecision(
        expression_id="exp-a",
        retrieval_id="ret-a",
        actor=ACTOR,
        intended_audience="user:test",
        identity_id="idn-a",
        lineage_id="lin-a",
        branch_id="brn-a",
        vault_id="vlt-a",
        principal_id="prn-a",
        capability_id="cap-a",
        operation="express",
        purpose="reflection",
        policy_version="policy-v1",
        selected_evidence_refs=("evt-a",),
        omitted_evidence_refs=("mem-a",),
        mode="express",
        reason_codes=("policy-allowed",),
        decided_at=NOW,
    )


def test_views_have_exact_canonical_field_order_and_construct() -> None:
    assert tuple(Instance.model_fields) == (
        "instance_id", "identity_id", "branch_id", "runtime_version",
        "governor_policy_version", "model_backend_ref", "terminal_refs",
        "started_at", "stopped_at",
    )
    assert tuple(MaterializedViewManifest.model_fields) == (
        "view_id", "view_type", "identity_id", "branch_id", "vault_id",
        "source_watermark_seq", "source_root_hash", "builder_version",
        "built_at", "view_hash",
    )
    assert tuple(RetrievalRequest.model_fields) == (
        "retrieval_id", "actor", "intended_audience", "identity_id",
        "lineage_id", "branch_id", "vault_id", "principal_id",
        "capability_id", "operation", "query_ref", "allowed_memory_states",
        "max_results", "purpose", "policy_version", "requested_at",
    )
    assert tuple(ExpressionDecision.model_fields) == (
        "expression_id", "retrieval_id", "actor", "intended_audience",
        "identity_id", "lineage_id", "branch_id", "vault_id", "principal_id",
        "capability_id", "operation", "purpose", "policy_version",
        "selected_evidence_refs", "omitted_evidence_refs", "mode",
        "reason_codes", "decided_at",
    )
    assert _instance().stopped_at is None
    assert _manifest().source_watermark_seq == 0
    assert _retrieval_request().allowed_memory_states == ("active",)
    assert _expression_decision().mode == "express"


@pytest.mark.parametrize(
    "factory",
    (_instance, _manifest, _retrieval_request, _expression_decision),
)
def test_views_are_frozen_strict_and_forbid_extra(factory) -> None:
    view = factory()
    assert view.model_config["extra"] == "forbid"
    assert view.model_config["frozen"] is True
    assert view.model_config["strict"] is True
    with pytest.raises(ValidationError):
        type(view).model_validate({**view.model_dump(), "unexpected": True})
    with pytest.raises(ValidationError):
        setattr(view, next(iter(type(view).model_fields)), "changed")


@pytest.mark.parametrize(
    ("factory", "field"),
    (
        (_instance, "started_at"),
        (_manifest, "built_at"),
        (_retrieval_request, "requested_at"),
        (_expression_decision, "decided_at"),
    ),
)
@pytest.mark.parametrize(
    "invalid_time",
    (datetime(2026, 8, 5), datetime(2026, 8, 5, tzinfo=timezone(timedelta(hours=8)))),
    ids=("naive", "non-utc"),
)
def test_view_times_reject_non_utc(factory, field: str, invalid_time: datetime) -> None:
    body = factory().model_dump(mode="python")
    body[field] = invalid_time
    with pytest.raises(ValidationError):
        type(factory()).model_validate(body)


@pytest.mark.parametrize("field", ("actor", "operation", "allowed_memory_states"))
def test_retrieval_request_rejects_invalid_capability_shape(field: str) -> None:
    body = _retrieval_request().model_dump(mode="python")
    body[field] = {
        "actor": {"actor_type": "user", "actor_id": "usr-a"},
        "operation": "express",
        "allowed_memory_states": ("active", "archived"),
    }[field]
    with pytest.raises(ValidationError):
        RetrievalRequest.model_validate(body)


@pytest.mark.parametrize("invalid", (0, 21, True))
def test_retrieval_request_max_results_is_strictly_bounded(invalid: object) -> None:
    body = _retrieval_request().model_dump(mode="python")
    body["max_results"] = invalid
    with pytest.raises(ValidationError):
        RetrievalRequest.model_validate(body)


@pytest.mark.parametrize("field", ("actor", "operation", "mode"))
def test_expression_decision_rejects_invalid_capability_shape(field: str) -> None:
    body = _expression_decision().model_dump(mode="python")
    body[field] = {
        "actor": {"actor_type": "user", "actor_id": "usr-a"},
        "operation": "retrieve",
        "mode": "emit",
    }[field]
    with pytest.raises(ValidationError):
        ExpressionDecision.model_validate(body)


@pytest.mark.parametrize("invalid", (-1, True))
def test_view_watermark_is_nonnegative_strict_int(invalid: object) -> None:
    body = _manifest().model_dump(mode="python")
    body["source_watermark_seq"] = invalid
    with pytest.raises(ValidationError):
        MaterializedViewManifest.model_validate(body)


def test_views_are_not_authoritative_or_writeable_through_public_boundaries(tmp_path) -> None:
    from amadeus_core.contracts.errors import CoreContractViolation
    from amadeus_core.storage import AuthorityRepository, open_database

    view_types = (Instance, MaterializedViewManifest, RetrievalRequest, ExpressionDecision)
    assert len(TYPE_REGISTRY) == len(AUTHORITATIVE_MODELS) == 17
    assert not {model.__name__ for model in view_types} & set(TYPE_REGISTRY)
    assert not {model.__name__ for model in view_types} & set(AUTHORITATIVE_MODELS)
    with pytest.raises(TypeError, match="unregistered authoritative model"):
        compute_record_content_hash(_manifest())
    with pytest.raises(CoreContractViolation):
        validate_authoritative_record("materialized_view_manifest", _manifest().model_dump())
    connection = open_database(tmp_path / "authority.db")
    try:
        with pytest.raises(CoreContractViolation):
            AuthorityRepository(connection).save_authoritative(
                "materialized_view_manifest", _manifest().model_dump()
            )
    finally:
        connection.close()


def _p1_view_models():
    import amadeus_core.contracts as contracts
    import amadeus_core.contracts.views as views

    model_names = ("RebuiltMaterializedViews", "DerivedViewFallback")
    missing = tuple(name for name in model_names if not hasattr(views, name))
    if missing:
        pytest.fail(f"missing P1 views models: {missing}")
    missing_exports = tuple(
        name
        for name in model_names
        if name not in views.__all__
        or not hasattr(contracts, name)
        or name not in contracts.__all__
    )
    if missing_exports:
        pytest.fail(f"missing P1 view exports: {missing_exports}")
    return (
        getattr(views, "RebuiltMaterializedViews"),
        getattr(views, "DerivedViewFallback"),
    )


def _five_manifests() -> tuple[MaterializedViewManifest, ...]:
    return tuple(
        MaterializedViewManifest(
            view_id=f"viw-{index}",
            view_type=view_type,
            identity_id="idn-a",
            branch_id="brn-a",
            vault_id="vlt-a",
            source_watermark_seq=7,
            source_root_hash="a" * 64,
            builder_version="view-builder-v1",
            built_at=NOW,
            view_hash=(format(index, "x") * 64)[:64],
        )
        for index, view_type in enumerate(
            ("summary", "timeline", "vector", "fulltext", "cue")
        )
    )


def test_rebuilt_materialized_views_enforces_exact_five_field_contract_and_derived_view_fallback() -> None:
    RebuiltMaterializedViews, DerivedViewFallback = _p1_view_models()
    assert tuple(RebuiltMaterializedViews.model_fields) == (
        "status",
        "identity_id",
        "lineage_id",
        "branch_id",
        "vault_id",
        "manifests",
        "source_watermark_seq",
        "source_root_hash",
    )
    assert tuple(DerivedViewFallback.model_fields) == (
        "status",
        "identity_id",
        "lineage_id",
        "branch_id",
        "vault_id",
        "authoritative_read_required",
        "source_watermark_seq",
        "source_root_hash",
        "validation_failure_event_id",
        "fallback_event_id",
    )
    assert (
        DerivedViewFallback.model_fields["authoritative_read_required"].annotation
        == Literal[True]
    )
    assert (
        DerivedViewFallback.model_json_schema()["properties"]
        ["authoritative_read_required"]["const"]
        is True
    )

    manifests = _five_manifests()
    rebuilt = RebuiltMaterializedViews(
        status="rebuilt",
        identity_id="idn-a",
        lineage_id="lin-a",
        branch_id="brn-a",
        vault_id="vlt-a",
        manifests=manifests,
        source_watermark_seq=7,
        source_root_hash="a" * 64,
    )
    assert rebuilt.manifests == manifests
    assert isinstance(rebuilt.manifests, tuple)

    invalid_manifest_sets = (
        manifests[:4],
        manifests + (manifests[-1],),
        (manifests[0], manifests[0], *manifests[2:]),
        (manifests[1], manifests[0], *manifests[2:]),
    )
    for invalid_manifests in invalid_manifest_sets:
        with pytest.raises(ValidationError):
            RebuiltMaterializedViews.model_validate(
                {**rebuilt.model_dump(mode="python"), "manifests": invalid_manifests}
            )
    with pytest.raises(ValidationError):
        RebuiltMaterializedViews.model_validate(
            {**rebuilt.model_dump(mode="python"), "manifests": list(manifests)}
        )

    for field, changed_value in (
        ("identity_id", "idn-b"),
        ("branch_id", "brn-b"),
        ("vault_id", "vlt-b"),
        ("source_watermark_seq", 8),
        ("source_root_hash", "c" * 64),
        ("builder_version", "view-builder-v2"),
    ):
        changed_manifest = manifests[1].model_copy(update={field: changed_value})
        changed_manifests = (manifests[0], changed_manifest, *manifests[2:])
        with pytest.raises(ValidationError):
            RebuiltMaterializedViews.model_validate(
                {
                    **rebuilt.model_dump(mode="python"),
                    "manifests": changed_manifests,
                }
            )

    with pytest.raises(ValidationError):
        RebuiltMaterializedViews.model_validate(
            {**rebuilt.model_dump(mode="python"), "unexpected": True}
        )
    with pytest.raises(ValidationError):
        setattr(rebuilt, "status", "fallback")

    fallback = DerivedViewFallback(
        status="fallback",
        identity_id="idn-a",
        lineage_id="lin-a",
        branch_id="brn-a",
        vault_id="vlt-a",
        authoritative_read_required=True,
        source_watermark_seq=7,
        source_root_hash="a" * 64,
        validation_failure_event_id="evt-faa1",
        fallback_event_id="evt-faa2",
    )
    assert fallback.authoritative_read_required is True
    for invalid in (False, 1, "true", object()):
        with pytest.raises(ValidationError):
            DerivedViewFallback.model_validate(
                {
                    **fallback.model_dump(mode="python"),
                    "authoritative_read_required": invalid,
                }
            )
    with pytest.raises(ValidationError):
        DerivedViewFallback.model_validate(
            {**fallback.model_dump(mode="python"), "status": "rebuilt"}
        )
    with pytest.raises(ValidationError):
        DerivedViewFallback.model_validate(
            {**fallback.model_dump(mode="python"), "unexpected": True}
        )
    with pytest.raises(ValidationError):
        setattr(fallback, "status", "rebuilt")

    non_authoritative_names = {
        RebuiltMaterializedViews.__name__,
        DerivedViewFallback.__name__,
    }
    assert not non_authoritative_names & set(TYPE_REGISTRY)
    assert not non_authoritative_names & set(AUTHORITATIVE_MODELS)
