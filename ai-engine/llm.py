"""
LLM provider abstraction for the Knowledge Debt AI Learning & Debt Repayment Engine.

The rest of the application only calls `generate_learning_content`,
`generate_misconception_followup`, and `generate_hint`. None of it needs to
know which LLM provider (if any) is configured.

If no LLM credentials are configured, or the LLM call fails/returns malformed
JSON, these functions fall back to deterministic, hand-authored demo content
so the API never breaks during a live demo.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

import prompts

load_dotenv()

logger = logging.getLogger("knowledge_debt.llm")

LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.anthropic.com/v1/messages").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6").strip()
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
LLM_RETRY_BACKOFF_SECONDS = float(os.getenv("LLM_RETRY_BACKOFF_SECONDS", "1"))


class LLMUnavailableError(Exception):
    """Raised internally when the LLM cannot be used; callers should fall back."""


def _llm_configured() -> bool:
    return bool(LLM_API_KEY)


def _extract_json(raw_text: str) -> Dict[str, Any]:
    """
    Extract a JSON object from raw LLM text output. Handles the common case of
    the model wrapping JSON in markdown fences despite instructions not to.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        # Strip a leading language tag like "json\n"
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    # Always isolate the outermost braces to strip any leading/trailing
    # commentary the model added despite instructions not to (e.g. a closing
    # remark after the JSON, or a leading "Here is the JSON:" preamble).
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    return json.loads(text)


def _call_anthropic(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    """
    Calls the Anthropic Messages API and parses a JSON object from the reply.

    Retries transient network/HTTP failures (LLM_MAX_RETRIES attempts, with a
    short linear backoff) before giving up. A malformed-JSON response is NOT
    retried with the same prompt (retrying wouldn't change a deterministic
    parsing failure) — it goes straight to the fallback.
    """
    if not _llm_configured():
        raise LLMUnavailableError("No LLM_API_KEY configured")

    headers = {
        "x-api-key": LLM_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "max_tokens": 2000,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    last_error: Optional[Exception] = None
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=LLM_TIMEOUT_SECONDS) as client:
                response = client.post(LLM_API_URL, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            break
        except httpx.HTTPError as exc:
            last_error = exc
            logger.warning("LLM request attempt %d/%d failed: %s", attempt, LLM_MAX_RETRIES, exc)
            if attempt < LLM_MAX_RETRIES:
                time.sleep(LLM_RETRY_BACKOFF_SECONDS * attempt)
    else:
        raise LLMUnavailableError(str(last_error))

    content_blocks = data.get("content", [])
    text_parts = [block.get("text", "") for block in content_blocks if block.get("type") == "text"]
    raw_text = "\n".join(text_parts).strip()

    if not raw_text:
        raise LLMUnavailableError("LLM returned no text content")

    try:
        return _extract_json(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("LLM returned malformed JSON: %s", exc)
        raise LLMUnavailableError("LLM returned malformed JSON") from exc


# ---------------------------------------------------------------------------
# Public API used by services/
# ---------------------------------------------------------------------------

def generate_learning_content(
    student_id: str,
    concept: str,
    student_level: str,
    root_gap: str,
    root_misconception: str,
    weak_concepts: List[str],
    repair_path: List[str],
    concept_context: Dict[str, Any],
    reinforced_misconceptions: Optional[List[str]] = None,
    attempt_number: int = 1,
) -> Dict[str, Any]:
    """
    Returns a dict matching the /learn content schema (diagnosis, explanation,
    analogy, example, key_points, practice_questions, next_step,
    estimated_minutes), plus a "source" key of "llm" or "fallback".

    reinforced_misconceptions and attempt_number let the caller (learning_service,
    informed by services/student_state.py) close the loop between /practice
    (where misconceptions surface) and /learn (where they get taught to).
    """
    if _llm_configured():
        user_prompt = prompts.build_learning_prompt(
            student_id=student_id,
            concept=concept,
            student_level=student_level,
            root_gap=root_gap,
            root_misconception=root_misconception,
            weak_concepts=weak_concepts,
            repair_path=repair_path,
            concept_context=concept_context,
            reinforced_misconceptions=reinforced_misconceptions,
            attempt_number=attempt_number,
        )
        try:
            result = _call_anthropic(prompts.SYSTEM_PROMPT, user_prompt)
            result["source"] = "llm"
            return result
        except LLMUnavailableError as exc:
            logger.info("Falling back to deterministic content: %s", exc)

    return _fallback_learning_content(
        concept=concept,
        student_level=student_level,
        root_gap=root_gap,
        root_misconception=root_misconception,
        repair_path=repair_path,
        concept_context=concept_context,
        reinforced_misconceptions=reinforced_misconceptions,
    )


def generate_misconception_followup(
    concept: str,
    question_text: str,
    student_answer: str,
    correct_answer: str,
) -> Dict[str, Any]:
    """Returns likely_misconception, hint, and follow_up_question for a wrong answer."""
    if _llm_configured():
        user_prompt = prompts.build_misconception_prompt(
            concept=concept,
            question_text=question_text,
            student_answer=student_answer,
            correct_answer=correct_answer,
        )
        try:
            return _call_anthropic(prompts.SYSTEM_PROMPT, user_prompt)
        except LLMUnavailableError as exc:
            logger.info("Falling back to rule-based misconception detection: %s", exc)

    return None  # Caller (misconception_service) supplies the rule-based fallback


def generate_hint(concept: str, question_text: str, student_level: str) -> Optional[str]:
    if _llm_configured():
        user_prompt = prompts.build_hint_prompt(concept, question_text, student_level)
        try:
            result = _call_anthropic(prompts.SYSTEM_PROMPT, user_prompt)
            return result.get("hint")
        except LLMUnavailableError as exc:
            logger.info("Hint fallback triggered: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Deterministic fallback content (mandatory — must work with zero LLM keys)
# ---------------------------------------------------------------------------

def _fallback_learning_content(
    concept: str,
    student_level: str,
    root_gap: str,
    root_misconception: str,
    repair_path: List[str],
    concept_context: Dict[str, Any],
    reinforced_misconceptions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Deterministic demo content. Specifically hand-authored for the primary
    hackathon demo scenario (Dijkstra failure -> BFS/DFS root gap -> BFS
    repair), with a generic-but-still-grounded template for other concepts
    so the API never breaks regardless of input.
    """
    concept_key = _match_concept_key(concept, concept_context)

    if concept_key == "BFS":
        branch = "bfs_fallback"
        content = _bfs_fallback()
    elif concept_key == "DFS":
        branch = "dfs_fallback"
        content = _dfs_fallback()
    elif concept_key == "Dijkstra":
        branch = "dijkstra_fallback"
        content = _dijkstra_fallback()
    else:
        branch = "generic_fallback"
        content = _generic_fallback(concept_key or concept, concept_context)

    logger.info("Fallback content generated via %s for concept=%s", branch, concept)

    diagnosis_text = (
        f"Based on the diagnosis, the real blocker isn't \"{concept}\" itself — it's this: "
        f"{root_misconception}"
    )
    if reinforced_misconceptions:
        joined = "; ".join(reinforced_misconceptions)
        diagnosis_text += f" Practice attempts also showed: {joined}."

    content["diagnosis"] = diagnosis_text
    content["source"] = "fallback"

    next_step = _next_step_in_path(concept_key or concept, repair_path)
    content["next_step"] = next_step

    return content


def _match_concept_key(concept: str, concept_context: Dict[str, Any]) -> Optional[str]:
    if concept in concept_context:
        return concept
    lowered = concept.strip().lower()
    for key in concept_context.keys():
        if key.lower() == lowered:
            return key
    return None


def _next_step_in_path(concept: str, repair_path: List[str]) -> str:
    try:
        idx = repair_path.index(concept)
    except ValueError:
        return repair_path[0] if repair_path else concept
    if idx + 1 < len(repair_path):
        return repair_path[idx + 1]
    return f"Review and reassess {concept} to confirm the debt is repaid."


def _bfs_fallback() -> Dict[str, Any]:
    return {
        "explanation": (
            "BFS (Breadth-First Search) explores a graph level by level, starting from the "
            "source node. It uses a QUEUE (first-in, first-out): the first node you discover "
            "is the first one you expand next. This is the opposite of DFS, which uses a STACK "
            "(last-in, first-out) and dives deep down one path before backtracking. Because BFS "
            "always expands nodes in the order they were discovered, it guarantees every node is "
            "visited in increasing order of distance (number of edges) from the source. That "
            "ordering guarantee is exactly why BFS finds the SHORTEST PATH in an unweighted "
            "graph — and it's the same core idea that Dijkstra's algorithm later generalizes to "
            "weighted graphs using a priority queue instead of a plain queue."
        ),
        "analogy": (
            "Picture ripples spreading outward from a stone dropped in a pond. The ripple one "
            "ring out from the stone reaches every point at that distance before the next ring "
            "starts — nothing skips ahead. That's BFS: it finishes visiting everything at "
            "distance 1 before moving to distance 2. DFS is different — it's like following one "
            "single corridor in a maze as deep as it goes before backtracking to try another "
            "corridor."
        ),
        "example": (
            "Graph: A-B, A-C, B-D, C-D. BFS from A:\n"
            "1. Queue = [A]. Visit A (distance 0). Enqueue neighbors B, C. Queue = [B, C]\n"
            "2. Visit B (distance 1). Enqueue D. Queue = [C, D]\n"
            "3. Visit C (distance 1). D already enqueued. Queue = [D]\n"
            "4. Visit D (distance 2).\n"
            "Visit order: A, B, C, D — exactly ordered by distance from A, because the queue "
            "preserves discovery order."
        ),
        "key_points": [
            "BFS uses a queue (FIFO); DFS uses a stack (LIFO) or recursion.",
            "BFS visits nodes in strictly non-decreasing order of distance from the source.",
            "This ordering guarantee is why BFS finds shortest paths in unweighted graphs.",
            "DFS has no such distance guarantee — it finds *a* path, not necessarily the shortest.",
            "Dijkstra = BFS + a priority queue, to handle weighted edges instead of uniform ones.",
        ],
        "practice_questions": [
            {
                "id": "bfs_q1",
                "difficulty": "easy",
                "question": "Which data structure does BFS use to decide which node to visit next?",
                "options": ["Stack", "Queue", "Priority Queue", "Hash Map"],
                "correct_answer": "Queue",
                "explanation": (
                    "BFS uses a FIFO queue so nodes are expanded in the order they were "
                    "discovered, which produces the level-by-level traversal order."
                ),
                "hint": "Think about which structure processes items in the same order they arrive.",
            },
            {
                "id": "bfs_q2",
                "difficulty": "medium",
                "question": (
                    "In an unweighted graph, why does BFS starting from node A find the shortest "
                    "path (fewest edges) to every other node?"
                ),
                "options": [
                    "Because BFS visits nodes in alphabetical order.",
                    "Because BFS always expands nodes in increasing order of distance from A, so a node is first reached via its shortest route.",
                    "Because BFS uses recursion to explore all paths simultaneously.",
                    "Because BFS ignores edges that create cycles.",
                ],
                "correct_answer": (
                    "Because BFS always expands nodes in increasing order of distance from A, "
                    "so a node is first reached via its shortest route."
                ),
                "explanation": (
                    "The queue's FIFO order guarantees BFS finishes all distance-1 nodes before "
                    "any distance-2 node, so the first time a node is reached, it's via the "
                    "shortest possible route."
                ),
                "hint": "Reconsider what 'first discovered' means when a queue is used.",
            },
            {
                "id": "bfs_q3",
                "difficulty": "medium",
                "question": (
                    "A graph has edge weights that are NOT all equal. Why can plain BFS no "
                    "longer guarantee the shortest path, and what does Dijkstra change to fix this?"
                ),
                "options": [
                    "BFS still works fine; Dijkstra is unrelated to BFS.",
                    "BFS assumes every edge costs the same (1 step); Dijkstra replaces the plain queue with a priority queue so it always expands the node with the smallest known total distance.",
                    "BFS fails because it uses recursion, and Dijkstra removes recursion entirely.",
                    "Dijkstra just runs BFS twice to double-check the path.",
                ],
                "correct_answer": (
                    "BFS assumes every edge costs the same (1 step); Dijkstra replaces the plain "
                    "queue with a priority queue so it always expands the node with the smallest "
                    "known total distance."
                ),
                "explanation": (
                    "BFS's shortest-path guarantee relies on every edge having equal weight. "
                    "Dijkstra keeps BFS's core idea (always expand the closest known node) but "
                    "swaps the queue for a priority queue so it works when edges have different weights."
                ),
                "hint": "Ask yourself what 'closest node' means once edges no longer all cost the same.",
            },
        ],
        "estimated_minutes": 6,
    }


def _dfs_fallback() -> Dict[str, Any]:
    return {
        "explanation": (
            "DFS (Depth-First Search) explores a graph by going as deep as possible along one "
            "path before backtracking, using a STACK (explicit, or implicitly via recursion's "
            "call stack). Unlike BFS, DFS gives no guarantee about visiting nodes in order of "
            "distance from the source — it just finds *a* path, diving deep first. DFS is the "
            "right tool for tasks like detecting cycles, finding connected components, or "
            "topological sorting, but it is NOT the right tool when you specifically need the "
            "shortest path in terms of number of edges — that's BFS's job."
        ),
        "analogy": (
            "Imagine exploring a maze by always turning down the first unexplored corridor and "
            "committing to it fully, only backtracking when you hit a dead end. You might "
            "stumble onto the exit quickly, or you might take a very long, winding route even "
            "though a shorter one existed — DFS makes no promises about finding the shortest way."
        ),
        "example": (
            "Graph: A-B, A-C, B-D, C-D. DFS from A (using a stack):\n"
            "1. Visit A. Push B, C.\n"
            "2. Pop C (LIFO — last pushed, first popped). Visit C. Push D.\n"
            "3. Pop D. Visit D.\n"
            "4. Pop B. Visit B (already partially explored via D, depending on implementation).\n"
            "Notice the order depends on which neighbor is pushed/popped last — very different "
            "from BFS's strict distance ordering."
        ),
        "key_points": [
            "DFS uses a stack (explicit) or recursion (implicit call stack).",
            "DFS dives deep before exploring siblings — the opposite of BFS's level-by-level order.",
            "DFS gives no shortest-path guarantee.",
            "DFS is well suited to cycle detection, topological sort, and connected components.",
            "Use BFS, not DFS, when you specifically need the fewest-edges path.",
        ],
        "practice_questions": [
            {
                "id": "dfs_q1",
                "difficulty": "easy",
                "question": "Which data structure underlies DFS, whether used explicitly or via recursion?",
                "options": ["Queue", "Stack", "Priority Queue", "Linked List"],
                "correct_answer": "Stack",
                "explanation": "DFS relies on LIFO ordering — the most recently discovered node is explored next.",
                "hint": "Think about what recursive function calls use internally.",
            },
            {
                "id": "dfs_q2",
                "difficulty": "medium",
                "question": "Which task is DFS naturally best suited for?",
                "options": [
                    "Finding the shortest path by edge count in an unweighted graph.",
                    "Detecting whether a graph contains a cycle.",
                    "Finding the minimum spanning tree.",
                    "Sorting an array of numbers.",
                ],
                "correct_answer": "Detecting whether a graph contains a cycle.",
                "explanation": "DFS's depth-first exploration naturally reveals back-edges, which indicate cycles.",
                "hint": "Which of these tasks doesn't depend on finding the fewest edges?",
            },
            {
                "id": "dfs_q3",
                "difficulty": "medium",
                "question": "Why might DFS return a longer path between two nodes than BFS would?",
                "options": [
                    "DFS always visits nodes in alphabetical order.",
                    "DFS commits to exploring one branch fully before backtracking, so it may reach the target via a long detour instead of the shortest route.",
                    "DFS refuses to visit any node more than once, unlike BFS.",
                    "DFS and BFS always return identical paths.",
                ],
                "correct_answer": (
                    "DFS commits to exploring one branch fully before backtracking, so it may "
                    "reach the target via a long detour instead of the shortest route."
                ),
                "explanation": "DFS has no mechanism that prioritizes closer nodes, unlike BFS's queue-based ordering.",
                "hint": "Think about what BFS guarantees that DFS does not.",
            },
        ],
        "estimated_minutes": 5,
    }


def _dijkstra_fallback() -> Dict[str, Any]:
    return {
        "explanation": (
            "Dijkstra's algorithm finds the shortest path from a source node in a weighted "
            "graph with non-negative edge weights. It is best understood as BFS generalized: "
            "BFS uses a plain queue and works when every edge costs the same (1 step); Dijkstra "
            "replaces that plain queue with a PRIORITY QUEUE (min-heap) so it can always expand "
            "the unvisited node with the smallest known total distance so far, even when edges "
            "have different weights. If you don't clearly understand why BFS's queue guarantees "
            "shortest paths in unweighted graphs, Dijkstra will feel arbitrary — it's really the "
            "same core idea with one key structure swapped."
        ),
        "analogy": (
            "BFS is like exploring ripples in a pond where every ripple takes the same time to "
            "travel one ring outward. Dijkstra is like exploring a landscape of hills and "
            "valleys, where 'distance traveled' depends on effort, not just number of steps — so "
            "instead of expanding in strict ring order, you always go to whichever unexplored "
            "spot currently has the least total effort to reach."
        ),
        "example": (
            "Weighted graph: A-B (weight 4), A-C (weight 1), C-B (weight 1). Dijkstra from A:\n"
            "1. dist = {A:0, B:inf, C:inf}. Priority queue: [(0,A)].\n"
            "2. Pop A (dist 0). Update B to 4, C to 1. Queue: [(1,C), (4,B)].\n"
            "3. Pop C (dist 1, smallest). Update B via C: 1+1=2, which beats 4. Queue: [(2,B)].\n"
            "4. Pop B (dist 2). Final: A=0, C=1, B=2.\n"
            "Notice Dijkstra always expands the node with the smallest *known distance so far* — "
            "exactly the BFS idea, but weight-aware."
        ),
        "key_points": [
            "Dijkstra = BFS's core idea + a priority queue instead of a plain queue.",
            "It greedily expands the unvisited node with the smallest known distance so far.",
            "Requires non-negative edge weights to guarantee correctness.",
            "When all edge weights equal 1, Dijkstra behaves identically to BFS.",
            "Misunderstanding BFS's queue-based ordering is a common root cause of struggling with Dijkstra.",
        ],
        "practice_questions": [
            {
                "id": "dij_q1",
                "difficulty": "easy",
                "question": "What data structure does Dijkstra use in place of BFS's plain queue?",
                "options": ["Stack", "Priority Queue (min-heap)", "Hash Set", "Doubly Linked List"],
                "correct_answer": "Priority Queue (min-heap)",
                "explanation": "A priority queue lets Dijkstra always expand the node with the smallest known distance, which a plain FIFO queue can't do once edge weights differ.",
                "hint": "Think about what structure lets you always retrieve the 'smallest' item efficiently.",
            },
            {
                "id": "dij_q2",
                "difficulty": "medium",
                "question": "Under what condition does Dijkstra behave exactly like BFS?",
                "options": [
                    "When the graph has no edges.",
                    "When every edge has the same weight (e.g. all weight 1).",
                    "When the graph is a tree.",
                    "Never — they are unrelated algorithms.",
                ],
                "correct_answer": "When every edge has the same weight (e.g. all weight 1).",
                "explanation": "If all edges cost 1, 'smallest known distance so far' becomes equivalent to 'fewest edges so far', which is exactly what BFS's FIFO queue already guarantees.",
                "hint": "Think about what makes BFS's shortest-path guarantee work in the first place.",
            },
            {
                "id": "dij_q3",
                "difficulty": "medium",
                "question": "Why does Dijkstra fail to guarantee correct results with negative edge weights?",
                "options": [
                    "It doesn't fail; Dijkstra handles negative weights fine.",
                    "Its greedy step assumes a node's distance is finalized once popped, but a later negative edge could still shrink that distance further, violating the algorithm's core assumption.",
                    "Negative weights make the priority queue crash.",
                    "Dijkstra only supports integer weights, not negative ones specifically.",
                ],
                "correct_answer": (
                    "Its greedy step assumes a node's distance is finalized once popped, but a "
                    "later negative edge could still shrink that distance further, violating the "
                    "algorithm's core assumption."
                ),
                "explanation": "Dijkstra's correctness relies on distances only increasing as you explore further, which negative weights can violate.",
                "hint": "Think about what 'greedy and never revisited' assumes about how distances change.",
            },
        ],
        "estimated_minutes": 7,
    }


def _generic_fallback(concept: str, concept_context: Dict[str, Any]) -> Dict[str, Any]:
    """A safety-net template for any concept not covered by a hand-authored fallback."""
    info = concept_context.get(concept, {})
    description = info.get("description", f"{concept} is a core data structures & algorithms concept.")
    key_ideas = info.get("key_ideas") or [f"Understand the core definition of {concept}.", "Practice applying it to a small example."]
    examples = info.get("examples") or [f"(No stored example available for {concept} yet.)"]
    misconceptions = info.get("common_misconceptions") or []

    filler_options = ["An unrelated sorting algorithm", "A type of database index", "A networking protocol", "A memory allocation strategy"]
    q2_options = list(dict.fromkeys(key_ideas + filler_options))[:4]
    while len(q2_options) < 4:
        q2_options.append("None of the above")

    return {
        "explanation": description,
        "analogy": f"Think of {concept} in terms of a simple everyday process that mirrors its core mechanism.",
        "example": examples[0] if examples else f"Consider a small worked example of {concept}.",
        "key_points": (key_ideas + misconceptions)[:5] or [description],
        "practice_questions": [
            {
                "id": "generic_q1",
                "difficulty": "easy",
                "question": f"What best describes {concept}?",
                "options": [description[:60] + "...", "An unrelated sorting algorithm", "A type of database index", "A networking protocol"],
                "correct_answer": description[:60] + "...",
                "explanation": f"This matches the core definition of {concept}.",
                "hint": f"Recall the core definition of {concept}.",
            },
            {
                "id": "generic_q2",
                "difficulty": "medium",
                "question": f"Which of these is a key idea behind {concept}?",
                "options": q2_options,
                "correct_answer": key_ideas[0],
                "explanation": "This reflects one of the foundational ideas behind the concept.",
                "hint": "Think about what makes this concept distinct from related ones.",
            },
            {
                "id": "generic_q3",
                "difficulty": "medium",
                "question": f"How does {concept} connect to the next step in your repair path?",
                "options": ["It is unrelated", "It builds a foundation the next concept depends on", "It replaces the need to learn further", "It only matters for interviews"],
                "correct_answer": "It builds a foundation the next concept depends on",
                "explanation": "Each step in the repair path is a prerequisite for the next.",
                "hint": "Consider why the repair path is ordered the way it is.",
            },
        ],
        "estimated_minutes": 5,
    }
