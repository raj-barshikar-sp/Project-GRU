"""Ensure the shared library and agents are importable.

`adk web` loads this folder as a package without adding the rest of the repo
to PYTHONPATH. Without this, you get: No module named 'mktg_core'.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PACKAGES = _REPO_ROOT / "packages"
for _path in (_REPO_ROOT, _PACKAGES):
    _s = str(_path)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from .agent import marketing_orchestrator, root_agent
from .app import build_app, build_runner

# `adk web` looks for a module-level `App` named `app` and only falls back to
# `root_agent` when it does not find one. Exporting `root_agent` alone means the
# UI runs the bare agent with no context cache config, so every transfer re-sends
# the whole prompt: the same tree costs several times more from the UI than from
# scripts/demo.py, which builds the runner properly. The name has to be `app`,
# which is also why this line shadows the `root.app` submodule as an attribute.
# Import from it as `from root.app import build_app`, never `import root.app`.
app = build_app()

__all__ = [
    "app", "build_app", "build_runner", "marketing_orchestrator", "root_agent",
]
