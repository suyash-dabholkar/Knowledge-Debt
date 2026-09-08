import httpx

DIAGNOSE_URL = "http://127.0.0.1:8001/diagnose"
LEARN_URL = "http://127.0.0.1:8000/learn"

quiz_submission = {
    "student_id": "demo_student",
    "student_level": "beginner",
    "target_concept": "Dijkstra",
    "answers": [
        {"question_id": "q_arrays_01", "concept": "Arrays", "selected_answer": "O(1)"},
        {"question_id": "q_arrays_02", "concept": "Arrays", "selected_answer": "O(n)"},
        {"question_id": "q_arrays_03", "concept": "Arrays", "selected_answer": "The number of elements currently stored"},

        {"question_id": "q_pointers_01", "concept": "Pointers", "selected_answer": "The memory address of another value"},
        {"question_id": "q_pointers_02", "concept": "Pointers", "selected_answer": "You retrieve the value stored at the address it points to"},
        {"question_id": "q_pointers_03", "concept": "Pointers", "selected_answer": "A pointer that points to nothing / no valid address"},

        {"question_id": "q_linkedlists_01", "concept": "Linked Lists", "selected_answer": "O(1)"},
        {"question_id": "q_linkedlists_02", "concept": "Linked Lists", "selected_answer": "O(n)"},
        {"question_id": "q_linkedlists_03", "concept": "Linked Lists", "selected_answer": "Contiguous memory allocation"},

        {"question_id": "q_recursion_01", "concept": "Recursion", "selected_answer": "A base case"},
        {"question_id": "q_recursion_02", "concept": "Recursion", "selected_answer": "Track pending calls waiting to complete"},
        {"question_id": "q_recursion_03", "concept": "Recursion", "selected_answer": "No — it depends on the problem and implementation"},

        {"question_id": "q_trees_01", "concept": "Trees", "selected_answer": "It is connected and acyclic"},
        {"question_id": "q_trees_02", "concept": "Trees", "selected_answer": "Exactly one"},
        {"question_id": "q_trees_03", "concept": "Trees", "selected_answer": "BFS on a graph"},

        {"question_id": "q_graphs_01", "concept": "Graphs", "selected_answer": "Graphs generalize trees by allowing cycles and multiple paths"},
        {"question_id": "q_graphs_02", "concept": "Graphs", "selected_answer": "Cycles"},
        {"question_id": "q_graphs_03", "concept": "Graphs", "selected_answer": "The connection only goes one way"},

        {"question_id": "q_bfs_01", "concept": "BFS", "selected_answer": "Stack"},
        {"question_id": "q_bfs_02", "concept": "BFS", "selected_answer": "Deepest node first"},
        {"question_id": "q_bfs_03", "concept": "BFS", "selected_answer": "It ignores edge direction"},

        {"question_id": "q_dfs_01", "concept": "DFS", "selected_answer": "Always finding the shortest path"},
        {"question_id": "q_dfs_02", "concept": "DFS", "selected_answer": "A queue"},
        {"question_id": "q_dfs_03", "concept": "DFS", "selected_answer": "Guaranteeing shortest path in weighted graphs"},

        {"question_id": "q_graphtraversal_01", "concept": "Graph Traversal", "selected_answer": "BFS"},
        {"question_id": "q_graphtraversal_02", "concept": "Graph Traversal", "selected_answer": "What guarantee the problem needs (e.g. shortest path vs reachability)"},
        {"question_id": "q_graphtraversal_03", "concept": "Graph Traversal", "selected_answer": "Shortest-path algorithms like Dijkstra"},

        {"question_id": "q_shortestpaths_01", "concept": "Shortest Paths", "selected_answer": "BFS assumes all edges cost the same, so it can't account for differing weights"},
        {"question_id": "q_shortestpaths_02", "concept": "Shortest Paths", "selected_answer": "Because edge costs differ, so the next-cheapest node isn't always the next-discovered one"},
        {"question_id": "q_shortestpaths_03", "concept": "Shortest Paths", "selected_answer": "A priority queue that always expands the cheapest known node"},

        {"question_id": "q_dijkstra_01", "concept": "Dijkstra", "selected_answer": "Priority queue (min-heap)"},
        {"question_id": "q_dijkstra_02", "concept": "Dijkstra", "selected_answer": "All edge weights must be non-negative"},
        {"question_id": "q_dijkstra_03", "concept": "Dijkstra", "selected_answer": "BFS"}
    ]
}

print("Calling /diagnose ...")
response = httpx.post(DIAGNOSE_URL, json=quiz_submission, timeout=30)
print("status code:", response.status_code)
if response.status_code != 200:
    print("ERROR response body:", response.text)
    raise SystemExit(1)
diagnosis = response.json()
print("root_gap:", diagnosis["root_gap"])
print("weak_concepts:", diagnosis["weak_concepts"])
print("repair_path:", diagnosis["repair_path"])
print("mastery_by_concept:", diagnosis["mastery_by_concept"])