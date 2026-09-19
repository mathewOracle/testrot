# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-19

Initial release.

### Added

- Six AST rules for tests that cannot fail:
  - `TR001` tautological-assert -- `assert x == x`
  - `TR002` assert-on-tuple -- `assert (x == y, "msg")`
  - `TR003` shadowed-definition -- a name defined twice; earlier copies never run
  - `TR004` duplicate-dict-key -- `{1: "a", 1: "b"}`
  - `TR005` discarded-result -- a call's result overwritten before it is read
  - `TR006` uncalled-mock-assertion -- `m.assert_called_once` with no `()`
- `testrot` CLI with `text`, `json`, and `github` output formats, multi-path
  scanning, rule selection, severity filtering, and CI-friendly exit codes.
- LangGraph integration: `get_tools()` for binding to an existing agent and
  `build_graph()` for a prebuilt one. Compatible with both
  `langchain.agents.create_agent` (LangChain v1) and the older
  `langgraph.prebuilt.create_react_agent`.
- A `caveat` on every finding describing how it could be a false positive,
  surfaced to humans and to LLM triage alike.
- Self-registering analyzer API for third-party rules.

### Notes

The rules are derived from defects found and fixed upstream, including
[urllib3#5267](https://github.com/urllib3/urllib3/pull/5267) (tautological
assert) and [networkx#8917](https://github.com/networkx/networkx/pull/8917)
(duplicate dict key). Known-innocent idioms are filtered rather than reported --
notably names captured eagerly as decorator arguments, which look shadowed but
are live.

[0.1.0]: https://github.com/mathewOracle/testrot/releases/tag/v0.1.0
