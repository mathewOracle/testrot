"""TR003/TR004 -- definitions and dict keys silently shadowed by a later twin.

A module that defines ``test_foo`` twice only ever runs the second one. pytest
reports no error and the coverage number barely moves, so the lost test can sit
dead for years. This rule found real lost coverage in networkx.
"""

from __future__ import annotations

import ast
from collections import defaultdict

from testrot.analyzers.base import Analyzer, register
from testrot.models import Finding, Severity

#: Decorators that make redefining a name the entire point.
INTENTIONAL_REDEFINITION = (
    "overload",
    "setter",
    "getter",
    "deleter",
    "register",
    "fixture",
    "validator",
    "default",
)


def _decorator_names(node: ast.AST) -> set[str]:
    decorators = getattr(node, "decorator_list", [])
    return {ast.unparse(d).split("(")[0] for d in decorators}


def _eagerly_captured(body: list[ast.stmt]) -> set[str]:
    """Names passed as decorator *arguments*, which binds them immediately.

    ``@mark_dualiter("users", make_users)`` captures whichever ``make_users``
    exists at decoration time, so a later redefinition does not kill the
    earlier one. Without this check the analyzer reports live code as dead --
    a false positive observed on jinja's test suite.
    """
    captured: set[str] = set()
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        for dec in getattr(node, "decorator_list", []):
            if not isinstance(dec, ast.Call):
                continue
            for arg in [*dec.args, *(kw.value for kw in dec.keywords)]:
                captured.update(
                    n.id for n in ast.walk(arg) if isinstance(n, ast.Name)
                )
    return captured


class ShadowedDefinition(Analyzer):
    code = "TR003"
    name = "shadowed-definition"
    description = "a function/class/method is redefined, so earlier copies never run"

    def visit_module(self, tree: ast.Module, path: str, source: str) -> list[Finding]:
        findings = self._scan_block(tree.body, path, source, "module")
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                findings.extend(
                    self._scan_block(node.body, path, source, f"class {node.name}")
                )
        return findings

    def _scan_block(
        self, body: list[ast.stmt], path: str, source: str, scope: str
    ) -> list[Finding]:
        captured = _eagerly_captured(body)
        seen: dict[str, list[int]] = defaultdict(list)
        for node in body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if any(
                d.endswith(INTENTIONAL_REDEFINITION) for d in _decorator_names(node)
            ):
                continue
            seen[node.name].append(node.lineno)

        findings: list[Finding] = []
        for name, lines in seen.items():
            if len(lines) < 2 or name in captured:
                continue
            is_test = name.startswith("test_")
            findings.append(
                Finding(
                    path=path,
                    line=lines[0],
                    rule=self.code,
                    message=(
                        f"{name!r} is defined {len(lines)}x in {scope} "
                        f"(lines {lines}); only the last definition survives"
                    ),
                    severity=Severity.HIGH if is_test else Severity.MEDIUM,
                    snippet=self.line_of(source, lines[0]),
                    caveat=(
                        "Some suites redefine a name deliberately to test "
                        "redefinition behaviour or generated-method metadata."
                    ),
                )
            )
        return findings


class DuplicateDictKey(Analyzer):
    code = "TR004"
    name = "duplicate-dict-key"
    description = "a dict literal repeats a key, silently discarding the first value"

    def visit_module(self, tree: ast.Module, path: str, source: str) -> list[Finding]:
        findings: list[Finding] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            seen: dict[tuple[str, object], int] = {}
            for key in node.keys:
                if not isinstance(key, ast.Constant):
                    continue
                if not isinstance(key.value, (str, int, float, bool)):
                    continue
                marker = (type(key.value).__name__, key.value)
                if marker in seen:
                    findings.append(
                        Finding(
                            path=path,
                            line=key.lineno,
                            rule=self.code,
                            message=(
                                f"duplicate key {key.value!r} (first at line "
                                f"{seen[marker]}); the earlier value is discarded"
                            ),
                            severity=Severity.HIGH,
                            snippet=self.line_of(source, key.lineno),
                            caveat="",
                        )
                    )
                seen[marker] = key.lineno
        return findings


register(ShadowedDefinition())
register(DuplicateDictKey())
