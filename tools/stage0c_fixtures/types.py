# tools/stage0c_fixtures/types.py：不得 import 任何项目内模块
from dataclasses import dataclass
from typing import Literal


type JsonScalar = None | bool | int | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


class Stage0CError(Exception):
    __slots__ = ("code", "source", "detail")

    def __init__(
        self,
        code: str,
        *,
        source: str | None = None,
        detail: str = "",
    ) -> None:
        self.code = code
        self.source = source
        self.detail = detail
        text = code
        if source is not None:
            text += f":{source}"
        if detail:
            text += f":{detail}"
        super().__init__(text)


class FixtureInputError(Stage0CError):
    pass


class PublicationError(Stage0CError):
    pass


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    json_pointer: str
    code: str
    message: str


def _is_upper_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(ch in "0123456789ABCDEF" for ch in value)
    )


@dataclass(frozen=True, slots=True)
class PublicationResult:
    published: bool
    no_op: bool
    recovered: bool
    tree_sha256: str

    def __post_init__(self) -> None:
        if any(
            type(value) is not bool
            for value in (self.published, self.no_op, self.recovered)
        ):
            raise PublicationError(
                "publication_result_invalid",
                detail="boolean fields",
            )
        if self.published == self.no_op:
            raise PublicationError(
                "publication_result_invalid",
                detail="exactly one of published/no_op must be true",
            )
        if not _is_upper_sha256(self.tree_sha256):
            raise PublicationError(
                "publication_result_invalid",
                detail="tree_sha256",
            )


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    terminal: Literal["present", "absent"]
    tree_sha256: str | None
    changed: bool

    def __post_init__(self) -> None:
        if type(self.changed) is not bool:
            raise PublicationError(
                "recovery_result_invalid",
                detail="changed",
            )
        if self.terminal not in ("present", "absent"):
            raise PublicationError(
                "recovery_result_invalid",
                detail="terminal",
            )
        if (self.terminal == "absent") != (self.tree_sha256 is None):
            raise PublicationError(
                "recovery_result_invalid",
                detail="terminal/tree_sha256",
            )
        if self.tree_sha256 is not None and not _is_upper_sha256(
            self.tree_sha256
        ):
            raise PublicationError(
                "recovery_result_invalid",
                detail="tree_sha256",
            )


@dataclass(frozen=True, slots=True)
class PublicationProbeSpec:
    case_id: str
    journal_state: str
    disk_shape: str
    fault_point: str

    def to_json(self) -> JsonObject:
        return {
            "case_id": self.case_id,
            "journal_state": self.journal_state,
            "disk_shape": self.disk_shape,
            "fault_point": self.fault_point,
        }


@dataclass(frozen=True, slots=True)
class PublicationProbeOutcome:
    attempt_count: int
    executed: bool
    passed: bool
    terminal_tree_sha256: str | None
    actual: JsonValue
