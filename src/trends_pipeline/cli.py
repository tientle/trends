"""Command-line interface for validating and running the Trends pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from trends_pipeline.pipeline import run_pipeline, validate_files, write_validation_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trends-pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "run"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--input", type=Path, default=Path("data/raw/trends.csv"))
        subparser.add_argument("--manifest", type=Path, default=Path("data/raw/manifest.yaml"))
        if command == "validate":
            subparser.add_argument("--report", type=Path)
        else:
            subparser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
            subparser.add_argument("--report", type=Path, default=Path("reports/validation.json"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            report, _, _ = validate_files(args.input, args.manifest)
            if args.report:
                write_validation_report(args.report, report)
        else:
            report = run_pipeline(args.input, args.manifest, args.output_dir, args.report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as error:
        report = {"valid": False, "errors": [str(error)]}
        if getattr(args, "report", None):
            write_validation_report(args.report, report)
        print(json.dumps(report, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())