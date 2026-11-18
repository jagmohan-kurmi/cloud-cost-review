import argparse
import json
import sys
from pathlib import Path
from .core import ingest, detect_spikes, markdown_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cost-review")
    parser.add_argument("csv")
    parser.add_argument("-o", "--output")
    parser.add_argument("--mad-threshold", type=float, default=3.0)
    parser.add_argument("--minimum-history", type=int, default=7)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)
    try:
        rows, errors = ingest(args.csv)
        findings = detect_spikes(rows, args.mad_threshold, args.minimum_history)
        payload = {"findings": findings, "errors": errors}
        report = json.dumps(payload, indent=2) if args.format == "json" else markdown_report(findings, errors)
        if args.output:
            Path(args.output).write_text(report, encoding="utf-8")
        else:
            sys.stdout.write(report)
        return 2 if not rows and errors else (1 if errors else 0)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
