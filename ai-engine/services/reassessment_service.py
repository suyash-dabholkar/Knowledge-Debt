"""
Handles POST /reassess: scores a micro-assessment and produces an updated,
explainable mastery estimate.

The mastery formula is intentionally simple and transparent (see
README.md's "Mastery formula" section) — this is a hackathon prototype, and
we explicitly avoid pretending 3 questions "prove" mastery.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set

from schemas import (
    ReassessBatchRequest,
    ReassessBatchResponse,
    ReassessRequest,
    ReassessResponse,
    ReassessQuestionResult,
)

# Configurable thresholds (env-overridable, kept in one place per spec section 12).
MASTERED_THRESHOLD = float(os.getenv("MASTERY_THRESHOLD_MASTERED", "80"))
IMPROVING_THRESHOLD = float(os.getenv("MASTERY_THRESHOLD_IMPROVING", "60"))

# Weight given to the new quiz score vs. the student's prior mastery estimate.
# A higher weight means recent performance moves the needle faster.
NEW_SCORE_WEIGHT = float(os.getenv("MASTERY_NEW_SCORE_WEIGHT", "0.7"))
PREVIOUS_MASTERY_WEIGHT = 1.0 - NEW_SCORE_WEIGHT

# Minimum improvement a "debt reduced" verdict requires.
DEBT_REDUCED_MIN_IMPROVEMENT = float(os.getenv("DEBT_REDUCED_MIN_IMPROVEMENT", "10"))


def _score_questions(questions: List[ReassessQuestionResult]) -> float:
    """Percentage of questions answered correctly, 0-100."""
    if not questions:
        return 0.0
    correct = sum(
        1 for q in questions if _normalize(q.answer) == _normalize(q.correct_answer)
    )
    return round((correct / len(questions)) * 100, 2)


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _mastery_status(mastery: float) -> str:
    if mastery >= MASTERED_THRESHOLD:
        return "mastered"
    if mastery >= IMPROVING_THRESHOLD:
        return "improving"
    return "still_weak"


def _recommendation(status: str, concept: str, next_concept: str | None) -> str:
    if status == "mastered":
        if next_concept:
            return f"Continue to {next_concept}."
        return f"{concept} is mastered — no further repair needed for this concept."
    if status == "improving":
        return f"Do one more short practice round on {concept} before moving on."
    return f"Repeat the {concept} lesson with a simplified explanation before reattempting."


def reassess(request: ReassessRequest, next_concept: str | None = None) -> ReassessResponse:
    """
    Computes a new mastery estimate as a weighted combination of the
    student's previous mastery and their score on this micro-assessment.

    new_mastery = (PREVIOUS_MASTERY_WEIGHT * previous_mastery)
                + (NEW_SCORE_WEIGHT * score)

    This is a deliberately transparent formula: recent performance is
    weighted more heavily (demonstrating whether the repair worked) while
    still respecting the student's prior trajectory rather than discarding
    it after just 3 questions.
    """
    score = _score_questions(request.questions)

    new_mastery = round(
        (PREVIOUS_MASTERY_WEIGHT * request.previous_mastery) + (NEW_SCORE_WEIGHT * score),
        2,
    )
    new_mastery = min(100.0, max(0.0, new_mastery))

    improvement = round(new_mastery - request.previous_mastery, 2)
    status = _mastery_status(new_mastery)
    debt_reduced = improvement >= DEBT_REDUCED_MIN_IMPROVEMENT or status == "mastered"

    recommendation = _recommendation(status, request.concept, next_concept)

    return ReassessResponse(
        student_id=request.student_id,
        concept=request.concept,
        previous_mastery=request.previous_mastery,
        new_mastery=new_mastery,
        improvement=improvement,
        score=score,
        mastery_status=status,
        debt_reduced=debt_reduced,
        recommendation=recommendation,
    )


def _guess_next_concept_in_kb(concept: str, kb: Dict[str, Any]) -> Optional[str]:
    """Finds a concept in the KB whose prerequisites include `concept`."""
    for name, info in kb.items():
        if concept in info.get("prerequisites", []):
            return name
    return None


def reassess_batch(request: ReassessBatchRequest) -> ReassessBatchResponse:
    """
    Reassesses several concepts in one call and infers which downstream
    concepts (per the local prerequisite graph) likely had debt reduced as a
    side effect, even though they were not directly reassessed.

    This is what makes the "we repaired BFS, and that's why Dijkstra improved
    too" story visible in a single response, matching the core product
    principle: repairing a prerequisite gap lifts everything built on it.
    """
    # Local import to avoid a circular import at module load time
    # (learning_service does not import reassessment_service).
    from services import learning_service

    kb = learning_service._load_concept_kb()

    results: List[ReassessResponse] = []
    reduced_concepts: Set[str] = set()
    directly_assessed: Set[str] = set()

    for assessment in request.assessments:
        directly_assessed.add(assessment.concept)
        next_concept = _guess_next_concept_in_kb(assessment.concept, kb)
        result = reassess(assessment, next_concept=next_concept)
        results.append(result)
        if result.debt_reduced:
            reduced_concepts.add(assessment.concept)

    # Walk the KB's prerequisite graph to find concepts that depend
    # (directly or transitively) on a concept whose debt was reduced in this
    # batch, and that weren't already reassessed directly.
    downstream: Set[str] = set()
    changed = True
    frontier = set(reduced_concepts)
    while changed:
        changed = False
        for name, info in kb.items():
            if name in downstream or name in directly_assessed:
                continue
            prereqs = set(info.get("prerequisites", []))
            if prereqs & (frontier | downstream):
                downstream.add(name)
                changed = True

    downstream_list = sorted(downstream)

    if reduced_concepts:
        summary = (
            f"Debt reduced for {', '.join(sorted(reduced_concepts))}. "
            + (
                f"This likely also improves {', '.join(downstream_list)}, since they build on it "
                "in the local prerequisite graph (inferred, not separately measured)."
                if downstream_list
                else "No downstream concepts in the knowledge base currently depend on these."
            )
        )
    else:
        summary = "No concept in this batch reached the debt-reduced threshold yet."

    return ReassessBatchResponse(
        results=results,
        downstream_concepts_likely_improved=downstream_list,
        summary=summary,
    )
