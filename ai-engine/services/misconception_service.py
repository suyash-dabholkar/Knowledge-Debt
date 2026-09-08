"""
Lightweight misconception detection.

IMPORTANT: This service does NOT determine the student's root knowledge gap.
Member 1's diagnostic engine owns that decision. This service only identifies
likely misconceptions *during* the AI repair process (e.g. when a student
answers a practice question incorrectly), so the tutor can respond
intelligently instead of just saying "Incorrect."

Detection is primarily rule/keyword based for transparency and to guarantee a
deterministic fallback with zero LLM dependency. If an LLM is configured, we
prefer its structured output, but always fall back to the rules below.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

import llm as llm_module


# Each rule: (regex pattern matched against the student's answer text, misconception label/explanation)
_RULES = [
    (
        re.compile(r"\bstack\b", re.IGNORECASE),
        "BFS/DFS",
        "The student may be confusing BFS's queue-based level-order traversal with DFS's stack/recursion-based depth-first traversal.",
    ),
    (
        re.compile(r"deepest|dive deep|goes deep", re.IGNORECASE),
        "BFS/DFS",
        "The student may be describing DFS's depth-first behavior while believing it applies to BFS.",
    ),
    (
        re.compile(r"cannot find shortest|does not find shortest|no shortest path", re.IGNORECASE),
        "BFS/shortest-path",
        "The student may not realize that BFS's queue-based ordering guarantees the shortest path in unweighted graphs.",
    ),
    (
        re.compile(r"always find(s)? the shortest", re.IGNORECASE),
        "DFS/shortest-path",
        "The student may be conflating graph traversal with shortest-path guarantees — DFS finds *a* path, not necessarily the shortest one.",
    ),
    (
        re.compile(r"negative edge|negative weight", re.IGNORECASE),
        "Dijkstra/negative-weights",
        "The student may believe Dijkstra handles negative edge weights, when in fact its greedy guarantee breaks down with negative weights.",
    ),
    (
        re.compile(r"random access|o\(1\).*(insert|delete).*middle", re.IGNORECASE),
        "Array/LinkedList",
        "The student may be conflating array random-access performance with linked list traversal performance.",
    ),
]


def detect_misconception_from_text(answer_text: str) -> Optional[Dict[str, str]]:
    """Rule-based scan of a free-text or option-text answer for known misconception patterns."""
    for pattern, label, explanation in _RULES:
        if pattern.search(answer_text):
            return {"label": label, "explanation": explanation}
    return None


def analyze_wrong_answer(
    concept: str,
    question_text: str,
    student_answer: str,
    correct_answer: str,
) -> Dict[str, object]:
    """
    Returns a dict with keys: likely_misconception (str), hint (str),
    follow_up_question (dict, matching PracticeQuestion shape).

    Tries the LLM first (if configured), then falls back to rule-based
    detection with a deterministic follow-up question.
    """
    llm_result = llm_module.generate_misconception_followup(
        concept=concept,
        question_text=question_text,
        student_answer=student_answer,
        correct_answer=correct_answer,
    )
    if llm_result:
        return llm_result

    rule_match = detect_misconception_from_text(student_answer)
    if rule_match is None:
        rule_match = {
            "label": "general",
            "explanation": (
                f"The student's answer ('{student_answer}') doesn't match the expected answer "
                f"('{correct_answer}'); the specific misconception isn't automatically classified, "
                "so a general clarifying question is offered."
            ),
        }

    return {
        "likely_misconception": rule_match["explanation"],
        "hint": _fallback_hint_for_label(rule_match["label"], concept),
        "follow_up_question": _fallback_followup_for_label(rule_match["label"], concept),
    }


def _fallback_hint_for_label(label: str, concept: str) -> str:
    hints = {
        "BFS/DFS": "Think about which structure processes the FIRST discovered item first, versus the MOST recently discovered item first.",
        "BFS/shortest-path": "Consider what BFS's discovery order guarantees about distance from the source.",
        "DFS/shortest-path": "Consider whether diving deep down one branch guarantees you took the fewest steps.",
        "Dijkstra/negative-weights": "Consider what happens to a 'finalized' shortest distance if a later edge could make it even smaller.",
        "Array/LinkedList": "Consider what 'contiguous memory' does and doesn't give you for free.",
        "general": f"Re-read the core definition of {concept} and compare it carefully to your answer.",
    }
    return hints.get(label, hints["general"])


def _fallback_followup_for_label(label: str, concept: str) -> Dict[str, object]:
    if label == "BFS/DFS":
        return {
            "id": "followup_bfs_dfs",
            "difficulty": "easy",
            "question": "Which traversal strategy explores all nodes at the current distance before moving further away?",
            "options": ["DFS (stack-based)", "BFS (queue-based)", "Binary search", "Union-Find"],
            "correct_answer": "BFS (queue-based)",
            "explanation": "BFS's FIFO queue guarantees all nodes at the current distance are processed before any farther node.",
            "hint": "Think about FIFO vs LIFO ordering.",
        }
    if label == "BFS/shortest-path":
        return {
            "id": "followup_bfs_shortest",
            "difficulty": "easy",
            "question": "In an unweighted graph, what guarantees BFS finds the shortest path?",
            "options": [
                "It visits every node twice.",
                "It expands nodes strictly in order of increasing distance from the source.",
                "It sorts all nodes alphabetically first.",
                "It ignores nodes with more than 2 neighbors.",
            ],
            "correct_answer": "It expands nodes strictly in order of increasing distance from the source.",
            "explanation": "This ordering guarantee is the reason BFS reaches any node via its shortest route first.",
            "hint": "Think about what the queue preserves.",
        }
    if label == "DFS/shortest-path":
        return {
            "id": "followup_dfs_shortest",
            "difficulty": "easy",
            "question": "Why can't DFS guarantee the shortest path between two nodes?",
            "options": [
                "DFS refuses to visit nodes more than once.",
                "DFS has no mechanism prioritizing closer nodes — it just dives deep along one branch.",
                "DFS always visits nodes in reverse alphabetical order.",
                "DFS is identical to BFS.",
            ],
            "correct_answer": "DFS has no mechanism prioritizing closer nodes — it just dives deep along one branch.",
            "explanation": "DFS makes no distance-based ordering guarantee, unlike BFS.",
            "hint": "Think about whether DFS tracks distance from the source at all.",
        }
    if label == "Dijkstra/negative-weights":
        return {
            "id": "followup_dijkstra_negative",
            "difficulty": "medium",
            "question": "Why does a negative edge weight break Dijkstra's correctness guarantee?",
            "options": [
                "Negative weights aren't allowed as input syntax.",
                "A finalized shortest distance could later be shrunk further by a negative edge, violating Dijkstra's greedy assumption.",
                "Dijkstra can't use a priority queue with negative numbers.",
                "It doesn't — Dijkstra handles negative weights fine.",
            ],
            "correct_answer": "A finalized shortest distance could later be shrunk further by a negative edge, violating Dijkstra's greedy assumption.",
            "explanation": "Dijkstra assumes distances only grow as you explore further, which negative weights can violate.",
            "hint": "Think about what 'greedy and never revisited' assumes.",
        }
    return {
        "id": "followup_general",
        "difficulty": "easy",
        "question": f"Which statement best matches the core definition of {concept}?",
        "options": [f"The correct definition of {concept}", "An unrelated definition A", "An unrelated definition B", "An unrelated definition C"],
        "correct_answer": f"The correct definition of {concept}",
        "explanation": f"Revisiting the core definition of {concept} clarifies the confusion.",
        "hint": f"Re-read the core definition of {concept}.",
    }
