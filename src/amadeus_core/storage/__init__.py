"""SQLite authority storage boundary."""

from .database import SQLiteDatabase, open_database
from .derived_views import (
    DerivedViewCASConflict,
    DerivedViewEntry,
    DerivedViewIntegrityError,
    DerivedViewScope,
    DerivedViewSnapshot,
    DerivedViewTransactionRequired,
    SQLiteDerivedViewStore,
    empty_derived_state_hash,
)
from .ledger import (
    LedgerAppendResult,
    LedgerReplayResult,
    LedgerVerification,
    append_session_event,
    deny_user_hard_delete,
    replay_ledger,
    verify_ledger_chain,
)
from .payloads import (
    ExternalPayloadAdapter,
    LedgerPayloadHashMismatch,
    LedgerPayloadMissing,
    LedgerPayloadResolver,
    MAX_RECEIPT_RESULT_BYTES,
    ReceiptResultTooLarge,
    SQLiteLedgerPayloadResolver,
    StoredLedgerPayload,
    prepare_external_payload,
    prepare_inline_payload,
)
from .repository import AuthorityRepository
from .reader import ProposalReadSnapshot, SQLiteAuthorityReader
from .records import ZERO_HASH, record_header, reseal_update, seal_record
from .unit_of_work import SQLiteUnitOfWork, UnitOfWork

__all__ = [
    "AuthorityRepository",
    "DerivedViewCASConflict",
    "DerivedViewEntry",
    "DerivedViewIntegrityError",
    "DerivedViewScope",
    "DerivedViewSnapshot",
    "DerivedViewTransactionRequired",
    "ExternalPayloadAdapter",
    "LedgerPayloadHashMismatch",
    "LedgerPayloadMissing",
    "LedgerPayloadResolver",
    "LedgerAppendResult",
    "LedgerReplayResult",
    "LedgerVerification",
    "MAX_RECEIPT_RESULT_BYTES",
    "ReceiptResultTooLarge",
    "ProposalReadSnapshot",
    "SQLiteDatabase",
    "SQLiteDerivedViewStore",
    "SQLiteAuthorityReader",
    "SQLiteLedgerPayloadResolver",
    "SQLiteUnitOfWork",
    "StoredLedgerPayload",
    "UnitOfWork",
    "ZERO_HASH",
    "append_session_event",
    "deny_user_hard_delete",
    "empty_derived_state_hash",
    "open_database",
    "prepare_external_payload",
    "prepare_inline_payload",
    "record_header",
    "reseal_update",
    "replay_ledger",
    "seal_record",
    "verify_ledger_chain",
]
