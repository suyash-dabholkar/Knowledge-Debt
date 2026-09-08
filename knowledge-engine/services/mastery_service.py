from __future__ import annotations
from collections import defaultdict
from typing import Dict, List
from schemas import QuizAnswer


def calculate_mastery(answers: List[QuizAnswer], questions_by_id: Dict[str, dict]) -> Dict[str, float]:
    correct_count: Dict[str, int] = defaultdict(int)
    total_count: Dict[str, int] = defaultdict(int)

    for answer in answers:
        question = questions_by_id.get(answer.question_id)
        if not question:
            continue
        concept = question["concept"]
        total_count[concept] += 1
        if answer.selected_answer.strip().lower() == question["correct_answer"].strip().lower():
            correct_count[concept] += 1

    return {
        concept: round((correct_count[concept] / total) * 100, 2)
        for concept, total in total_count.items()
    }