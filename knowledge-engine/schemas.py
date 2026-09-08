from __future__ import annotations
from typing import List
from pydantic import BaseModel, Field


class QuizAnswer(BaseModel):
    question_id: str
    concept: str
    selected_answer: str


class QuizSubmission(BaseModel):
    student_id: str = Field(..., min_length=1)
    student_level: str = Field(default="beginner")
    target_concept: str = Field(..., min_length=1)
    answers: List[QuizAnswer]


class DiagnosisResponse(BaseModel):
    student_id: str
    concept: str
    student_level: str
    root_gap: str
    root_misconception: str
    weak_concepts: List[str]
    repair_path: List[str]
    previous_attempts: List[dict] = Field(default_factory=list)
    mastery_by_concept: dict = Field(default_factory=dict)