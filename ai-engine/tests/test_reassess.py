import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _payload(previous_mastery, questions):
    return {
        "student_id": "student_001",
        "concept": "BFS",
        "previous_mastery": previous_mastery,
        "questions": questions,
    }


ALL_CORRECT_QUESTIONS = [
    {"question_id": "bfs_01", "answer": "Queue", "correct_answer": "Queue"},
    {"question_id": "bfs_02", "answer": "Level by level", "correct_answer": "Level by level"},
    {
        "question_id": "bfs_03",
        "answer": "It explores nodes in increasing distance from the source",
        "correct_answer": "It explores nodes in increasing distance from the source",
    },
]

ALL_INCORRECT_QUESTIONS = [
    {"question_id": "bfs_01", "answer": "Stack", "correct_answer": "Queue"},
    {"question_id": "bfs_02", "answer": "Depth first", "correct_answer": "Level by level"},
    {
        "question_id": "bfs_03",
        "answer": "It explores the deepest node first",
        "correct_answer": "It explores nodes in increasing distance from the source",
    },
]

MIXED_QUESTIONS = [
    {"question_id": "bfs_01", "answer": "Queue", "correct_answer": "Queue"},
    {"question_id": "bfs_02", "answer": "Depth first", "correct_answer": "Level by level"},
    {
        "question_id": "bfs_03",
        "answer": "It explores nodes in increasing distance from the source",
        "correct_answer": "It explores nodes in increasing distance from the source",
    },
]


def test_reassess_all_correct_reaches_mastered():
    response = client.post("/reassess", json=_payload(37, ALL_CORRECT_QUESTIONS))
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 100.0
    assert data["mastery_status"] == "mastered"
    assert data["debt_reduced"] is True
    assert data["new_mastery"] > data["previous_mastery"]
    assert data["improvement"] > 0


def test_reassess_mixed_answers_partial_improvement():
    response = client.post("/reassess", json=_payload(37, MIXED_QUESTIONS))
    assert response.status_code == 200
    data = response.json()
    assert 0 < data["score"] < 100
    assert data["mastery_status"] in {"still_weak", "improving", "mastered"}


def test_reassess_all_incorrect_stays_weak():
    response = client.post("/reassess", json=_payload(37, ALL_INCORRECT_QUESTIONS))
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 0.0
    assert data["mastery_status"] == "still_weak"
    assert data["debt_reduced"] is False


def test_reassess_invalid_request_missing_questions():
    bad_payload = _payload(37, [])
    response = client.post("/reassess", json=bad_payload)
    assert response.status_code == 422


def test_reassess_invalid_previous_mastery_out_of_range():
    bad_payload = _payload(150, ALL_CORRECT_QUESTIONS)
    response = client.post("/reassess", json=bad_payload)
    assert response.status_code == 422
