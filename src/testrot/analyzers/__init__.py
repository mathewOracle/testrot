"""Built-in analyzers.

Importing a module is what registers its rules, so keep the imports inside a
function to make the side effect explicit rather than an import-order accident.
"""

from __future__ import annotations

_LOADED = False


def load_builtin_analyzers() -> None:
    """Import every built-in analyzer module exactly once."""
    global _LOADED
    if _LOADED:
        return
    from testrot.analyzers import deadcode, shadowing, tautology  # noqa: F401

    _LOADED = True
