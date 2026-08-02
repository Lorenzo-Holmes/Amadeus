"""SQLite authority storage boundary."""

from .database import SQLiteDatabase, open_database
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
from .unit_of_work import SQLiteUnitOfWork, UnitOfWork

__all__ = [
    "AuthorityRepository",
    "ExternalPayloadAdapter",
    "LedgerPayloadHashMismatch",
    "LedgerPayloadMissing",
    "LedgerPayloadResolver",
    "LedgerAppendResult",
    "LedgerReplayResult",
    "LedgerVerification",
    "MAX_RECEIPT_RESULT_BYTES",
    "ReceiptResultTooLarge",
    "SQLiteDatabase",
    "SQLiteLedgerPayloadResolver",
    "SQLiteUnitOfWork",
    "StoredLedgerPayload",
    "UnitOfWork",
    "append_session_event",
    "deny_user_hard_delete",
    "open_database",
    "prepare_external_payload",
    "prepare_inline_payload",
    "replay_ledger",
    "verify_ledger_chain",
]
