"""TR007 -- assertions inside a ``pytest.raises`` block that can never run."""

from __future__ import annotations

import ast

from testrot.analyzers.base import Analyzer, register
from testrot.models import Finding, Severity

#: Context managers that catch an exception raised in their body. Anything
#: that inspects the captured exception has to run *after* the block exits.
RAISES_CONTEXTS = frozenset(
    {"raises", "assertRaises", "assertRaisesRegex", "assertWarns", "assertWarnsRegex"}
)


def _captured_name(item: ast.withitem) -> str | None:
    """Return ``exc`` for ``pytest.raises(E) as exc``, else None."""
    call = item.context_expr
    if not isinstance(call, ast.Call) or not isinstance(item.optional_vars, ast.Name):
        return None
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    return item.optional_vars.id if name in RAISES_CONTEXTS else None


def _reads(stmt: ast.stmt, names: set[str]) -> bool:
    return any(
        isinstance(node, ast.Name) and node.id in names and isinstance(node.ctx, ast.Load)
        for node in ast.walk(stmt)
    )


class UnreachableRaisesCheck(Analyzer):
    code = "TR007"
    name = "unreachable-raises-check"
    description = (
        "the captured exception is inspected inside its own `pytest.raises` "
        "block, after the line that raises, so the check never executes"
    )

    def visit_module(self, tree: ast.Module, path: str, source: str) -> list[Finding]:
        findings: list[Finding] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.With, ast.AsyncWith)):
                continue
            names = {n for n in map(_captured_name, node.items) if n}
            if not names:
                continue
            for stmt in node.body:
                if not _reads(stmt, names):
                    continue
                findings.append(
                    Finding(
                        path=path,
                        line=stmt.lineno,
                        rule=self.code,
                        message=(
                            f"`{ast.unparse(stmt).splitlines()[0]}` reads the "
                            f"captured exception inside the raises block; if the "
                            f"block raises as expected this line is skipped, so "
                            f"it never checks anything -- dedent it"
                        ),
                        severity=Severity.HIGH,
                        snippet=self.line_of(source, stmt.lineno),
                        caveat=(
                            "Only reachable if an earlier statement in the block "
                            "does *not* raise, in which case pytest.raises fails "
                            "the test anyway."
                        ),
                    )
                )
        return findings


register(UnreachableRaisesCheck())
