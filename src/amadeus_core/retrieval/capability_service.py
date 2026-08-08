"""Authoritative issue/revoke/expire lifecycle for VaultReadCapability only."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import cast

from pydantic import ValidationError

from amadeus_core.clock import Clock, SystemClock
from amadeus_core.contracts.commands import Actor, CommandExecutionContext, CommandResult, MutationCommandEnvelope
from amadeus_core.contracts.errors import CoreContractViolation, CoreError, CoreErrorCode, RETRYABLE_ERROR_CODES
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.vault import RelationshipVault, VaultReadCapability
from amadeus_core.ids import new_id
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.payloads import prepare_inline_payload
from amadeus_core.storage.records import ZERO_HASH, record_header, reseal_update, seal_record
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

from .capability_validator import AttestationVerifier, IssuerRegistry


_EVENT_BY_ACTION = {
    "issue": "vault_read_capability_issued",
    "revoke": "vault_read_capability_revoked",
    "expire": "vault_read_capability_expired",
}


def _error(command: MutationCommandEnvelope, code: CoreErrorCode, event_id: str | None = None) -> CoreError:
    return CoreError(
        error_id=new_id("error"), code=code, message=code.value,
        correlation_id=command.audit_context_id, audit_event_id=event_id,
        retryable=code in RETRYABLE_ERROR_CODES, details_ref=None,
    )


class VaultCapabilityService:
    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        issuer_registry: IssuerRegistry,
        attestation_verifier: AttestationVerifier,
        clock: Clock | None = None,
    ) -> None:
        self._database = database
        self._issuer_registry = issuer_registry
        self._attestation_verifier = attestation_verifier
        self._clock = SystemClock() if clock is None else clock
        self._unit_of_work = SQLiteUnitOfWork(database, clock=self._clock)

    def issue(self, command: MutationCommandEnvelope, capability: VaultReadCapability) -> CommandResult[VaultReadCapability]:
        try:
            snapshot = VaultReadCapability.model_validate(capability.model_dump(mode="python"))
        except ValidationError:
            return cast(CommandResult[VaultReadCapability], CommandResult(value=None, event_ids=(), error=_error(command, CoreErrorCode.HEADER_BODY_MISMATCH), replayed=False))
        return self._execute(command, "issue", snapshot.capability_id, snapshot, None)

    def revoke(self, command: MutationCommandEnvelope, capability_id: str, now: datetime) -> CommandResult[VaultReadCapability]:
        return self._execute(command, "revoke", capability_id, None, now)

    def expire(self, command: MutationCommandEnvelope, capability_id: str, now: datetime) -> CommandResult[VaultReadCapability]:
        return self._execute(command, "expire", capability_id, None, now)

    def find_expired(self, now: datetime) -> tuple[str, ...]:
        connection = self._database.connect()
        try:
            rows = connection.execute(
                "SELECT capability_id FROM capabilities WHERE capability_type = 'vault_read' AND status = 'active' AND expires_at <= ? ORDER BY capability_id",
                (now.isoformat().replace("+00:00", "Z"),),
            ).fetchall()
            return tuple(cast(str, row[0]) for row in rows)
        finally:
            connection.close()

    def _execute(self, command: MutationCommandEnvelope, action: str, capability_id: str, supplied: VaultReadCapability | None, now: datetime | None) -> CommandResult[VaultReadCapability]:
        command_type = f"vault_read_capability.{action}"
        denied_event_id = command.payload.get("denied_event_id")
        event_id = command.payload.get("event_id")
        requested_event_id = event_id if isinstance(event_id, str) else denied_event_id
        if command.command_type != command_type or command.actor.actor_type not in {"governor", "system"} or not isinstance(requested_event_id, str):
            return cast(CommandResult[VaultReadCapability], CommandResult(value=None, event_ids=(), error=_error(command, CoreErrorCode.HEADER_BODY_MISMATCH), replayed=False))

        def handler(repository: AuthorityRepository, mutation: MutationCommandEnvelope, context: CommandExecutionContext) -> CommandResult[object]:
            try:
                capability = supplied if action == "issue" else repository.get_validated(capability_id)
                if action == "issue":
                    if not isinstance(capability, VaultReadCapability):
                        raise CoreContractViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
                    code = self._validate_issue(mutation, capability)
                    if code is not None:
                        raise CoreContractViolation(code)
                    stored = repository.save_authoritative("vault_read_capability", capability.model_dump(mode="python"))
                    if not isinstance(stored, VaultReadCapability):
                        raise TypeError("wrong capability authority type")
                    event = self._append(repository, mutation, context, stored, cast(str, event_id), _EVENT_BY_ACTION[action], self._event_payload(stored, action), mutation.issued_at)
                else:
                    if not isinstance(capability, VaultReadCapability):
                        return CommandResult(
                            value=None,
                            event_ids=(),
                            error=_error(mutation, CoreErrorCode.HEADER_BODY_MISMATCH),
                            replayed=False,
                        )
                    if action == "revoke":
                        valid = capability.status == "active"
                    else:
                        valid = capability.status == "active" and now is not None and now >= capability.expires_at
                    if not valid:
                        raise CoreContractViolation(CoreErrorCode.INVALID_LIFECYCLE_TRANSITION)
                    status = "revoked" if action == "revoke" else "expired"
                    stored = cast(VaultReadCapability, reseal_update(capability, {"status": status, "version": capability.version + 1}))
                    stored = cast(VaultReadCapability, repository.save_authoritative("vault_read_capability", stored.model_dump(mode="python")))
                    event = self._append(repository, mutation, context, stored, cast(str, event_id), _EVENT_BY_ACTION[action], self._event_payload(stored, action), cast(datetime, now))
                return CommandResult(value=stored.model_dump(mode="json"), event_ids=(event.event_id,), error=None, replayed=False)
            except CoreContractViolation as error:
                denial = self._append_denial(repository, mutation, context, capability, requested_event_id, error.code)
                return CommandResult(value=None, event_ids=(denial.event_id,), error=_error(mutation, error.code, denial.event_id), replayed=False)

        try:
            raw = self._unit_of_work.execute_command(command, handler)
        except (CoreContractViolation, ValidationError):
            raw = CommandResult(value=None, event_ids=(), error=_error(command, CoreErrorCode.HEADER_BODY_MISMATCH), replayed=False)
        if raw.value is None:
            return cast(CommandResult[VaultReadCapability], raw)
        value = VaultReadCapability.model_validate_json(
            canonical_json(cast(Mapping[str, object], raw.value))
        )
        return CommandResult(value=value, event_ids=raw.event_ids, error=raw.error, replayed=raw.replayed)

    def _validate_issue(
        self,
        command: MutationCommandEnvelope,
        capability: VaultReadCapability,
    ) -> CoreErrorCode | None:
        now = self._clock.now()
        if now < capability.not_before:
            return CoreErrorCode.VAULT_CAPABILITY_BINDING
        if now >= capability.expires_at or capability.status == "expired":
            return CoreErrorCode.VAULT_CAPABILITY_EXPIRED
        if (
            capability.status != "active"
            or capability.version != 1
            or command.actor.actor_type != capability.issuer.actor_type
            or command.actor.actor_id != capability.issuer.actor_id
        ):
            return CoreErrorCode.VAULT_CAPABILITY_BINDING
        issuer = Actor(
            actor_type=capability.issuer.actor_type,
            actor_id=capability.issuer.actor_id,
        )
        try:
            trusted_issuer = self._issuer_registry.is_trusted(
                issuer, capability.policy_version
            )
        except Exception:
            trusted_issuer = False
        if trusted_issuer is not True:
            return CoreErrorCode.VAULT_CAPABILITY_BINDING
        payload_hash = sha256_hex(
            canonical_json(
                capability.model_dump(mode="python", exclude={"attestation"})
            )
        )
        try:
            valid_attestation = self._attestation_verifier.verify(
                capability.attestation, payload_hash
            )
        except Exception:
            valid_attestation = False
        if valid_attestation is not True:
            return CoreErrorCode.VAULT_CAPABILITY_BINDING
        return None

    def _event_payload(self, capability: VaultReadCapability, action: str) -> dict[str, object]:
        return {"capability_id": capability.capability_id, "status": capability.status, "version": capability.version, "action": action, "capability_content_hash": capability.record_header.content_hash}

    def _append_denial(self, repository: AuthorityRepository, command: MutationCommandEnvelope, context: CommandExecutionContext, capability: object, event_id: str, code: CoreErrorCode) -> LedgerEvent:
        if not isinstance(capability, VaultReadCapability):
            raise CoreContractViolation(code)
        return self._append(repository, command, context, capability, event_id, "vault_read_capability_denied", {"capability_id": capability.capability_id, "error_code": code.value}, command.issued_at)

    def _append(self, repository: AuthorityRepository, command: MutationCommandEnvelope, context: CommandExecutionContext, capability: VaultReadCapability, event_id: str, event_type: str, payload: Mapping[str, object], occurred_at: datetime) -> LedgerEvent:
        instance_id = command.payload.get("instance_id")
        if not isinstance(instance_id, str):
            raise CoreContractViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
        vault = repository.get_validated(capability.vault_id)
        if not isinstance(vault, RelationshipVault) or (vault.identity_id, vault.lineage_id, vault.branch_id) != (capability.identity_id, capability.lineage_id, capability.branch_id):
            raise CoreContractViolation(CoreErrorCode.VAULT_CAPABILITY_BINDING)
        head = repository.verified_ledger_head(capability.branch_id)
        if not isinstance(head, LedgerEvent):
            raise CoreContractViolation(CoreErrorCode.HASH_SCOPE_MISMATCH)
        stored_payload = prepare_inline_payload(payload)
        event = cast(LedgerEvent, seal_record(LedgerEvent, {
            "record_header": record_header("LedgerEvent", event_id, identity_id=capability.identity_id, lineage_id=capability.lineage_id, branch_id=capability.branch_id, created_at=occurred_at, created_by_event_id=event_id, deployment_policy_ref=capability.record_header.deployment_policy_ref),
            "event_id": event_id, "ledger_seq": head.ledger_seq + 1, "identity_id": capability.identity_id, "lineage_id": capability.lineage_id, "branch_id": capability.branch_id, "instance_id": instance_id, "vault_id": capability.vault_id, "event_type": event_type, "occurred_at": occurred_at, "ingested_at": command.issued_at, "actor_type": command.actor.actor_type, "actor_id": command.actor.actor_id, "mutation_command_id": context.command_id, "mutation_command_hash": context.command_hash, "payload_ref": stored_payload.payload_ref, "causation_id": None, "correlation_id": context.audit_context_id, "previous_event_hash": head.event_hash, "event_hash": ZERO_HASH, "version": 1,
        }))
        appended = repository.append_ledger_event(event.model_dump(mode="python"), payload=stored_payload)
        if not isinstance(appended, LedgerEvent):
            raise TypeError("wrong ledger event type")
        return appended


__all__ = ["VaultCapabilityService"]
