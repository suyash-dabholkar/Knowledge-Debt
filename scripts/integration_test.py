import httpx

DIAGNOSE_URL = "http://127.0.0.1:8001/diagnose"
LEARN_URL = "http://127.0.0.1:8000/learn"

quiz_submission = {
    "student_id": "demo_student",
    "student_level": "beginner",
    "target_concept": "Dijkstra",
    "answers": [
        {"question_id": "q_arrays_01", "concept": "Arrays", "selected_answer": "O(1)"},
        {"question_id": "q_pointers_01", "concept": "Pointers", "selected_answer": "The memory address of another value"},
        {"question_id": "q_linkedlists_01", "concept": "Linked Lists", "selected_answer": "O(1)"},
        {"question_id": "q_trees_01", "concept": "Trees", "selected_answer": "It is connected and acyclic"},
        {"question_id": "q_graphs_01", "concept": "Graphs", "selected_answer": "Graphs generalize trees by allowing cycles and multiple paths"},
        {"question_id": "q_bfs_01", "concept": "BFS", "selected_answer": "Stack"},
        {"question_id": "q_dfs_01", "concept": "DFS", "selected_answer": "Always finding the shortest path"},
        {"question_id": "q_graphtraversal_01", "concept": "Graph Traversal", "selected_answer": "BFS"},
        {"question_id": "q_shortestpaths_01", "concept": "Shortest Paths", "selected_answer": "BFS assumes all edges cost the same, so it can't account for differing weights"},
        {"question_id": "q_dijkstra_01", "concept": "Dijkstra", "selected_answer": "Priority queue (min-heap)"}
    ]
}

print("Calling /diagnose ...")
diagnosis = httpx.post(DIAGNOSE_URL, json=quiz_submission, timeout=30).json()
print("root_gap:", diagnosis["root_gap"])
print("repair_path:", diagnosis["repair_path"])

print("\nCalling /learn with that diagnosis ...")
lesson = httpx.post(LEARN_URL, json=diagnosis, timeout=60).json()
print("source:", lesson["source"])
print("explanation:", lesson["explanation"][:200], "...")
print("practice questions:", len(lesson["practice_questions"]))