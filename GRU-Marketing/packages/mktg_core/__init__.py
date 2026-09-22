"""Shared library for the Marketing Agents system.

Everything the seven domain agents have in common lives here: the data shapes,
the connectors to source systems, the calculations, and the deck renderer.

The one rule that governs this package: all arithmetic happens in `metrics/`,
never in an agent's prompt.
"""

__all__ = ["contracts", "connectors", "metrics", "rendering", "profile"]
