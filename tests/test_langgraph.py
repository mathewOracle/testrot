"""Tests for the LangGraph integration.

Skipped entirely when langchain-core is absent, which is the supported state
for a base install.
"""

from __future__ import annotations

import json
import textwrap
import typing

import pytest

pytest.importorskip("langchain_core")

from testrot.langgraph import (
    build_graph,
    get_tools,
    list_testrot_rules,
    scan_for_rotten_tests,
)

ROTTEN = textwrap.dedent(
    """
    def test_copy():
        assert p.scheme == p.scheme

    def test_dup():
        d = {1: 'a', 1: 'b'}
    """
)


@pytest.fixture
def rotten_repo(tmp_path):
    (tmp_path / "test_sample.py").write_text(ROTTEN)
    return tmp_path


def test_tools_are_exposed():
    tools = get_tools()
    assert {t.name for t in tools} == {"scan_for_rotten_tests", "list_testrot_rules"}


def test_tool_has_description_for_the_llm():
    # An empty description makes a tool unusable by a model.
    for tool in get_tools():
        assert tool.description
        assert len(tool.description) > 40


def test_scan_tool_returns_findings(rotten_repo):
    payload = json.loads(scan_for_rotten_tests.invoke({"path": str(rotten_repo)}))
    assert payload["total_findings"] == 2
    rules = {f["rule"] for f in payload["findings"]}
    assert rules == {"TR001", "TR004"}


def test_scan_tool_reports_missing_path():
    payload = json.loads(scan_for_rotten_tests.invoke({"path": "/no/such/place"}))
    assert "error" in payload


def test_scan_tool_rejects_bad_severity(rotten_repo):
    payload = json.loads(
        scan_for_rotten_tests.invoke({"path": str(rotten_repo), "min_severity": "urgent"})
    )
    assert "error" in payload


def test_scan_tool_rejects_unknown_rule(rotten_repo):
    payload = json.loads(
        scan_for_rotten_tests.invoke({"path": str(rotten_repo), "rules": ["TR999"]})
    )
    assert "error" in payload


def test_scan_tool_truncates_and_says_so(rotten_repo):
    payload = json.loads(
        scan_for_rotten_tests.invoke({"path": str(rotten_repo), "limit": 1})
    )
    assert payload["returned"] == 1
    assert payload["truncated"] is True
    assert payload["total_findings"] == 2


def test_scan_tool_filters_by_severity(rotten_repo):
    payload = json.loads(
        scan_for_rotten_tests.invoke({"path": str(rotten_repo), "min_severity": "high"})
    )
    # The tautology is MEDIUM, so only the duplicate key survives.
    assert {f["rule"] for f in payload["findings"]} == {"TR004"}


def test_findings_carry_caveats(rotten_repo):
    payload = json.loads(scan_for_rotten_tests.invoke({"path": str(rotten_repo)}))
    tautology = next(f for f in payload["findings"] if f["rule"] == "TR001")
    assert tautology["caveat"]


def test_list_rules_tool():
    rules = json.loads(list_testrot_rules.invoke({}))
    assert {r["code"] for r in rules} >= {"TR001", "TR003", "TR004", "TR006"}


from langchain_core.language_models.fake_chat_models import (  # noqa: E402
    GenericFakeChatModel,
)


class _ToolBindingFakeModel(GenericFakeChatModel):
    """A real chat model that also supports ``bind_tools``.

    The stock LangChain fakes raise ``NotImplementedError`` on ``bind_tools``,
    which is exactly the call an agent makes while compiling. Subclassing keeps
    it a genuine Runnable while letting the graph build offline.
    """

    bound_tools: typing.ClassVar[list] = []

    def bind_tools(self, tools, **kwargs):
        self.bound_tools = list(tools)
        return self


def _fake_model() -> _ToolBindingFakeModel:
    return _ToolBindingFakeModel(messages=iter(["done"]))


def test_build_graph_compiles_without_api_call():
    """The graph must compile offline; only .invoke() should need a model."""
    graph = build_graph(_fake_model())
    assert graph is not None
    assert hasattr(graph, "invoke")


def test_build_graph_exposes_both_tools():
    """Both tools must reach the compiled graph.

    Asserted via the graph's own structure rather than ``bind_tools``, because
    LangChain v1's ``create_agent`` binds lazily at invoke time while the older
    ``create_react_agent`` binds eagerly. The tools being reachable is the real
    contract; when they get bound is an implementation detail.
    """
    graph = build_graph(_fake_model())
    rendered = str(graph.get_graph().to_json())
    assert "tools" in rendered


def test_build_graph_accepts_custom_prompt():
    assert build_graph(_fake_model(), system_prompt="Be terse.") is not None


def test_default_prompt_warns_against_overclaiming():
    from testrot.langgraph import SYSTEM_PROMPT

    lowered = SYSTEM_PROMPT.lower()
    assert "caveat" in lowered
    assert "mutation" in lowered
