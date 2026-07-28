import argparse
import re
from pathlib import Path
from typing import Sequence

from .manifest import ProjectKBError, load_index


__all__ = ["main"]

_HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+(.*))?[ \t]*$")
_CLOSING_HEADING_SEQUENCE = re.compile(r"[ \t]+#+[ \t]*$")
_FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def _markdown_lines(text: str):
    fence_character: str | None = None
    fence_length = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        in_fence = fence_character is not None
        if fence_character is None:
            opening = _FENCE_OPEN.match(line)
            if opening is not None:
                marker, remainder = opening.groups()
                if marker[0] != "`" or "`" not in remainder:
                    fence_character = marker[0]
                    fence_length = len(marker)
                    in_fence = True
        else:
            indentation = len(line) - len(line.lstrip(" "))
            if indentation <= 3:
                candidate = line[indentation:]
                marker_length = len(candidate) - len(
                    candidate.lstrip(fence_character)
                )
                if (
                    marker_length >= fence_length
                    and candidate[marker_length:].strip(" \t") == ""
                ):
                    fence_character = None
                    fence_length = 0
        yield line_number, line, in_fence


def _positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "limit must be a positive integer"
        ) from error
    if parsed < 1:
        raise argparse.ArgumentTypeError(
            "limit must be a positive integer"
        )
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amadeus-project-kb")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="project root containing knowledge/manifest.json",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "check",
        help="validate policy, manifest, and content",
    )
    search = commands.add_parser(
        "search",
        help="search manifest-approved Markdown",
    )
    search.add_argument("query")
    search.add_argument("--limit", type=_positive_integer, default=20)
    return parser


def _check(root: Path) -> int:
    index = load_index(root)
    print("project_kb_ready=true")
    print(f"indexed_documents={len(index.documents)}")
    print("raw_paths_indexed=0")
    return 0


def _search(root: Path, query: str, limit: int) -> int:
    index = load_index(root)
    folded_query = query.casefold()
    hits = 0
    for document in index.documents:
        heading = document.title
        for line_number, line, in_fence in _markdown_lines(document.text):
            if not in_fence:
                heading_match = _HEADING.match(line)
                if heading_match is not None:
                    content = heading_match.group(1) or ""
                    content = _CLOSING_HEADING_SEQUENCE.sub("", content)
                    heading = content.strip(" \t")
            if folded_query not in line.casefold():
                continue
            print(
                f"{document.path}:{line_number} | "
                f"{heading} | {line}"
            )
            hits += 1
            if hits >= limit:
                print(f"hits={hits}")
                return 0
    print(f"hits={hits}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "check":
            return _check(arguments.root)
        return _search(
            arguments.root,
            arguments.query,
            arguments.limit,
        )
    except ProjectKBError as error:
        print(f"{error.category}={error.detail}")
        return 1
    except OSError as error:
        print(f"io_error={error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
