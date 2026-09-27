"""Tests for the analyzers.

Each rule is checked in both directions: it fires on the defect, and it stays
silent on the legitimate idiom that resembles it. The negative cases are drawn
from real false positives observed on jinja, attrs, networkx and tox.
"""

from __future__ import annotations

import ast
import textwrap

import pytest

from testrot.analyzers.base import get_analyzers
from testrot.models import Severity
from testrot.scanner import scan


def findings_for(code: str, rule: str) -> list:
    source = textwrap.dedent(code)
    tree = ast.parse(source)
    analyzer = get_analyzers([rule])[0]
    return analyzer.visit_module(tree, "sample.py", source)


# -- TR001 tautological assert ----------------------------------------------


def test_tr001_flags_self_comparison():
    found = findings_for(
        """
        def test_copy():
            assert p.key_fn_by_scheme == p.key_fn_by_scheme
        """,
        "TR001",
    )
    assert len(found) == 1
    assert found[0].rule == "TR001"
    assert found[0].line == 3


def test_tr001_flags_pure_call_on_both_sides():
    found = findings_for("assert len(items) == len(items)", "TR001")
    assert len(found) == 1


def test_tr001_ignores_genuine_comparison():
    found = findings_for("assert p.key_fn_by_scheme == key_fn_by_scheme", "TR001")
    assert found == []


def test_tr001_ignores_impure_call_repeated():
    # next(it) == next(it) advances the iterator; the two sides really differ.
    found = findings_for("assert next(it) == next(it)", "TR001")
    assert found == []


def test_tr001_carries_a_caveat_about_reflexivity():
    found = findings_for("assert cfg == cfg", "TR001")
    assert "__eq__" in found[0].caveat


# -- TR002 assert on tuple ---------------------------------------------------


def test_tr002_flags_tuple_assert():
    found = findings_for("assert (x == y, 'should match')", "TR002")
    assert len(found) == 1
    assert found[0].severity == Severity.HIGH


def test_tr002_ignores_empty_tuple():
    found = findings_for("assert ()", "TR002")
    assert found == []


# -- TR003 shadowed definition -----------------------------------------------


def test_tr003_flags_redefined_test():
    found = findings_for(
        """
        def test_force_color():
            assert True

        def test_force_color():
            assert True
        """,
        "TR003",
    )
    assert len(found) == 1
    assert found[0].severity == Severity.HIGH
    assert "2x" in found[0].message


def test_tr003_ignores_overload_and_fixture_decorators():
    found = findings_for(
        """
        @overload
        def f(x: int) -> int: ...
        @overload
        def f(x: str) -> str: ...
        """,
        "TR003",
    )
    assert found == []


def test_tr003_ignores_name_captured_by_decorator_argument():
    """Regression: jinja's mark_dualiter binds the factory eagerly.

    The first make_users is passed as a decorator *argument*, so it is captured
    at decoration time and stays live despite the later redefinition.
    """
    found = findings_for(
        """
        def make_users():
            return ["foo"]

        @mark_dualiter("users", make_users)
        def test_join(users):
            assert users

        def make_users():
            return ["bar"]

        @mark_dualiter("users", make_users)
        def test_select(users):
            assert users
        """,
        "TR003",
    )
    assert found == []


def test_tr003_flags_duplicate_methods_in_class():
    found = findings_for(
        """
        class TestThing:
            def test_a(self):
                assert True
            def test_a(self):
                assert True
        """,
        "TR003",
    )
    assert len(found) == 1
    assert "class TestThing" in found[0].message


# -- TR004 duplicate dict key ------------------------------------------------


def test_tr004_flags_duplicate_key():
    found = findings_for("d = {1: 'cw', 2: 'ccw', 1: 'oops'}", "TR004")
    assert len(found) == 1
    assert found[0].severity == Severity.HIGH


def test_tr004_distinguishes_bool_from_int():
    # True == 1 in Python, but they are written as distinct literals; flagging
    # this would be more confusing than helpful.
    found = findings_for("d = {'a': 1, 'b': 2}", "TR004")
    assert found == []


# -- TR005 discarded result --------------------------------------------------


def test_tr005_flags_overwritten_call_result():
    found = findings_for(
        """
        def test_thing():
            mod = sm.MNLogit(endog, exog)
            mod = smf.mnlogit(formula, data)
            assert mod
        """,
        "TR005",
    )
    assert len(found) == 1


def test_tr005_ignores_value_that_is_read_first():
    found = findings_for(
        """
        def test_thing():
            r = get(url)
            check(r)
            r = get(other)
            assert r
        """,
        "TR005",
    )
    assert found == []


def test_tr005_ignores_underscore_throwaway():
    found = findings_for(
        """
        def test_thing():
            _ = list(gen())
            _ = list(other())
            assert True
        """,
        "TR005",
    )
    assert found == []


# -- TR006 uncalled mock assertion -------------------------------------------


def test_tr006_flags_missing_parentheses():
    found = findings_for(
        """
        def test_thing():
            m.assert_called_once
        """,
        "TR006",
    )
    assert len(found) == 1
    assert found[0].severity == Severity.HIGH


def test_tr006_flags_phantom_attribute():
    found = findings_for("assert m.called_once", "TR006")
    assert len(found) == 1
    assert "auto-creates" in found[0].message


def test_tr006_ignores_properly_called_assertion():
    found = findings_for(
        """
        def test_thing():
            m.assert_called_once_with(1)
            assert m.called
        """,
        "TR006",
    )
    assert found == []


# -- TR007 unreachable raises check -----------------------------------------


def test_tr007_flags_check_inside_raises_block():
    """Shape of the real langgraph test_tool_node_node_interrupt defect."""
    found = findings_for(
        """
        def test_interrupt():
            with pytest.raises(GraphBubbleUp) as exc_info:
                node.invoke({})
                assert exc_info.value == "foo"
        """,
        "TR007",
    )
    assert len(found) == 1
    assert found[0].line == 5
    assert found[0].severity == Severity.HIGH


def test_tr007_flags_unittest_and_async_forms():
    found = findings_for(
        """
        async def test_a(self):
            async with self.assertRaises(ValueError) as cm:
                await f()
                self.assertIn("bad", str(cm.exception))
        """,
        "TR007",
    )
    assert len(found) == 1


def test_tr007_ignores_check_after_the_block():
    found = findings_for(
        """
        def test_ok():
            with pytest.raises(ValueError) as exc_info:
                f()
            assert exc_info.value.args == ("x",)
        """,
        "TR007",
    )
    assert found == []


def test_tr007_ignores_other_statements_in_the_block():
    # Setup lines that don't touch the captured exception are fine.
    found = findings_for(
        """
        def test_ok():
            with pytest.raises(ValueError) as exc_info:
                pending = f()
                assert isawaitable(pending)
                g(pending)
        """,
        "TR007",
    )
    assert found == []


def test_tr007_ignores_unrelated_context_managers():
    found = findings_for(
        """
        def test_ok():
            with open(p) as fh:
                data = fh.read()
                assert fh.closed is False
        """,
        "TR007",
    )
    assert found == []


# -- scanner plumbing --------------------------------------------------------


def test_scan_reports_and_sorts(tmp_path):
    (tmp_path / "test_sample.py").write_text(
        textwrap.dedent(
            """
            def test_one():
                assert x == x

            def test_dup():
                assert {1: 'a', 1: 'b'}
            """
        )
    )
    findings = scan(tmp_path)
    assert len(findings) == 2
    # HIGH (duplicate key) must sort ahead of MEDIUM (tautology).
    assert findings[0].severity == Severity.HIGH


def test_scan_respects_min_severity(tmp_path):
    (tmp_path / "test_sample.py").write_text("def test_a():\n    assert x == x\n")
    assert scan(tmp_path, min_severity=Severity.MEDIUM)
    assert scan(tmp_path, min_severity=Severity.HIGH) == []


def test_scan_skips_excluded_directories(tmp_path):
    fixtures = tmp_path / "node_modules"
    fixtures.mkdir()
    (fixtures / "test_x.py").write_text("assert x == x\n")
    assert scan(tmp_path) == []


def test_scan_survives_unparseable_file(tmp_path):
    (tmp_path / "broken.py").write_text("def (((\n")
    assert scan(tmp_path) == []


def test_scan_rejects_unknown_rule(tmp_path):
    with pytest.raises(KeyError):
        scan(tmp_path, rules=["TR999"])


def test_tests_only_filter(tmp_path):
    (tmp_path / "app.py").write_text("assert x == x\n")
    assert scan(tmp_path)
    assert scan(tmp_path, tests_only=True) == []
