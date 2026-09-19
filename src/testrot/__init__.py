"""Public API for testrot.

Find tests that pass without testing anything.
"""

from __future__ import annotations

from testrot.analyzers import load_builtin_analyzers
from testrot.analyzers.base import Analyzer, all_analyzers, register
from testrot.models import Finding, Severity
from testrot.scanner import scan, scan_file

load_builtin_analyzers()

__version__ = "0.1.0"

__all__ = [
    "Analyzer",
    "Finding",
    "Severity",
    "__version__",
    "all_analyzers",
    "register",
    "scan",
    "scan_file",
]
