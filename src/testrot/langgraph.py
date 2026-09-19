"""LangGraph / LangChain integration.

Importing this module requires ``langchain-core``; install it with::

    pip install "testrot[langgraph]"

Two levels of integration are offered:

* :func:`get_tools` -- plain LangChain tools to bind to any agent you already
  have. Use this if you own the orchestration.
* :func:`build_graph` -- a prebuilt ReAct-style graph for the common case of
  "point an LLM at a repo and ask what's rotten".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from langchain_core.tools import tool
except ImportError as exc:  # pragma: no cover - exercised via import guard test
    raise ImportError(
        "testrot's LangGraph integration needs langchain-core. "
        'Install it with: pip install "testrot[langgraph]"'
    ) from exc

from testrot.analyzers.base import all_analyzers
from testrot.models import Severity
from testrot.scanner import scan

#: Cap on findings returned to an LLM. A 300-finding dump wrecks the context
#: window and buries the signal, which is the opposite of the point.
MAX_RESULTS = 50


@tool
def scan_for_rotten_tests(
    path: str,
    rules: list[str] | None = None,
    min_severity: str = "medium",
    tests_only: bool = False,
    limit: int = MAX_RESULTS,
) -> str:
    """Find tests that pass without testing anything, and dead assertions.

    Detects tautological asserts, tests shadowed by a later definition with the
    same name, duplicate dict keys, discarded call results, and mock assertions
    that were never invoked.

    Args:
        path: File or directory to scan.
        rules: Optional rule codes to run, e.g. ["TR001", "TR003"]. Omit for all.
        min_severity: One of "high", "medium", "low". Defaults to "medium".
        tests_only: If true, only analyze files that look like test modules.
        limit: Maximum findings to return.

    Returns:
        A JSON object with the total count and a list of findings. Each finding
        carries a "caveat" explaining how it could be a false positive -- read
        it before reporting anything as a bug.
    """
    target = Path(path).expanduser()
    if not target.exists():
        return json.dumps({"error": f"path does not exist: {path}"})

    try:
        severity = Severity(min_severity.lower())
    except ValueError:
        return json.dumps(
            {"error": f"min_severity must be high, medium or low; got {min_severity!r}"}
        )

    try:
        findings = scan(target, rules=rules, min_severity=severity, tests_only=tests_only)
    except KeyError as exc:
        return json.dumps({"error": str(exc)})

    capped = findings[: max(0, limit)]
    return json.dumps(
        {
            "total_findings": len(findings),
            "returned": len(capped),
            "truncated": len(capped) < len(findings),
            "findings": [f.as_dict() for f in capped],
        },
        indent=2,
    )


@tool
def list_testrot_rules() -> str:
    """List every available testrot rule with its code and description."""
    return json.dumps(
        [
            {"code": a.code, "name": a.name, "description": a.description}
            for a in all_analyzers()
        ],
        indent=2,
    )


def get_tools() -> list[Any]:
    """Return the testrot tools for binding to a LangGraph or LangChain agent.

    Example::

        from langgraph.prebuilt import create_react_agent
        from testrot.langgraph import get_tools

        agent = create_react_agent(model, get_tools())
    """
    return [scan_for_rotten_tests, list_testrot_rules]


SYSTEM_PROMPT = """You are a code review assistant specialising in test quality.

Use the testrot tools to find tests that pass without testing anything.

Rules you must follow when reporting:
1. Every finding includes a "caveat" field. Read it. Many flagged patterns are
   deliberate idioms -- `assert x == x` is often a genuine __eq__ reflexivity
   test, and some suites redefine names on purpose.
2. Never claim a finding is a confirmed bug from static analysis alone. Say what
   the code does, what it appears to intend, and what would confirm the gap.
3. The decisive check is mutation testing: break the behaviour the test claims
   to cover and confirm the test then fails. If it still passes, the test is
   not testing what its name says.
4. Prefer a few well-explained findings over an exhaustive dump.
"""


def build_graph(model: Any, system_prompt: str | None = None) -> Any:
    """Build a prebuilt ReAct agent wired to the testrot tools.

    Prefers ``langchain.agents.create_agent`` (LangChain v1) and falls back to
    ``langgraph.prebuilt.create_react_agent`` on older stacks, so this keeps
    working across the v1.0 reshuffle without emitting deprecation warnings on
    modern installs.

    Args:
        model: A LangChain chat model, or a model identifier string such as
            ``"anthropic:claude-sonnet-4-5"``.
        system_prompt: Override the default test-quality reviewer prompt.

    Returns:
        A compiled LangGraph agent, ready to ``.invoke(...)``.

    Example::

        from testrot.langgraph import build_graph

        agent = build_graph("anthropic:claude-sonnet-4-5")
        result = agent.invoke(
            {"messages": [{"role": "user", "content": "Audit ./tests"}]}
        )
        print(result["messages"][-1].content)
    """
    prompt = system_prompt or SYSTEM_PROMPT

    try:
        from langchain.agents import create_agent
    except ImportError:
        pass
    else:
        return create_agent(model, get_tools(), system_prompt=prompt)

    try:
        from langgraph.prebuilt import create_react_agent
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            'build_graph needs langgraph. Install: pip install "testrot[langgraph]"'
        ) from exc

    return create_react_agent(model, get_tools(), prompt=prompt)


__all__ = [
    "SYSTEM_PROMPT",
    "build_graph",
    "get_tools",
    "list_testrot_rules",
    "scan_for_rotten_tests",
]
