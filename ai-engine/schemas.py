"""
Pydantic models for the Knowledge Debt AI Learning & Debt Repayment Engine.

These models define the API contract with Member 1 (diagnostic engine) and
Member 3 (frontend), and the internal shape of AI-generated content.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Input contract (received from Member 1's diagnostic engine)
# ---------------------------------------------------------------------------

class PreviousAttempt(BaseModel):
    """A single prior attempt/interaction, if Member 1 tracks history."""
    concept: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None
    correct: Optional[bool] = None


class DiagnosisRequest(BaseModel):
    """
    The diagnostic payload produced by Member 1.

    This module NEVER re-derives root_gap or root_misconception. It only
    consumes them.
    """

    student_id: str = Field(..., min_length=1)
    concept: str = Field(..., min_length=1)
    student_level: str = Field(default="beginner")
    root_gap: str = Field(..., min_length=1)
    root_misconception: str = Field(..., min_length=1)
    weak_concepts: List[str] = Field(default_factory=list)
    repair_path: List[str] = Field(..., min_length=1)
    previous_attempts: List[PreviousAttempt] = Field(default_factory=list)

    @field_validator("student_level")
    @classmethod
    def normalize_level(cls, v: str) -> str:
        allowed = {"beginner", "intermediate", "advanced"}
        v_norm = (v or "beginner").strip().lower()
        return v_norm if v_norm in allowed else "beginner"

    @field_validator("repair_path")
    @classmethod
    def repair_path_not_empty(cls, v: List[str]) -> List[str]:
        if not v or len(v) == 0:
            raise ValueError("repair_path must contain at least one concept")
        return v


# ---------------------------------------------------------------------------
# /learn response
# ---------------------------------------------------------------------------

class PracticeQuestion(BaseModel):
    id: str
    difficulty: str  # "easy" | "medium" | "hard"
    question: str
    options: List[str]
    correct_answer: str
    explanation: str
    hint: str


class LearningResponse(BaseModel):
    student_id: str
    concept: str
    root_gap: str
    diagnosis: str
    explanation: str
    analogy: str
    example: str
    key_points: List[str]
    practice_questions: List[PracticeQuestion]
    next_step: str
    estimated_minutes: int
    source: str = Field(
        default="llm",
        description="Indicates whether content came from the LLM or the deterministic fallback ('llm' | 'fallback').",
    )
    attempt_number: int = Field(
        default=1,
        description="How many times /learn has been called for this student+concept pair in this server session.",
    )
    reinforced_misconceptions: List[str] = Field(
        default_factory=list,
        description=(
            "Misconceptions surfaced by earlier /practice calls for this student+concept pair "
            "that were folded into this lesson's teaching, if any."
        ),
    )


# ---------------------------------------------------------------------------
# /reassess
# ---------------------------------------------------------------------------

class ReassessQuestionResult(BaseModel):
    question_id: str
    answer: str
    correct_answer: str


class ReassessRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    concept: str = Field(..., min_length=1)
    previous_mastery: float = Field(..., ge=0, le=100)
    questions: List[ReassessQuestionResult] = Field(..., min_length=1)

    @field_validator("questions")
    @classmethod
    def questions_not_empty(cls, v):
        if not v:
            raise ValueError("questions must contain at least one result")
        return v


class ReassessResponse(BaseModel):
    student_id: str
    concept: str
    previous_mastery: float
    new_mastery: float
    improvement: float
    score: float
    mastery_status: str  # "mastered" | "improving" | "still_weak"
    debt_reduced: bool
    recommendation: str
    note: str = Field(
        default="Mastery is an estimated prototype metric, not a scientifically validated measurement.",
    )


class ReassessBatchRequest(BaseModel):
    """
    Reassess several concepts at once — e.g. after a full repair-path session,
    or to show how repairing one concept (BFS) cascades into others that
    depend on it (DFS, Graph Traversal, Shortest Paths, Dijkstra).
    """
    assessments: List[ReassessRequest] = Field(..., min_length=1)


class ReassessBatchResponse(BaseModel):
    results: List[ReassessResponse]
    downstream_concepts_likely_improved: List[str] = Field(
        default_factory=list,
        description=(
            "Concepts not directly reassessed here, whose prerequisites include a concept "
            "that had debt reduced in this batch. This is an inference from the local "
            "knowledge base's prerequisite graph, not a measured result."
        ),
    )
    summary: str


# ---------------------------------------------------------------------------
# /practice (optional, P1)
# ---------------------------------------------------------------------------

class PracticeAnswerRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    concept: str = Field(..., min_length=1)
    student_level: str = Field(default="beginner")
    question_id: str
    question_text: str
    student_answer: str
    correct_answer: str
    is_correct: bool


class PracticeAnswerResponse(BaseModel):
    is_correct: bool
    likely_misconception: Optional[str] = None
    feedback: str
    follow_up_question: Optional[PracticeQuestion] = None
    difficulty_direction: str  # "increase" | "decrease" | "hold"


# ---------------------------------------------------------------------------
# /hint (optional, P1)
# ---------------------------------------------------------------------------

class HintRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    concept: str = Field(..., min_length=1)
    question_text: str
    student_level: str = Field(default="beginner")


class HintResponse(BaseModel):
    hint: str


# ---------------------------------------------------------------------------
# Generic error shape
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
