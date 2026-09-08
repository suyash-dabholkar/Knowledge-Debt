import json
import os

from fastapi import FastAPI, HTTPException

from schemas import DiagnosisResponse, QuizSubmission
from services import debt_detection_service, mastery_service

app = FastAPI(title="Knowledge Debt — Knowledge Graph & Diagnostic Engine")

_CONCEPTS_PATH = os.path.join(os.path.dirname(__file__), "data", "concepts.json")
_QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), "data", "questions.json")


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/")
def root():
    return {"status": "ok", "service": "knowledge-debt-diagnostic-engine"}


@app.post("/diagnose", response_model=DiagnosisResponse)
def diagnose(submission: QuizSubmission):
    kb = _load_json(_CONCEPTS_PATH)
    questions_by_id = {q["id"]: q for q in _load_json(_QUESTIONS_PATH)}

    if submission.target_concept not in kb:
        raise HTTPException(status_code=400, detail=f"Unknown target_concept '{submission.target_concept}'")

    mastery = mastery_service.calculate_mastery(submission.answers, questions_by_id)
    result = debt_detection_service.find_root_gap(submission.target_concept, mastery, kb)
    root_misconception = debt_detection_service.root_misconception_for(result["root_gap"], kb)

    return DiagnosisResponse(
        student_id=submission.student_id,
        concept=submission.target_concept,
        student_level=submission.student_level,
        root_gap=result["root_gap"],
        root_misconception=root_misconception,
        weak_concepts=result["weak_concepts"],
        repair_path=result["repair_path"],
        mastery_by_concept=mastery,
    )