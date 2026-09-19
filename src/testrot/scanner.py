"""Filesystem traversal and the public scanning API."""

from __future__ import annotations

import ast
import os
from collections.abc import Iterator
from pathlib import Path

from testrot.analyzers.base import DEFAULT_EXCLUDES, Analyzer, get_analyzers
from testrot.models import Finding, Severity

SEVERITY_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}


def iter_python_files(
    root: Path, excludes: frozenset[str] = DEFAULT_EXCLUDES
) -> Iterator[Path]:
    """Yield every ``.py`` file under ``root``, skipping excluded directories."""
    if root.is_file():
        if root.suffix == ".py":
            yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        # Pruning in place stops os.walk from descending -- much faster than
        # filtering afterwards on big trees.
        dirnames[:] = [d for d in dirnames if d not in excludes]
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                yield Path(dirpath) / filename


def scan_file(path: Path, analyzers: list[Analyzer], root: Path | None = None) -> list[Finding]:
    """Run ``analyzers`` against a single file, ignoring unparseable sources."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    display = str(path.relative_to(root)) if root and path.is_relative_to(root) else str(path)
    findings: list[Finding] = []
    for analyzer in analyzers:
        findings.extend(analyzer.visit_module(tree, display, source))
    return findings


def scan(
    path: str | Path,
    rules: list[str] | None = None,
    min_severity: Severity = Severity.LOW,
    tests_only: bool = False,
    excludes: frozenset[str] = DEFAULT_EXCLUDES,
) -> list[Finding]:
    """Scan a file or directory for rotten tests and dead assertions.

    Args:
        path: File or directory to analyze.
        rules: Rule codes/names to run (e.g. ``["TR001"]``). ``None`` runs all.
        min_severity: Drop findings below this confidence level.
        tests_only: Restrict to files that look like test modules.
        excludes: Directory names to skip.

    Returns:
        Findings sorted by severity, then file, then line.
    """
    root = Path(path).resolve()
    analyzers = get_analyzers(rules)
    threshold = SEVERITY_ORDER[min_severity]

    findings: list[Finding] = []
    for file in iter_python_files(root, excludes):
        if tests_only and not _looks_like_test(file):
            continue
        findings.extend(scan_file(file, analyzers, root if root.is_dir() else None))

    return sorted(
        (f for f in findings if SEVERITY_ORDER[f.severity] <= threshold),
        key=lambda f: (SEVERITY_ORDER[f.severity], f.path, f.line),
    )


def _looks_like_test(path: Path) -> bool:
    return (
        path.name.startswith("test_")
        or path.name.endswith("_test.py")
        or "tests" in path.parts
        or "test" in path.parts
    )
