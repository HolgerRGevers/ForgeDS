"""Foreign key relationships and relational graph for ForgeDS.

Analogous to SQL's FOREIGN KEY constraints — models directed edges
between forms (tables) and supports topological ordering, reachability
queries, and cycle detection.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class ForeignKey:
    """A directed relationship: child_form.child_field -> parent_form.parent_field."""

    child_form: str
    child_field: str
    parent_form: str
    parent_field: str

    def __repr__(self) -> str:
        return (
            f"FK({self.child_form}.{self.child_field} "
            f"-> {self.parent_form}.{self.parent_field})"
        )


class RelationGraph:
    """Directed graph of FK relationships between forms.

    Edges go from child to parent (the dependency direction):
    a child form depends on its parent existing first.
    """

    def __init__(self) -> None:
        self._edges: list[ForeignKey] = []
        self._children_of: dict[str, list[ForeignKey]] = defaultdict(list)
        self._parents_of: dict[str, list[ForeignKey]] = defaultdict(list)
        self._forms: set[str] = set()

    def add(self, fk: ForeignKey) -> None:
        """Register a foreign key relationship."""
        self._edges.append(fk)
        self._children_of[fk.parent_form].append(fk)
        self._parents_of[fk.child_form].append(fk)
        self._forms.add(fk.child_form)
        self._forms.add(fk.parent_form)

    def parents_of(self, form: str) -> list[ForeignKey]:
        """Return FK edges where *form* is the child (its dependencies)."""
        return list(self._parents_of.get(form, []))

    def children_of(self, form: str) -> list[ForeignKey]:
        """Return FK edges where *form* is the parent (forms that depend on it)."""
        return list(self._children_of.get(form, []))

    def all_forms(self) -> set[str]:
        """Return all forms mentioned in any FK."""
        return set(self._forms)

    def all_edges(self) -> list[ForeignKey]:
        return list(self._edges)

    def topological_order(self, extra_forms: set[str] | None = None) -> list[str]:
        """Return forms in dependency order (parents before children).

        Forms with no dependencies come first. If *extra_forms* is provided,
        standalone forms (no FK edges) are included in the result.

        Raises ValueError if a cycle is detected.
        """
        forms = set(self._forms)
        if extra_forms:
            forms |= extra_forms

        # Kahn's algorithm
        in_degree: dict[str, int] = {f: 0 for f in forms}
        adj: dict[str, list[str]] = defaultdict(list)

        for fk in self._edges:
            # edge: parent -> child (parent must come first)
            adj[fk.parent_form].append(fk.child_form)
            in_degree[fk.child_form] = in_degree.get(fk.child_form, 0) + 1

        queue = sorted(f for f, d in in_degree.items() if d == 0)
        order: list[str] = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for child in sorted(adj.get(node, [])):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(order) != len(forms):
            missing = forms - set(order)
            raise ValueError(
                f"Cycle detected in FK graph involving: {', '.join(sorted(missing))}"
            )

        return order

    def has_cycle(self) -> bool:
        """Return True if the FK graph contains a cycle."""
        try:
            self.topological_order()
            return False
        except ValueError:
            return True
