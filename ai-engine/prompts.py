"""
Prompt templates for the Knowledge Debt AI Learning & Debt Repayment Engine.

All prompts are kept here, out of main.py and services/, so they can be
iterated on independently of application logic.
"""

import json
from typing import Any, Dict, List, Optional


SYSTEM_PROMPT = """You are an adaptive tutor inside "Knowledge Debt", a system that repairs \
hidden prerequisite knowledge gaps rather than re-teaching a topic a student already failed.

You will be given a DIAGNOSIS produced by a separate diagnostic engine. This diagnosis is \
authoritative and MUST NOT be second-guessed, changed, or replaced. Specifically:

- Do NOT decide or imply a different root_gap than the one given to you.
- Do NOT invent facts about the student that were not provided.
- Do NOT deviate from the given repair_path ordering.
- DO explicitly teach to the given root_misconception, not just define the concept generically.
- DO calibrate explanation depth and vocabulary to the given student_level.
- DO keep explanations concise but conceptually precise — no filler.
- DO produce exactly 3 practice questions with increasing difficulty: easy (conceptual), \
medium (application), medium (reasoning).
- DO ground your answer in the provided concept knowledge base facts; do not invent \
prerequisite relationships that contradict it.

You MUST respond with valid JSON only — no markdown fences, no commentary, no preamble. \
The JSON must match the exact schema described in the user message."""


def build_learning_prompt(
    student_id: str,
    concept: str,
    student_level: str,
    root_gap: str,
    root_misconception: str,
    weak_concepts: List[str],
    repair_path: List[str],
    concept_context: Dict[str, Any],
    reinforced_misconceptions: Optional[List[str]] = None,
    attempt_number: int = 1,
) -> str:
    """Builds the user-turn prompt for /learn content generation."""

    reinforcement_block = ""
    if reinforced_misconceptions:
        joined = "\n".join(f"- {m}" for m in reinforced_misconceptions)
        reinforcement_block = f"""

ADDITIONAL SIGNAL FROM PRIOR PRACTICE (this student has shown these specific
misconceptions on THIS concept during earlier practice attempts — address
them explicitly alongside root_misconception, don't just repeat root_misconception
verbatim):
{joined}"""

    retry_note = ""
    if attempt_number > 1:
        retry_note = f"""

This is attempt #{attempt_number} at teaching this concept to this student. The
previous attempt(s) did not fully resolve the gap — simplify your explanation
and analogy further than you would for a first attempt, and avoid repeating
the exact same analogy or example as a generic first pass would use."""

    return f"""DIAGNOSIS (authoritative — do not question or change this):
student_id: {student_id}
concept_to_teach: {concept}
student_level: {student_level}
root_gap: {root_gap}
root_misconception: {root_misconception}
weak_concepts: {json.dumps(weak_concepts)}
repair_path: {json.dumps(repair_path)}
{reinforcement_block}{retry_note}

CONCEPT KNOWLEDGE BASE CONTEXT (ground your explanation in these facts, do not contradict them):
{json.dumps(concept_context, indent=2)}

TASK:
Generate a personalized repair lesson for "{concept}" that explicitly teaches through the
root_misconception above. Follow this structure:

A. Diagnosis: what the student appears to misunderstand, in plain language.
B. Why it matters: how this gap affects downstream learning (reference the repair_path).
C. Simple explanation calibrated to student_level.
D. An intuitive real-world analogy.
E. A small, concrete DSA example (pseudocode or worked trace is fine).
F. 3-5 concise key takeaways.
G. Exactly 3 practice questions (easy conceptual, medium application, medium reasoning),
   each with 4 multiple-choice options, one correct_answer (must exactly match one option),
   a short explanation of why it's correct, and a hint that does not give away the answer.
H. next_step: which concept in the repair_path the student should study next.
I. estimated_minutes: a realistic integer estimate for this repair step (typically 3-10).

Respond with ONLY this JSON shape (no extra keys, no markdown fences):

{{
  "diagnosis": "...",
  "explanation": "...",
  "analogy": "...",
  "example": "...",
  "key_points": ["...", "...", "..."],
  "practice_questions": [
    {{
      "id": "q1",
      "difficulty": "easy",
      "question": "...",
      "options": ["...", "...", "...", "..."],
      "correct_answer": "...",
      "explanation": "...",
      "hint": "..."
    }},
    {{
      "id": "q2",
      "difficulty": "medium",
      "question": "...",
      "options": ["...", "...", "...", "..."],
      "correct_answer": "...",
      "explanation": "...",
      "hint": "..."
    }},
    {{
      "id": "q3",
      "difficulty": "medium",
      "question": "...",
      "options": ["...", "...", "...", "..."],
      "correct_answer": "...",
      "explanation": "...",
      "hint": "..."
    }}
  ],
  "next_step": "...",
  "estimated_minutes": 5
}}"""


def build_misconception_prompt(
    concept: str,
    question_text: str,
    student_answer: str,
    correct_answer: str,
) -> str:
    """Builds a prompt to identify the likely misconception behind a wrong answer."""

    return f"""A student answered a practice question incorrectly.

concept: {concept}
question: {question_text}
correct_answer: {correct_answer}
student_answer: {student_answer}

Identify the SPECIFIC likely misconception behind this wrong answer (one or two sentences),
grounded in known DSA misconceptions (e.g. BFS/DFS mechanism confusion, traversal vs
shortest-path confusion, weighted vs unweighted confusion). Then write a short hint (not the
answer itself) that nudges the student toward the correct reasoning, and one targeted
follow-up multiple-choice question (4 options) that isolates this specific misconception.

Respond with ONLY this JSON shape:

{{
  "likely_misconception": "...",
  "hint": "...",
  "follow_up_question": {{
    "id": "followup_1",
    "difficulty": "easy",
    "question": "...",
    "options": ["...", "...", "...", "..."],
    "correct_answer": "...",
    "explanation": "...",
    "hint": "..."
  }}
}}"""


def build_hint_prompt(concept: str, question_text: str, student_level: str) -> str:
    """Builds a prompt for a standalone hint request."""

    return f"""concept: {concept}
student_level: {student_level}
question: {question_text}

Give ONE short hint (1-2 sentences) that nudges the student toward the correct reasoning
WITHOUT revealing the answer outright. Respond with ONLY this JSON shape:

{{"hint": "..."}}"""
