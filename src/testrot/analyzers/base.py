"""Analyzer base class and registry.

Each analyzer is a pure function of one parsed module, so adding a rule never
means touching the traversal, CLI, or LangGraph layers (open/closed).
"""

from __future__ import annotations

import abc
import ast

from testrot.models import Finding

#: Directories that are never worth analyzing. ``data`` and ``cases`` matter
#: more than they look: formatter/linter projects keep deliberately-broken
#: fixture code there, which produces pure noise.
DEFAULT_EXCLUDES: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".tox",
        ".nox",
        ".venv",
        "venv",
        "env",
        "build",
        "dist",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "_vendor",
        "vendor",
        "third_party",
        "site-packages",
        "data",
        "cases",
        "fixtures",
    }
)


class Analyzer(abc.ABC):
    """Base class for a single detection rule."""

    #: Stable identifier, e.g. ``"TR001"``. Used for selecting/ignoring rules.
    code: str
    #: Short human name, e.g. ``"tautological-assert"``.
    name: str
    #: One-line description shown by ``testrot rules``.
    description: str

    @abc.abstractmethod
    def visit_module(self, tree: ast.Module, path: str, source: str) -> list[Finding]:
        """Return findings for one parsed module."""

    # -- helpers shared by subclasses -------------------------------------

    @staticmethod
    def line_of(source: str, lineno: int) -> str:
        lines = source.splitlines()
        return lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""


_REGISTRY: dict[str, Analyzer] = {}


def register(analyzer: Analyzer) -> Analyzer:
    """Add an analyzer to the global registry, keyed by its code."""
    if analyzer.code in _REGISTRY:
        raise ValueError(f"duplicate analyzer code: {analyzer.code}")
    _REGISTRY[analyzer.code] = analyzer
    return analyzer


def all_analyzers() -> list[Analyzer]:
    return list(_REGISTRY.values())


def get_analyzers(select: list[str] | None = None) -> list[Analyzer]:
    """Resolve analyzers by code or name; ``None`` means all of them."""
    if not select:
        return all_analyzers()
    chosen: list[Analyzer] = []
    for key in select:
        match = next(
            (a for a in _REGISTRY.values() if key in (a.code, a.name)),
            None,
        )
        if match is None:
            known = ", ".join(sorted(a.code for a in _REGISTRY.values()))
            raise KeyError(f"unknown rule {key!r}; available: {known}")
        chosen.append(match)
    return chosen
