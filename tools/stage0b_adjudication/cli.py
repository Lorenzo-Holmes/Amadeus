import argparse
from pathlib import Path
from typing import Sequence

from .checklist import write_checklist


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amadeus-stage0b")
    parser.add_argument("command", choices=("checklist",))
    parser.add_argument("--root", default=".")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        path = write_checklist(Path(args.root))
    except (OSError, ValueError) as error:
        print(f"stage0b_error={error}")
        return 1
    print("stage0b_checklist_ready=true")
    print("checklist_items=214")
    print(f"output={path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
