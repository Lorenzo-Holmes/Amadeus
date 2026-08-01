"""Generated common value objects for Core v0.1."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from decimal import Decimal
import math
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints, model_validator


_FORBIDDEN_KEY_MATERIAL_NAMES = frozenset({
    "raw_key",
    "private_key_bytes",
    "default_shared_key",
})


class FrozenMapping(Mapping[str, object]):
    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, object]) -> None:
        object.__setattr__(self, "_values", MappingProxyType(dict(values)))

    def __getitem__(self, key: str) -> object:
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __setattr__(self, name: str, value: object) -> None:
        raise TypeError("frozen contract mapping is immutable")

    def __deepcopy__(self, memo: dict[int, object]) -> "FrozenMapping":
        return self

    def __repr__(self) -> str:
        return repr(dict(self._values))


def _freeze_contract_value(value: object) -> object:
    if isinstance(value, FrozenModel):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise ValueError("binary values are outside the contract JSON domain")
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError("contract strings must be valid UTF-8") from error
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("contract numbers must be finite")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("contract numbers must be finite")
        return value
    if isinstance(value, datetime):
        if value.utcoffset() != timedelta(0):
            raise ValueError("contract datetime must use UTC")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("contract JSON object keys must be strings")
            try:
                key.encode("utf-8")
            except UnicodeEncodeError as error:
                raise ValueError("contract keys must be valid UTF-8") from error
            if key in _FORBIDDEN_KEY_MATERIAL_NAMES:
                raise ValueError(f"raw key material field is forbidden: {key}")
            frozen[key] = _freeze_contract_value(item)
        return FrozenMapping(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_contract_value(item) for item in value)
    raise ValueError(f"value is outside the contract JSON domain: {type(value).__qualname__}")


def _thaw_contract_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_contract_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_thaw_contract_value(item) for item in value)
    return value


def _serialize_json_object(value: Mapping[str, object]) -> dict[str, object]:
    return {key: _thaw_contract_value(item) for key, item in value.items()}


def _require_utc_datetime(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("datetime must use UTC")
    return value


UtcDatetime = Annotated[datetime, AfterValidator(_require_utc_datetime)]
RecordId = Annotated[str, StringConstraints(min_length=5, pattern=r"^[a-z]{3}-[0-9a-f]+(?:-[0-9a-f]+)*$")]
HashHex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
PositiveVersion = Annotated[int, Field(strict=True, ge=1)]
SingleUseLimit = Annotated[int, Field(strict=True, ge=1, le=1)]
RemainingUses = Annotated[int, Field(strict=True, ge=0, le=1)]
JsonObject = Annotated[
    Mapping[str, object],
    PlainSerializer(_serialize_json_object, return_type=dict[str, object]),
]
PayloadRef = str


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @model_validator(mode="after")
    def _freeze_nested_contract_values(self) -> Self:
        for field_name in type(self).model_fields:
            value = getattr(self, field_name)
            frozen = _freeze_contract_value(value)
            if frozen is not value:
                object.__setattr__(self, field_name, frozen)
        return self

    def model_copy(
        self,
        *,
        update: Mapping[str, object] | None = None,
        deep: bool = False,
    ) -> Self:
        del deep
        data = self.model_dump(mode="python")
        if update:
            data.update(update)
        return type(self).model_validate(data)

    def copy(
        self,
        *,
        include: object = None,
        exclude: object = None,
        update: Mapping[str, object] | None = None,
        deep: bool = False,
    ) -> Self:
        if include is not None or exclude is not None:
            raise TypeError("partial copies are outside the frozen contract")
        return self.model_copy(update=update, deep=deep)


class RecordHeader(FrozenModel):
    schema_version: Literal['0.1']
    record_type: str
    record_id: RecordId
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    created_at: UtcDatetime
    created_by_event_id: RecordId
    deployment_policy_ref: str
    canonicalization: Literal['core-canonical-json-v1']
    hash_algorithm: Literal['sha256']
    hash_scope_registry_version: Literal['core-hash-scope-registry-v0.1']
    hash_scope_registry_digest: HashHex
    hash_scope: tuple[str, ...]
    content_hash: HashHex

class Actor(FrozenModel):
    actor_type: Literal['user', 'llm', 'governor', 'maintainer', 'custodian_executor', 'system', 'amadeus']
    actor_id: str

class AuditContext(FrozenModel):
    context_id: str
    correlation_id: str
    actor_id: str
    actor_type: Literal['user', 'llm', 'governor', 'maintainer', 'custodian_executor', 'system', 'amadeus']
    capability_id: str
    purpose_code: str
    source_instance_id: str
    source_terminal_ref: str
    started_at: UtcDatetime

class ExpressionPolicy(FrozenModel):
    mode: Literal['eligible', 'restricted', 'non_mention', 'silent']
    reason_refs: tuple[RecordId, ...]

class ProposalActor(FrozenModel):
    actor_type: Literal['llm', 'user_adapter', 'system_detector', 'maintainer_adapter']
    actor_id: RecordId

class DeferConditions(FrozenModel):
    missing_evidence_types: tuple[str, ...]
    reopen_not_before: UtcDatetime | None

class VaultIssuer(FrozenModel):
    actor_type: Literal['governor', 'system']
    actor_id: RecordId

class IssuedToActor(FrozenModel):
    actor_type: Literal['llm', 'system', 'amadeus']
    actor_id: RecordId

class BreakGlassExecutor(FrozenModel):
    actor_type: Literal['custodian_executor']
    actor_id: RecordId

__all__ = [
    'FrozenModel',
    'RecordId',
    'HashHex',
    'PositiveVersion',
    'SingleUseLimit',
    'RemainingUses',
    'JsonObject',
    'PayloadRef',
    'UtcDatetime',
    'RecordHeader',
    'Actor',
    'AuditContext',
    'ExpressionPolicy',
    'ProposalActor',
    'DeferConditions',
    'VaultIssuer',
    'IssuedToActor',
    'BreakGlassExecutor',
]
