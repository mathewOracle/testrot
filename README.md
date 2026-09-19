# testrot

**Find tests that pass without testing anything.**

A test that cannot fail is worse than no test. It reports green, it counts toward coverage, and it convinces everyone that a code path is protected when nothing is checking it at all. `testrot` finds these with AST analysis — no execution, no imports, no configuration.

```console
$ testrot tests/

test/test_poolmanager.py
    162: [MEDIUM] TR001 `assert p.key_fn_by_scheme == p.key_fn_by_scheme` compares a value to itself and always holds
         | assert p.key_fn_by_scheme == p.key_fn_by_scheme
         ? Test suites legitimately assert `x == x` to exercise a custom __eq__ or __hash__...

1 finding(s).
Confirm by mutation: break the covered behaviour and check the test fails.
```

That example is real. It became [urllib3#5267](https://github.com/urllib3/urllib3/pull/5267) — a test whose docstring promised *"each PoolManager gets a copy"* while asserting an object equalled itself. The rules here were built while finding and fixing defects in [networkx](https://github.com/networkx/networkx/pull/8917), urllib3, and others.

## Install

```console
pip install testrot                  # zero dependencies
pip install "testrot[langgraph]"     # + LangChain/LangGraph tools
```

## Use it as a CLI

```console
testrot .                       # scan the current tree
testrot tests/ --tests-only     # only test modules
testrot . --min-severity high   # only the near-certain findings
testrot . --format json         # machine-readable
testrot . --format github       # GitHub Actions annotations
testrot --list-rules
```

Exit code is `1` when findings exist, `0` when clean, `2` on error — so it drops straight into CI. Use `--exit-zero` to report without failing the build.

## Use it as a library

```python
import testrot

for finding in testrot.scan("./tests", min_severity=testrot.Severity.HIGH):
    print(finding.path, finding.line, finding.message)
```

## Use it in LangGraph

The reason this package exists: give a coding agent the ability to audit test quality.

```python
from langgraph.prebuilt import create_react_agent
from testrot.langgraph import get_tools

agent = create_react_agent("anthropic:claude-sonnet-4-5", get_tools())
result = agent.invoke({
    "messages": [{"role": "user", "content": "Audit ./tests and explain the worst finding."}]
})
print(result["messages"][-1].content)
```

Or take the prebuilt graph, which ships with a system prompt tuned to avoid overclaiming:

```python
from testrot.langgraph import build_graph

agent = build_graph("anthropic:claude-sonnet-4-5")
agent.invoke({"messages": [{"role": "user", "content": "What's rotten in ./tests?"}]})
```

Two tools are exposed: `scan_for_rotten_tests` and `list_testrot_rules`. Results are JSON, capped at 50 findings by default so a large repo cannot blow out the context window.

## Rules

| Code | Name | What it catches |
|---|---|---|
| `TR001` | `tautological-assert` | `assert x == x` — an expression compared to itself |
| `TR002` | `assert-on-tuple` | `assert (x == y, "msg")` — always true, stray comma |
| `TR003` | `shadowed-definition` | `def test_foo` twice; only the last one runs |
| `TR004` | `duplicate-dict-key` | `{1: "a", 1: "b"}` — first value silently discarded |
| `TR005` | `discarded-result` | A call's result overwritten before it is ever read |
| `TR006` | `uncalled-mock-assertion` | `m.assert_called_once` without `()` — never executes |

## On false positives

Every rule here has a legitimate counter-idiom, and pretending otherwise would make this tool useless:

- `assert x == x` is often a deliberate `__eq__`/`__hash__` reflexivity test.
- Some suites redefine a name on purpose, to test redefinition warnings or generated-method metadata.
- A discarded call result may be wanted for its side effect, like priming a cache.
- A name passed as a *decorator argument* is captured eagerly, so a later redefinition does not kill it. (`testrot` knows this one and stays quiet — it was a real false positive found on jinja's suite.)

So every finding carries a `caveat` field explaining how it could be innocent. Findings are ranked `HIGH` / `MEDIUM` / `LOW` by how hard they are to explain away, and the default `--min-severity medium` hides the speculative tail.

**Static analysis suggests; only mutation testing proves.** Before you report anything as a bug, break the behaviour the test claims to cover and confirm the test now fails. If it still passes, you have found real rot. If it fails, the test was fine and the tool was wrong — that workflow caught a bad patch of my own before it shipped.

## Extending

Rules are self-registering, so adding one never means touching the traversal, CLI, or LangGraph layers:

```python
import ast
from testrot import Finding, Severity, register
from testrot.analyzers.base import Analyzer

class NoBareExcept(Analyzer):
    code = "X001"
    name = "bare-except"
    description = "except: with no exception type"

    def visit_module(self, tree, path, source):
        return [
            Finding(path=path, line=n.lineno, rule=self.code,
                    message="bare except swallows everything",
                    severity=Severity.MEDIUM)
            for n in ast.walk(tree)
            if isinstance(n, ast.ExceptHandler) and n.type is None
        ]

register(NoBareExcept())
```

## Development

```console
uv venv && uv pip install -e ".[dev]"
pytest
ruff check . && mypy src
```

## License

MIT
