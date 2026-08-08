"""Non-authoritative frozen contracts for runtime and derived views."""

from collections.abc import Mapping
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .common import FrozenModel, HashHex, IssuedToActor, RecordId, UtcDatetime


_ViewWatermark = Annotated[int, Field(strict=True, ge=0)]
_RetrievalMaxResults = Annotated[int, Field(strict=True, ge=1, le=20)]
_Purpose = Literal["response_context", "reflection", "consolidation"]
_MaterializedViewTypes = ("summary", "timeline", "vector", "fulltext", "cue")


class Instance(FrozenModel):
    instance_id: RecordId
    identity_id: RecordId
    branch_id: RecordId
    runtime_version: str
    governor_policy_version: str
    model_backend_ref: str
    terminal_refs: tuple[str, ...]
    started_at: UtcDatetime
    stopped_at: UtcDatetime | None


class MaterializedViewManifest(FrozenModel):
    view_id: RecordId
    view_type: Literal["summary", "timeline", "vector", "fulltext", "cue"]
    identity_id: RecordId
    branch_id: RecordId
    vault_id: RecordId
    source_watermark_seq: _ViewWatermark
    source_root_hash: HashHex
    builder_version: str
    built_at: UtcDatetime
    view_hash: HashHex


class RebuiltMaterializedViews(FrozenModel):
    status: Literal["rebuilt"]
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    vault_id: RecordId
    manifests: tuple[MaterializedViewManifest, ...]
    source_watermark_seq: _ViewWatermark
    source_root_hash: HashHex

    @model_validator(mode="before")
    @classmethod
    def _require_manifest_tuple(cls, value: object) -> object:
        if isinstance(value, Mapping) and "manifests" in value:
            if type(value["manifests"]) is not tuple:
                raise ValueError("manifests must be a strict tuple")
        return value

    @model_validator(mode="after")
    def _require_complete_matching_manifests(self) -> Self:
        if len(self.manifests) != len(_MaterializedViewTypes):
            raise ValueError("manifests must contain exactly five entries")
        if tuple(manifest.view_type for manifest in self.manifests) != _MaterializedViewTypes:
            raise ValueError("manifests must use the canonical view-type order")
        for manifest in self.manifests:
            if (
                manifest.identity_id != self.identity_id
                or manifest.branch_id != self.branch_id
                or manifest.vault_id != self.vault_id
            ):
                raise ValueError("manifest scope must match rebuilt-view scope")
            if manifest.source_watermark_seq != self.source_watermark_seq:
                raise ValueError("manifest watermark must match rebuilt-view watermark")
            if manifest.source_root_hash != self.source_root_hash:
                raise ValueError("manifest root hash must match rebuilt-view root hash")
        builder_versions = {manifest.builder_version for manifest in self.manifests}
        if len(builder_versions) != 1:
            raise ValueError("all manifests must use one builder version")
        return self


class DerivedViewFallback(FrozenModel):
    status: Literal["fallback"]
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    vault_id: RecordId
    authoritative_read_required: Literal[True]
    source_watermark_seq: _ViewWatermark
    source_root_hash: HashHex
    validation_failure_event_id: RecordId
    fallback_event_id: RecordId

    @model_validator(mode="before")
    @classmethod
    def _require_builtin_true(cls, value: object) -> object:
        if isinstance(value, Mapping) and "authoritative_read_required" in value:
            required = value["authoritative_read_required"]
            if type(required) is not bool or required is not True:
                raise ValueError("authoritative_read_required must be built-in True")
        return value


class RetrievalRequest(FrozenModel):
    retrieval_id: RecordId
    actor: IssuedToActor
    intended_audience: str
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    vault_id: RecordId
    principal_id: RecordId
    capability_id: RecordId
    operation: Literal["retrieve"]
    query_ref: str
    allowed_memory_states: tuple[Literal["active"], ...]
    max_results: _RetrievalMaxResults
    purpose: _Purpose
    policy_version: str
    requested_at: UtcDatetime

    @model_validator(mode="after")
    def _require_only_active_memory_state(self) -> Self:
        if self.allowed_memory_states != ("active",):
            raise ValueError("allowed_memory_states must equal exactly ('active',)")
        return self


class ExpressionDecision(FrozenModel):
    expression_id: RecordId
    retrieval_id: RecordId
    actor: IssuedToActor
    intended_audience: str
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    vault_id: RecordId
    principal_id: RecordId
    capability_id: RecordId
    operation: Literal["express"]
    purpose: _Purpose
    policy_version: str
    selected_evidence_refs: tuple[RecordId, ...]
    omitted_evidence_refs: tuple[RecordId, ...]
    mode: Literal["express", "summarize", "defer", "silent"]
    reason_codes: tuple[str, ...]
    decided_at: UtcDatetime


__all__ = [
    "DerivedViewFallback",
    "ExpressionDecision",
    "Instance",
    "MaterializedViewManifest",
    "RebuiltMaterializedViews",
    "RetrievalRequest",
]
