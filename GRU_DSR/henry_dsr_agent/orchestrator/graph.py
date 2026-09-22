"""A small dependency graph for asynchronous agent workflows."""

from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping, MutableMapping, Sequence
from typing import Any, TypeAlias

State: TypeAlias = MutableMapping[str, Any]
NodeResult: TypeAlias = Mapping[str, Any] | None
Node: TypeAlias = Callable[[Mapping[str, Any]], NodeResult | Awaitable[NodeResult]]


class StateGraph:
    """Execute dependency-ready nodes concurrently and merge their state updates."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._dependencies: dict[str, set[str]] = defaultdict(set)

    def add_node(self, name: str, node: Node) -> StateGraph:
        """Register a uniquely named node."""
        if name in self._nodes:
            raise ValueError(f"Node '{name}' is already registered")
        self._nodes[name] = node
        self._dependencies.setdefault(name, set())
        return self

    def add_edge(self, source: str, target: str) -> StateGraph:
        """Require ``source`` to finish before ``target`` runs."""
        if source not in self._nodes or target not in self._nodes:
            raise KeyError("Both edge endpoints must be registered nodes")
        self._dependencies[target].add(source)
        return self

    def add_sequence(self, names: Sequence[str]) -> StateGraph:
        """Connect existing nodes into a sequential chain."""
        for source, target in zip(names, names[1:], strict=False):
            self.add_edge(source, target)
        return self

    def add_parallel(
        self,
        branches: Mapping[str, Node],
        *,
        after: str | None = None,
    ) -> StateGraph:
        """Register independent nodes that become ready at the same time."""
        for name, node in branches.items():
            self.add_node(name, node)
            if after is not None:
                self.add_edge(after, name)
        return self

    async def run(self, initial_state: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Run the graph to completion and return accumulated state."""
        state: dict[str, Any] = dict(initial_state or {})
        pending = set(self._nodes)
        completed: set[str] = set()
        while pending:
            ready = [
                name
                for name in self._nodes
                if name in pending and self._dependencies[name] <= completed
            ]
            if not ready:
                blocked = ", ".join(sorted(pending))
                raise ValueError(f"State graph contains a cycle or blocked nodes: {blocked}")
            snapshot = dict(state)
            results = await asyncio.gather(
                *(self._run_node(self._nodes[name], snapshot) for name in ready)
            )
            merged_in_wave: dict[str, Any] = {}
            for name, updates in zip(ready, results, strict=True):
                for key, item in updates.items():
                    if key in merged_in_wave and merged_in_wave[key] != item:
                        raise ValueError(
                            f"Parallel nodes produced conflicting values for state key '{key}'"
                        )
                    merged_in_wave[key] = item
                completed.add(name)
                pending.remove(name)
            state.update(merged_in_wave)
        return state

    @staticmethod
    async def _run_node(node: Node, state: Mapping[str, Any]) -> dict[str, Any]:
        result = node(state)
        if inspect.isawaitable(result):
            result = await result
        if result is None:
            return {}
        if not isinstance(result, Mapping):
            raise TypeError("State graph nodes must return a mapping or None")
        return dict(result)
