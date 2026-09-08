"""
Knowledge Debt — AI Learning & Debt Repayment Engine (Member 2's module).

Run with:
    uvicorn main:app --reload

Docs at http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from schemas import (
    DiagnosisRequest,
    HintRequest,
    HintResponse,
    LearningResponse,
    PracticeAnswerRequest,
    PracticeAnswerResponse,
    PracticeQuestion,
    ReassessBatchRequest,
    ReassessBatchResponse,
    ReassessRequest,
    ReassessResponse,
)
from services import learning_service, misconception_service, reassessment_service, student_state
import llm as llm_module

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("knowledge_debt.main")

app = FastAPI(
    title="Knowledge Debt — AI Learning & Debt Repayment Engine",
    description=(
        "Member 2's module. Receives a diagnosis (root gap + misconception) from "
        "Member 1's diagnostic engine and turns it into a personalized repair lesson, "
        "adaptive practice, and reassessment."
    ),
    version="1.0.0",
)

# CORS enabled for local hackathon development (frontend on a different port).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "knowledge-debt-ai-learning-engine",
        "endpoints": ["/learn", "/reassess", "/reassess/batch", "/practice", "/hint", "/concepts/{name}"],
        "llm_configured": llm_module._llm_configured(),
    }


@app.get("/concepts/{name}")
def get_concept(name: str):
    """
    Debug/integration-testing endpoint exposing a single knowledge-base entry
    (description, prerequisites, common misconceptions, key ideas, examples).
    Useful for Member 1 and Member 3 to sanity-check what this module knows
    about a given concept without needing to open data/concepts.json directly.
    """
    context = learning_service.retrieve_context(name)
    if not context:
        raise HTTPException(status_code=404, detail=f"No knowledge base entry found for '{name}'")
    return context


@app.post("/learn", response_model=LearningResponse)
def learn(diagnosis: DiagnosisRequest):
    """
    Receives Member 1's diagnosis and generates a personalized repair lesson.
    This endpoint does NOT re-derive root_gap or root_misconception — it only
    consumes them.
    """
    try:
        return learning_service.generate_lesson(diagnosis)
    except Exception as exc:  # noqa: BLE001 - top-level safety net for a hackathon demo
        logger.exception("Unexpected error in /learn")
        raise HTTPException(status_code=500, detail=f"Failed to generate lesson: {exc}") from exc


@app.post("/reassess", response_model=ReassessResponse)
def reassess(request: ReassessRequest):
    """
    Scores a micro-assessment and returns an updated, explainable mastery estimate.
    """
    try:
        next_concept = _guess_next_concept(request.concept)
        return reassessment_service.reassess(request, next_concept=next_concept)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in /reassess")
        raise HTTPException(status_code=500, detail=f"Failed to reassess: {exc}") from exc


@app.post("/reassess/batch", response_model=ReassessBatchResponse)
def reassess_batch(request: ReassessBatchRequest):
    """
    Reassesses several concepts in one call and infers which downstream
    concepts (per the local prerequisite graph) likely had debt reduced as a
    side effect, even though they weren't directly reassessed. This is what
    makes the "we repaired BFS, not just Dijkstra" story visible in one response.
    """
    try:
        return reassessment_service.reassess_batch(request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in /reassess/batch")
        raise HTTPException(status_code=500, detail=f"Failed to reassess batch: {exc}") from exc


@app.post("/practice", response_model=PracticeAnswerResponse)
def practice(request: PracticeAnswerRequest):
    """
    Optional (P1): adaptive follow-up when a student answers a practice question.

    - Correct answer -> difficulty_direction = "increase", encouraging feedback.
    - Incorrect answer -> identifies a likely misconception, gives a hint, and a
      targeted follow-up question (never just "Incorrect, the answer is X").
    """
    try:
        if request.is_correct:
            return PracticeAnswerResponse(
                is_correct=True,
                likely_misconception=None,
                feedback=(
                    f"Correct! You're building a solid grasp of {request.concept}. "
                    "Moving to a slightly harder question."
                ),
                follow_up_question=None,
                difficulty_direction="increase",
            )

        analysis = misconception_service.analyze_wrong_answer(
            concept=request.concept,
            question_text=request.question_text,
            student_answer=request.student_answer,
            correct_answer=request.correct_answer,
        )
        follow_up_raw = analysis.get("follow_up_question")
        follow_up = PracticeQuestion(**follow_up_raw) if follow_up_raw else None
        misconception_text = analysis.get("likely_misconception", "this points to a gap worth revisiting").rstrip(".")

        # Feed this back into student_state so a subsequent /learn call for the
        # same student+concept can explicitly reinforce teaching around it.
        if analysis.get("likely_misconception"):
            student_state.record_misconception(
                request.student_id, request.concept, analysis["likely_misconception"]
            )

        return PracticeAnswerResponse(
            is_correct=False,
            likely_misconception=analysis.get("likely_misconception"),
            feedback=(
                f"Not quite — {misconception_text}. "
                f"Hint: {analysis.get('hint', '')}"
            ),
            follow_up_question=follow_up,
            difficulty_direction="decrease",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in /practice")
        raise HTTPException(status_code=500, detail=f"Failed to process practice answer: {exc}") from exc


@app.post("/hint", response_model=HintResponse)
def hint(request: HintRequest):
    """Optional (P1): standalone hint generation for a given question."""
    try:
        generated = llm_module.generate_hint(
            concept=request.concept,
            question_text=request.question_text,
            student_level=request.student_level,
        )
        if generated:
            return HintResponse(hint=generated)
        return HintResponse(
            hint=f"Revisit the core definition of {request.concept} and compare it to what the question is really asking."
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in /hint")
        raise HTTPException(status_code=500, detail=f"Failed to generate hint: {exc}") from exc


def _guess_next_concept(concept: str) -> str | None:
    """
    Best-effort lookup of "what comes after this concept" using the local
    knowledge base's prerequisite graph, for the /reassess recommendation.
    This is a convenience only — Member 1 owns the authoritative repair path.
    """
    kb = learning_service._load_concept_kb()
    # Find any concept whose prerequisites include this one; return the first match
    # in the KB's natural (dependency) order.
    for name, info in kb.items():
        if concept in info.get("prerequisites", []):
            return name
    return None


@app.exception_handler(RequestValidationError)
def handle_request_validation_error(request: Request, exc: RequestValidationError):
    """
    Returns a clean, frontend-friendly 422 for malformed requests (e.g. missing
    root_misconception, empty repair_path) instead of FastAPI's default nested
    error format, per the error-handling requirements in the spec.
    """
    first_error = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first_error.get("loc", [])[1:])  # skip "body"
    message = first_error.get("msg", "Invalid request")
    detail = f"{field}: {message}" if field else message
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "detail": detail},
    )
