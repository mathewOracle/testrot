"""TR001 -- assertions that cannot fail."""

from __future__ import annotations

import ast

from testrot.analyzers.base import Analyzer, register
from testrot.models import Finding, Severity

#: Calls that are safe to evaluate twice, so `f(x) == f(x)` is still a
#: tautology rather than a meaningful comparison of two side effects.
PURE_BUILTINS = frozenset(
    {"len", "set", "sorted", "list", "tuple", "str", "int", "float", "abs", "type", "repr"}
)

REFLEXIVITY_CAVEAT = (
    "Test suites legitimately assert `x == x` to exercise a custom __eq__ or "
    "__hash__. Treat as a defect only when the surrounding docstring or test "
    "name promises a comparison against some *other* value."
)


def _is_pure_call(call: ast.Call) -> bool:
    return isinstance(call.func, ast.Name) and call.func.id in PURE_BUILTINS


def _structurally_equal(left: ast.AST, right: ast.AST) -> bool:
    """True when both sides are the same expression and free of side effects."""
    if ast.dump(left) != ast.dump(right):
        return False
    return all(
        _is_pure_call(node) for node in ast.walk(left) if isinstance(node, ast.Call)
    )


class TautologicalAssert(Analyzer):
    code = "TR001"
    name = "tautological-assert"
    description = "assert compares an expression to itself, so it can never fail"

    def visit_module(self, tree: ast.Module, path: str, source: str) -> list[Finding]:
        findings: list[Finding] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assert):
                continue
            test = node.test
            if (
                isinstance(test, ast.Compare)
                and len(test.ops) == 1
                and isinstance(test.ops[0], (ast.Eq, ast.Is, ast.LtE, ast.GtE))
                and _structurally_equal(test.left, test.comparators[0])
            ):
                findings.append(
                    Finding(
                        path=path,
                        line=node.lineno,
                        rule=self.code,
                        message=(
                            f"`assert {ast.unparse(test)}` compares a value to "
                            f"itself and always holds"
                        ),
                        severity=Severity.MEDIUM,
                        snippet=self.line_of(source, node.lineno),
                        caveat=REFLEXIVITY_CAVEAT,
                    )
                )
        return findings


class AssertOnTuple(Analyzer):
    code = "TR002"
    name = "assert-on-tuple"
    description = "assert on a non-empty tuple literal is always true"

    def visit_module(self, tree: ast.Module, path: str, source: str) -> list[Finding]:
        findings: list[Finding] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert) and isinstance(node.test, ast.Tuple):
                if not node.test.elts:
                    continue
                findings.append(
                    Finding(
                        path=path,
                        line=node.lineno,
                        rule=self.code,
                        message=(
                            "assert on a non-empty tuple is always true -- "
                            "likely a stray comma, e.g. `assert (x == y, 'msg')`"
                        ),
                        severity=Severity.HIGH,
                        snippet=self.line_of(source, node.lineno),
                        caveat="",
                    )
                )
        return findings


register(TautologicalAssert())
register(AssertOnTuple())
