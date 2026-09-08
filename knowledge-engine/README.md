# Knowledge Engine — Member 1

Diagnostic engine: concept graph, question bank, mastery scoring, and
root-gap (debt) detection.

## Run it

cd knowledge-engine
venv\Scripts\activate
uvicorn main:app --reload --port 8001

Docs: http://127.0.0.1:8001/docs

## POST /diagnose

**Request:**
```json
{
  "student_id": "demo_student",
  "student_level": "beginner",
  "target_concept": "Dijkstra",
  "answers": [
    {"question_id": "q_bfs_01", "concept": "BFS", "selected_answer": "Stack"}
  ]
}
```

**Response** — shaped to be passed directly into `ai-engine`'s `POST /learn`:
```json
{
  "student_id": "demo_student",
  "concept": "Dijkstra",
  "student_level": "beginner",
  "root_gap": "BFS",
  "root_misconception": "...",
  "weak_concepts": ["BFS"],
  "repair_path": ["BFS", "DFS", "Graph Traversal", "Shortest Paths", "Dijkstra"],
  "mastery_by_concept": {"BFS": 0.0, ...}
}
```

## How root_gap is found
Walks backward through `data/concepts.json`'s prerequisite chain from
`target_concept`, and returns the earliest concept in that chain with
mastery below 60%. If nothing upstream is weak, `root_gap` = `target_concept`.