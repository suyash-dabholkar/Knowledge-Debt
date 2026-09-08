import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


BFS_DIAGNOSIS = {
    "student_id": "student_001",
    "concept": "BFS",
    "student_level": "beginner",
    "root_gap": "BFS",
    "root_misconception": "Student confuses BFS and DFS and does not understand why BFS uses a queue.",
    "weak_concepts": ["BFS", "DFS", "Graph Traversal"],
    "repair_path": ["BFS", "DFS", "Graph Traversal", "Shortest Paths", "Dijkstra"],
    "previous_attempts": [],
}

DIJKSTRA_DIAGNOSIS = {
    "student_id": "student_002",
    "concept": "Dijkstra",
    "student_level": "beginner",
    "root_gap": "BFS",
    "root_misconception": "Student confuses BFS and DFS and does not understand why BFS uses a queue.",
    "weak_concepts": ["BFS", "DFS", "Graphs"],
    "repair_path": ["BFS", "DFS", "Graph Traversal", "Shortest Paths", "Dijkstra"],
    "previous_attempts": [],
}


def test_root_ok():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_learn_bfs_example():
    response = client.post("/learn", json=BFS_DIAGNOSIS)
    assert response.status_code == 200
    data = response.json()

    assert data["student_id"] == "student_001"
    assert data["concept"] == "BFS"
    assert data["root_gap"] == "BFS"
    assert "queue" in data["explanation"].lower()
    assert len(data["practice_questions"]) == 3
    assert data["practice_questions"][0]["difficulty"] == "easy"
    for q in data["practice_questions"]:
        assert len(q["options"]) == 4
        assert q["correct_answer"] in q["options"]
    assert data["next_step"] == "DFS"
    assert data["estimated_minutes"] > 0
    # No LLM key configured in test environment -> deterministic fallback.
    assert data["source"] == "fallback"


def test_learn_dijkstra_example_teaches_root_gap_not_surface_concept():
    response = client.post("/learn", json=DIJKSTRA_DIAGNOSIS)
    assert response.status_code == 200
    data = response.json()

    assert data["concept"] == "Dijkstra"
    # The root gap is BFS, and the lesson must be generated around Dijkstra
    # while acknowledging the true root misconception (BFS/queue).
    assert data["root_gap"] == "BFS"
    assert "queue" in data["explanation"].lower() or "priority queue" in data["explanation"].lower()
    assert len(data["practice_questions"]) == 3


def test_learn_missing_root_misconception_is_rejected():
    bad_payload = dict(BFS_DIAGNOSIS)
    del bad_payload["root_misconception"]
    response = client.post("/learn", json=bad_payload)
    assert response.status_code == 422


def test_learn_empty_repair_path_is_rejected():
    bad_payload = dict(BFS_DIAGNOSIS)
    bad_payload["repair_path"] = []
    response = client.post("/learn", json=bad_payload)
    assert response.status_code == 422


def test_learn_invalid_concept_still_returns_content_via_generic_fallback():
    payload = dict(BFS_DIAGNOSIS)
    payload["concept"] = "SomeUnknownConcept"
    payload["repair_path"] = ["SomeUnknownConcept", "BFS"]
    response = client.post("/learn", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["concept"] == "SomeUnknownConcept"
    assert len(data["practice_questions"]) == 3


def test_learn_works_without_llm_api_key_env_unset(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    import llm as llm_module

    monkeypatch.setattr(llm_module, "LLM_API_KEY", "")
    response = client.post("/learn", json=BFS_DIAGNOSIS)
    assert response.status_code == 200
    assert response.json()["source"] == "fallback"
