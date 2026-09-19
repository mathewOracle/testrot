"""Command-line interface.

Uses argparse rather than click/typer so the base install stays dependency-free.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from testrot import __version__
from testrot.analyzers.base import all_analyzers
from testrot.models import Finding, Severity
from testrot.scanner import scan

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="testrot",
        description="Find tests that pass without testing anything.",
        epilog="Static analysis suggests; only mutation testing proves. "
        "Break the behaviour and confirm the test fails before filing a bug.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="files or directories to scan (default: .)",
    )
    parser.add_argument(
        "--rule",
        action="append",
        dest="rules",
        metavar="CODE",
        help="run only this rule (repeatable), e.g. --rule TR001",
    )
    parser.add_argument(
        "--min-severity",
        choices=[s.value for s in Severity],
        default="medium",
        help="minimum severity to report (default: medium)",
    )
    parser.add_argument(
        "--tests-only",
        action="store_true",
        help="only analyze files that look like test modules",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "github"],
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--list-rules", action="store_true", help="list available rules and exit"
    )
    parser.add_argument(
        "--exit-zero",
        action="store_true",
        help="always exit 0, even when findings exist",
    )
    parser.add_argument("--version", action="version", version=f"testrot {__version__}")
    return parser


def _print_text(findings: list[Finding]) -> None:
    if not findings:
        print("No findings. Every assertion appears to earn its keep.")
        return
    current = ""
    for finding in findings:
        if finding.path != current:
            current = finding.path
            print(f"\n{current}")
        print(f"  {finding.line:>5}: [{finding.severity.upper()}] {finding.rule} {finding.message}")
        if finding.snippet:
            print(f"         | {finding.snippet}")
        if finding.caveat:
            print(f"         ? {finding.caveat}")
    print(f"\n{len(findings)} finding(s).")
    print("Confirm by mutation: break the covered behaviour and check the test fails.")


def _print_github(findings: list[Finding]) -> None:
    for f in findings:
        level = "error" if f.severity == Severity.HIGH else "warning"
        message = f.message.replace("\n", " ")
        print(f"::{level} file={f.path},line={f.line},title={f.rule}::{message}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.list_rules:
        for analyzer in sorted(all_analyzers(), key=lambda a: a.code):
            print(f"{analyzer.code}  {analyzer.name:<26} {analyzer.description}")
        return EXIT_OK

    paths = [Path(p).expanduser() for p in (args.paths or ["."])]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        print(f"testrot: path does not exist: {', '.join(missing)}", file=sys.stderr)
        return EXIT_ERROR

    try:
        findings: list[Finding] = []
        for target in paths:
            findings.extend(
                scan(
                    target,
                    rules=args.rules,
                    min_severity=Severity(args.min_severity),
                    tests_only=args.tests_only,
                )
            )
    except KeyError as exc:
        print(f"testrot: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.format == "json":
        print(json.dumps([f.as_dict() for f in findings], indent=2))
    elif args.format == "github":
        _print_github(findings)
    else:
        _print_text(findings)

    if args.exit_zero:
        return EXIT_OK
    return EXIT_FINDINGS if findings else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
