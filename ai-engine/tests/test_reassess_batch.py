import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


ALL_CORRECT_BFS = {
    "student_id": "student_020",
    "concept": "BFS",
    "previous_mastery": 37,
    "questions": [
        {"question_id": "bfs_01", "answer": "Queue", "correct_answer": "Queue"},
        {"question_id": "bfs_02", "answer": "Level by level", "correct_answer": "Level by level"},
        {
            "question_id": "bfs_03",
            "answer": "It explores nodes in increasing distance from the source",
            "correct_answer": "It explores nodes in increasing distance from the source",
        },
    ],
}

ALL_INCORRECT_DFS = {
    "student_id": "student_020",
    "concept": "DFS",
    "previous_mastery": 40,
    "questions": [
        {"question_id": "dfs_01", "answer": "Queue", "correct_answer": "Stack"},
    ],
}


def test_reassess_batch_flags_downstream_concepts_when_debt_reduced():
    response = client.post("/reassess/batch", json={"assessments": [ALL_CORRECT_BFS]})
    assert response.status_code == 200
    data = response.json()

    assert len(data["results"]) == 1
    assert data["results"][0]["concept"] == "BFS"
    assert data["results"][0]["debt_reduced"] is True

    # BFS is a prerequisite (directly or transitively) of DFS's sibling
    # concepts in the repair chain per data/concepts.json.
    assert "Dijkstra" in data["downstream_concepts_likely_improved"]
    assert "BFS" in data["summary"]


def test_reassess_batch_multiple_concepts_mixed_results():
    response = client.post(
        "/reassess/batch", json={"assessments": [ALL_CORRECT_BFS, ALL_INCORRECT_DFS]}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 2
    concepts = {r["concept"] for r in data["results"]}
    assert concepts == {"BFS", "DFS"}
    # DFS was directly assessed, so it should never appear in the downstream-inferred list.
    assert "DFS" not in data["downstream_concepts_likely_improved"]


def test_reassess_batch_empty_assessments_rejected():
    response = client.post("/reassess/batch", json={"assessments": []})
    assert response.status_code == 422


def test_reassess_batch_no_debt_reduced_has_empty_downstream_and_says_so():
    no_improvement_payload = {
        "student_id": "student_021",
        "concept": "BFS",
        "previous_mastery": 80,
        "questions": [
            {"question_id": "bfs_01", "answer": "Stack", "correct_answer": "Queue"},
        ],
    }
    response = client.post("/reassess/batch", json={"assessments": [no_improvement_payload]})
    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["debt_reduced"] is False
    assert data["downstream_concepts_likely_improved"] == []
    assert "No concept" in data["summary"]
