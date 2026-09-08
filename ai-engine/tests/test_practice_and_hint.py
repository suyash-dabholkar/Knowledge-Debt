import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from main import app
from services import student_state

client = TestClient(app)


def setup_function(_):
    # Each test gets a clean in-memory student_state, since it's process-global.
    student_state.reset_all()


def test_practice_correct_answer_increases_difficulty():
    payload = {
        "student_id": "student_010",
        "concept": "BFS",
        "student_level": "beginner",
        "question_id": "bfs_q1",
        "question_text": "Which data structure does BFS use?",
        "student_answer": "Queue",
        "correct_answer": "Queue",
        "is_correct": True,
    }
    response = client.post("/practice", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_correct"] is True
    assert data["difficulty_direction"] == "increase"
    assert data["likely_misconception"] is None
    assert data["follow_up_question"] is None


def test_practice_incorrect_answer_identifies_bfs_dfs_misconception():
    payload = {
        "student_id": "student_011",
        "concept": "BFS",
        "student_level": "beginner",
        "question_id": "bfs_q1",
        "question_text": "Which data structure does BFS use?",
        "student_answer": "BFS uses a stack",
        "correct_answer": "Queue",
        "is_correct": False,
    }
    response = client.post("/practice", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_correct"] is False
    assert data["difficulty_direction"] == "decrease"
    assert data["likely_misconception"] is not None
    assert "BFS" in data["likely_misconception"] or "queue" in data["likely_misconception"].lower()
    assert data["follow_up_question"] is not None
    assert len(data["follow_up_question"]["options"]) == 4
    assert data["follow_up_question"]["correct_answer"] in data["follow_up_question"]["options"]
    # Feedback should never be a bare "Incorrect, the answer is X."
    assert data["feedback"].lower() != f"incorrect. the answer is {data['follow_up_question']['correct_answer'].lower()}"


def test_practice_wrong_answer_is_recorded_in_student_state_and_reinforced_in_learn():
    practice_payload = {
        "student_id": "student_012",
        "concept": "BFS",
        "student_level": "beginner",
        "question_id": "bfs_q1",
        "question_text": "Which data structure does BFS use?",
        "student_answer": "BFS uses a stack",
        "correct_answer": "Queue",
        "is_correct": False,
    }
    practice_response = client.post("/practice", json=practice_payload)
    assert practice_response.status_code == 200

    # A subsequent /learn call for the same student+concept should reflect
    # that a misconception was already surfaced during practice.
    learn_payload = {
        "student_id": "student_012",
        "concept": "BFS",
        "student_level": "beginner",
        "root_gap": "BFS",
        "root_misconception": "Student confuses BFS and DFS and does not understand why BFS uses a queue.",
        "weak_concepts": ["BFS", "DFS"],
        "repair_path": ["BFS", "DFS", "Graph Traversal", "Shortest Paths", "Dijkstra"],
        "previous_attempts": [],
    }
    learn_response = client.post("/learn", json=learn_payload)
    assert learn_response.status_code == 200
    data = learn_response.json()
    assert len(data["reinforced_misconceptions"]) >= 1


def test_learn_attempt_number_increments_across_calls():
    payload = {
        "student_id": "student_013",
        "concept": "BFS",
        "student_level": "beginner",
        "root_gap": "BFS",
        "root_misconception": "Student confuses BFS and DFS and does not understand why BFS uses a queue.",
        "weak_concepts": ["BFS", "DFS"],
        "repair_path": ["BFS", "DFS", "Graph Traversal", "Shortest Paths", "Dijkstra"],
        "previous_attempts": [],
    }
    first = client.post("/learn", json=payload).json()
    second = client.post("/learn", json=payload).json()
    assert first["attempt_number"] == 1
    assert second["attempt_number"] == 2


def test_hint_works_without_llm_configured():
    payload = {
        "student_id": "student_014",
        "concept": "BFS",
        "question_text": "Which data structure does BFS use?",
        "student_level": "beginner",
    }
    response = client.post("/hint", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["hint"], str)
    assert len(data["hint"]) > 0


def test_concepts_debug_endpoint_returns_known_concept():
    response = client.get("/concepts/BFS")
    assert response.status_code == 200
    data = response.json()
    assert "BFS" in data
    assert "description" in data["BFS"]


def test_concepts_debug_endpoint_404s_for_unknown_concept():
    response = client.get("/concepts/NotARealConcept")
    assert response.status_code == 404
