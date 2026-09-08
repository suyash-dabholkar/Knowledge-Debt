"""
Orchestrates personalized lesson generation for POST /learn.

This service NEVER re-derives root_gap or root_misconception — those come
from Member 1's diagnostic engine and are treated as authoritative input.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict, List

import llm as llm_module
from schemas import DiagnosisRequest, LearningResponse, PracticeQuestion
from services import student_state

_CONCEPTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "concepts.json")


@lru_cache(maxsize=1)
def _load_concept_kb() -> Dict[str, Any]:
    with open(_CONCEPTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def retrieve_context(query: str) -> Dict[str, Any]:
    """
    Minimal RAG-style retrieval hook (optional feature, P2).

    For the hackathon MVP this simply looks up the concept in the local
    knowledge base. It's isolated behind this function so a real vector-store
    retriever can be swapped in later without touching calling code.
    """
    kb = _load_concept_kb()
    if query in kb:
        return {query: kb[query]}
    lowered = query.strip().lower()
    for key, value in kb.items():
        if key.lower() == lowered:
            return {key: value}
    return {}


def _build_relevant_context(concept: str, repair_path: List[str]) -> Dict[str, Any]:
    """Gathers KB context for the target concept plus its repair-path neighbors."""
    kb = _load_concept_kb()
    context: Dict[str, Any] = {}
    for name in [concept] + repair_path:
        match = retrieve_context(name)
        context.update(match)
    if not context:
        # Always give the LLM/fallback *something* grounded, even for unknown concepts.
        context = {concept: {"description": f"No stored knowledge base entry for {concept}."}}
    return context


def generate_lesson(diagnosis: DiagnosisRequest) -> LearningResponse:
    """
    Main entry point used by the /learn route. Turns Member 1's diagnosis into
    a fully personalized, structured lesson.
    """
    concept_context = _build_relevant_context(diagnosis.concept, diagnosis.repair_path)

    attempt_number = student_state.record_learn_attempt(diagnosis.student_id, diagnosis.concept)
    reinforced = student_state.get_recent_misconceptions(diagnosis.student_id, diagnosis.concept)

    raw = llm_module.generate_learning_content(
        student_id=diagnosis.student_id,
        concept=diagnosis.concept,
        student_level=diagnosis.student_level,
        root_gap=diagnosis.root_gap,
        root_misconception=diagnosis.root_misconception,
        weak_concepts=diagnosis.weak_concepts,
        repair_path=diagnosis.repair_path,
        concept_context=concept_context,
        reinforced_misconceptions=reinforced,
        attempt_number=attempt_number,
    )

    questions = [
        PracticeQuestion(**_normalize_question(q, idx))
        for idx, q in enumerate(raw.get("practice_questions", []), start=1)
    ]

    return LearningResponse(
        student_id=diagnosis.student_id,
        concept=diagnosis.concept,
        root_gap=diagnosis.root_gap,
        diagnosis=raw.get("diagnosis", diagnosis.root_misconception),
        explanation=raw.get("explanation", ""),
        analogy=raw.get("analogy", ""),
        example=raw.get("example", ""),
        key_points=raw.get("key_points", []),
        practice_questions=questions,
        next_step=raw.get("next_step", _default_next_step(diagnosis)),
        estimated_minutes=int(raw.get("estimated_minutes", 5)),
        source=raw.get("source", "llm"),
        attempt_number=attempt_number,
        reinforced_misconceptions=reinforced,
    )


def _default_next_step(diagnosis: DiagnosisRequest) -> str:
    path = diagnosis.repair_path
    try:
        idx = path.index(diagnosis.concept)
        if idx + 1 < len(path):
            return path[idx + 1]
    except ValueError:
        pass
    return path[0] if path else diagnosis.concept


def _normalize_question(q: Dict[str, Any], idx: int) -> Dict[str, Any]:
    """Fills in safe defaults if the LLM omits a field, so Pydantic validation never hard-fails."""
    options = q.get("options") or []
    while len(options) < 4:
        options.append(f"Option {len(options) + 1}")
    correct = q.get("correct_answer")
    if correct not in options:
        correct = options[0]
    return {
        "id": q.get("id") or f"q{idx}",
        "difficulty": q.get("difficulty") or ("easy" if idx == 1 else "medium"),
        "question": q.get("question") or "Question unavailable.",
        "options": options[:4],
        "correct_answer": correct,
        "explanation": q.get("explanation") or "",
        "hint": q.get("hint") or "Reconsider the core definition of this concept.",
    }
