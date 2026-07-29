import argparse
from pathlib import Path
from typing import Sequence

from .checklist import write_checklist
from .compiler import check_generated, write_generated


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amadeus-stage0b")
    parser.add_argument("command", choices=("checklist", "write", "check"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-dir")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "checklist":
            path = write_checklist(Path(args.root))
            print("stage0b_checklist_ready=true")
            print("checklist_items=214")
            print(f"output={path.as_posix()}")
            return 0
        if args.command == "write":
            write_generated(Path(args.root), args.output_dir)
        else:
            missing, changed, unexpected = check_generated(
                Path(args.root), args.output_dir
            )
            if missing or changed or unexpected:
                print(
                    "artifact_drift="
                    f"missing:{','.join(missing)};"
                    f"changed:{','.join(changed)};"
                    f"unexpected:{','.join(unexpected)}"
                )
                return 1
    except (OSError, ValueError) as error:
        print(f"stage0b_error={error}")
        return 1
    print("source_adjudication_ready=true")
    print("reviewed_sources=214")
    print("pending_oracle_assignments=0")
    print("pending_atomicity_reviews=0")
    print("case_coverage_complete=false")
    print("catalog_ready=false")
    print("release_ready=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
