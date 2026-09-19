"""Audit a repository for rotten tests using a LangGraph agent.

Usage:
    pip install "testrot[langgraph]" langchain-anthropic
    export ANTHROPIC_API_KEY=...
    python examples/langgraph_audit.py ./path/to/repo
"""

from __future__ import annotations

import sys

from testrot.langgraph import build_graph


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "."

    agent = build_graph("anthropic:claude-sonnet-4-5")
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Audit the tests in {target}. Report only findings you "
                        f"can justify, explain why each one matters, and say what "
                        f"mutation would confirm it."
                    ),
                }
            ]
        }
    )
    print(result["messages"][-1].content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
