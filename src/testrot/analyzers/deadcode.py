"""TR005/TR006 -- computed values that are thrown away, and mock assertions
that were never actually invoked.
"""

from __future__ import annotations

import ast

from testrot.analyzers.base import Analyzer, register
from testrot.models import Finding, Severity

#: Real Mock assertion methods -- inert unless called.
MOCK_ASSERTIONS = frozenset(
    {
        "assert_called",
        "assert_called_once",
        "assert_called_with",
        "assert_called_once_with",
        "assert_any_call",
        "assert_has_calls",
        "assert_not_called",
        "assert_awaited",
        "assert_awaited_once",
        "assert_awaited_with",
        "assert_awaited_once_with",
        "assert_not_awaited",
    }
)

#: Attributes Mock does not define, so accessing them auto-creates a truthy
#: child mock and any assertion on them passes unconditionally.
PHANTOM_ATTRS = frozenset(
    {"called_once", "called_once_with", "not_called", "called_twice"}
)

#: Statements that end straight-line flow, so we stop looking for an overwrite.
CONTROL_FLOW = (
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.If,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Return,
    ast.Match,
)


def _names_read(node: ast.AST) -> set[str]:
    return {
        n.id
        for n in ast.walk(node)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }


def _sole_target(stmt: ast.Assign) -> str | None:
    if len(stmt.targets) != 1:
        return None
    target = stmt.targets[0]
    return target.id if isinstance(target, ast.Name) else None


class DiscardedResult(Analyzer):
    code = "TR005"
    name = "discarded-result"
    description = "a value computed from a call is overwritten before it is read"

    def visit_module(self, tree: ast.Module, path: str, source: str) -> list[Finding]:
        findings: list[Finding] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                findings.extend(self._scan_body(node.body, path, source, node.name))
        return findings

    def _scan_body(
        self, body: list[ast.stmt], path: str, source: str, scope: str
    ) -> list[Finding]:
        findings: list[Finding] = []
        for index, stmt in enumerate(body):
            if not isinstance(stmt, ast.Assign) or not isinstance(stmt.value, ast.Call):
                continue
            name = _sole_target(stmt)
            if name is None or name == "_":
                continue
            for later in body[index + 1 :]:
                if isinstance(later, CONTROL_FLOW) or name in _names_read(later):
                    break
                if isinstance(later, ast.Assign) and _sole_target(later) == name:
                    findings.append(
                        Finding(
                            path=path,
                            line=stmt.lineno,
                            rule=self.code,
                            message=(
                                f"`{name}` is assigned from a call and "
                                f"overwritten at line {later.lineno} without "
                                f"ever being read (in {scope})"
                            ),
                            severity=Severity.MEDIUM,
                            snippet=self.line_of(source, stmt.lineno),
                            caveat=(
                                "The discarded call may be kept for its side "
                                "effect, e.g. priming a cache or a database."
                            ),
                        )
                    )
                    break
        return findings


class UncalledMockAssertion(Analyzer):
    code = "TR006"
    name = "uncalled-mock-assertion"
    description = "a mock assertion is referenced but never called, so it never runs"

    def visit_module(self, tree: ast.Module, path: str, source: str) -> list[Finding]:
        invoked = {
            id(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        findings: list[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Attribute):
                attr = node.value
                if attr.attr in MOCK_ASSERTIONS and id(attr) not in invoked:
                    findings.append(
                        Finding(
                            path=path,
                            line=node.lineno,
                            rule=self.code,
                            message=(
                                f"`{ast.unparse(attr)}` is only looked up, never "
                                f"called -- the assertion never executes. Add `()`."
                            ),
                            severity=Severity.HIGH,
                            snippet=self.line_of(source, node.lineno),
                            caveat="",
                        )
                    )

            if not isinstance(node, ast.Assert):
                continue
            for sub in ast.walk(node.test):
                if not isinstance(sub, ast.Attribute):
                    continue
                if sub.attr in PHANTOM_ATTRS:
                    findings.append(
                        Finding(
                            path=path,
                            line=node.lineno,
                            rule=self.code,
                            message=(
                                f"`{ast.unparse(sub)}` is not a real Mock "
                                f"attribute; Mock auto-creates it as a truthy "
                                f"child, so this assert always passes"
                            ),
                            severity=Severity.HIGH,
                            snippet=self.line_of(source, node.lineno),
                            caveat="",
                        )
                    )
                elif sub.attr in MOCK_ASSERTIONS and id(sub) not in invoked:
                    findings.append(
                        Finding(
                            path=path,
                            line=node.lineno,
                            rule=self.code,
                            message=(
                                f"`assert {ast.unparse(sub)}` asserts a bound "
                                f"method object, which is always truthy. Add `()`."
                            ),
                            severity=Severity.HIGH,
                            snippet=self.line_of(source, node.lineno),
                            caveat="",
                        )
                    )
        return findings


register(DiscardedResult())
register(UncalledMockAssertion())
