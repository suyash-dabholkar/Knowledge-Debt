from __future__ import annotations
from typing import Dict, List

WEAK_THRESHOLD = 60.0


def _ancestors_of(target: str, kb: dict) -> set:
    """Every concept target depends on, directly or transitively."""
    seen = {target}
    stack = [target]
    while stack:
        current = stack.pop()
        for prereq in kb.get(current, {}).get("prerequisites", []):
            if prereq not in seen:
                seen.add(prereq)
                stack.append(prereq)
    return seen


def _topological_order(kb: dict) -> List[str]:
    """Every prerequisite appears before anything that depends on it."""
    visited, order = set(), []

    def visit(name: str):
        if name in visited:
            return
        visited.add(name)
        for prereq in kb.get(name, {}).get("prerequisites", []):
            visit(prereq)
        order.append(name)

    for name in kb:
        visit(name)
    return order


def find_root_gap(target_concept: str, mastery: Dict[str, float], kb: dict) -> Dict[str, object]:
    ancestors = _ancestors_of(target_concept, kb)
    chain = [c for c in _topological_order(kb) if c in ancestors]

    weak_concepts = [c for c in chain if mastery.get(c, 100.0) < WEAK_THRESHOLD]
    root_gap = weak_concepts[0] if weak_concepts else target_concept

    root_index = chain.index(root_gap)
    target_index = chain.index(target_concept)
    repair_path = chain[root_index: target_index + 1]

    return {"root_gap": root_gap, "weak_concepts": weak_concepts, "repair_path": repair_path}


def root_misconception_for(root_gap: str, kb: dict) -> str:
    misconceptions = kb.get(root_gap, {}).get("common_misconceptions", [])
    return misconceptions[0] if misconceptions else f"Student has not yet solidified the core idea behind {root_gap}."