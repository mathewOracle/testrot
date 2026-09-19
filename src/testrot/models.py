"""Core data types shared by every analyzer.

Kept dependency-free on purpose: the analysis layer must not know whether it
is being driven by the CLI, a library call, or a LangGraph node.
"""

from __future__ import annotations

import dataclasses
import enum
from typing import Any


class Severity(enum.StrEnum):
    """How confident we are that a finding is a genuine defect.

    ``HIGH``   -- the code provably cannot do what it claims. Report it.
    ``MEDIUM`` -- almost certainly wrong, but a deliberate idiom could explain
                  it. Read the surrounding code before filing anything.
    ``LOW``    -- suspicious shape only. Triage fodder, never a bug report.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclasses.dataclass(frozen=True, slots=True)
class Finding:
    """A single suspected defect at a specific source location."""

    path: str
    line: int
    rule: str
    message: str
    severity: Severity = Severity.MEDIUM
    snippet: str = ""
    #: Why this might be a false positive. Displayed to humans and fed to LLM
    #: triage, because every rule here has a legitimate counter-idiom.
    caveat: str = ""

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.message}"
