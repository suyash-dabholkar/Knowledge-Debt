# Knowledge Debt — AI Learning & Debt Repayment Engine (Member 2)

## What this module does

This is **Member 2's** module inside the *Knowledge Debt* hackathon project.

It does **not** decide what a student is struggling with. Member 1's diagnostic
engine already figured that out — the true **root gap** and **root
misconception** behind a student's failure. This module's job is to turn that
diagnosis into:

1. A personalized repair **lesson** (explanation, analogy, worked example, key
   points) that teaches straight at the misconception, not a generic
   definition of the surface topic.
2. **Adaptive practice questions** that get harder on success and pivot to a
   targeted follow-up on failure.
3. A **reassessment** pass that measures whether the repair actually worked,
   with a transparent, explainable mastery formula.

## Why this is not just an LLM wrapper

1. Member 1 provides the diagnosis (`root_gap`, `root_misconception`,
   `repair_path`) — this module never re-derives or second-guesses it.
2. The AI receives a **structured misconception**, not just a topic name, and
   is explicitly instructed to teach through that misconception.
3. Content is personalized around the student's level, the misconception, the
   weak concepts, and where this step sits in the repair path.
4. Questions adapt: `/practice` reads the *type* of wrong answer and infers a
   likely misconception instead of just marking it wrong.
5. `/reassess` measures improvement with an explainable formula and is
   explicit that 3 questions is a prototype-level estimate, not proof of
   mastery.
6. The mastery/debt-reduced verdict is designed to feed back into the larger
   Knowledge Debt loop (`ASSESS → DETECT → TRACE → REPAIR → REASSESS`).

## Architecture

```
ai-engine/
├── main.py                        # FastAPI app, routes, CORS, error handling
├── schemas.py                     # Pydantic models (request/response contracts)
├── prompts.py                     # All LLM prompt templates (nothing in main.py)
├── llm.py                         # Provider abstraction + retry + deterministic fallback
├── services/
│   ├── learning_service.py        # Orchestrates /learn (grounds LLM in concepts.json)
│   ├── reassessment_service.py    # Mastery scoring formula for /reassess + /reassess/batch
│   ├── misconception_service.py   # Rule-based misconception detection for /practice
│   └── student_state.py           # In-memory session state (attempt counts, surfaced misconceptions)
├── data/
│   └── concepts.json              # Local knowledge base (descriptions, prereqs, misconceptions)
├── tests/
│   ├── test_learn.py
│   ├── test_reassess.py
│   ├── test_reassess_batch.py
│   ├── test_practice_and_hint.py
│   └── test_llm_fallback.py
├── requirements.txt
├── .env.example
└── .gitignore
```

**Architectural principle:** the diagnostic engine (Member 1) controls
educational reasoning (*what* is wrong). The LLM controls personalized
content generation (*how* to teach it). `llm.py` and `services/` never let
the LLM output override `root_gap`, `root_misconception`, or `repair_path` —
those are always echoed back from the input, not regenerated.

## Setup

```bash
cd ai-engine
pip install -r requirements.txt --break-system-packages   # or use a venv
cp .env.example .env
```

### Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `LLM_API_KEY` | API key for the LLM provider. **Leave blank to run in deterministic demo/fallback mode.** | *(empty)* |
| `LLM_API_URL` | LLM Messages endpoint | `https://api.anthropic.com/v1/messages` |
| `LLM_MODEL` | Model name | `claude-sonnet-4-6` |
| `LLM_TIMEOUT_SECONDS` | Per-request timeout before falling back | `20` |
| `LLM_MAX_RETRIES` | Retry attempts for transient network/HTTP errors before falling back | `2` |
| `LLM_RETRY_BACKOFF_SECONDS` | Linear backoff multiplier between retries | `1` |
| `MASTERY_THRESHOLD_MASTERED` | Mastery ≥ this → `"mastered"` | `80` |
| `MASTERY_THRESHOLD_IMPROVING` | Mastery ≥ this → `"improving"` | `60` |
| `MASTERY_NEW_SCORE_WEIGHT` | Weight given to the new quiz score vs. prior mastery (0–1) | `0.7` |
| `DEBT_REDUCED_MIN_IMPROVEMENT` | Minimum point improvement to count as debt reduced (below "mastered") | `10` |

**No LLM key is required.** If `LLM_API_KEY` is unset, empty, or the LLM call
fails/returns malformed JSON for any reason, the app automatically falls back
to deterministic, hand-authored content so the API — and your demo — never
breaks. A transient network error is retried (`LLM_MAX_RETRIES` attempts with
linear backoff) before falling back; malformed JSON is not retried, since
retrying the same prompt won't change a parsing failure. Every `/learn`
response includes `"source": "llm"` or `"source": "fallback"` so you always
know which path was used.

## Running

```bash
uvicorn main:app --reload
```

Visit **http://127.0.0.1:8000/docs** for interactive Swagger docs covering
`GET /`, `GET /concepts/{name}`, `POST /learn`, `POST /reassess`,
`POST /reassess/batch`, `POST /practice`, `POST /hint`.

## Running tests

```bash
python -m pytest tests/ -v
```

30 tests, run entirely offline — no LLM API key or network access required,
since they exercise the deterministic fallback path. Coverage includes
`/learn`, `/reassess`, `/reassess/batch`, `/practice`, `/hint`,
`/concepts/{name}`, the JSON-extraction helper in `llm.py`, and the
cross-endpoint adaptive loop (a misconception surfaced in `/practice`
reappearing in a subsequent `/learn` call's `reinforced_misconceptions`).

## API endpoints

### `POST /learn` (P0 — required)

Receives Member 1's diagnosis and returns a personalized repair lesson.

**Example request:**

```json
{
  "student_id": "student_001",
  "concept": "BFS",
  "student_level": "beginner",
  "root_gap": "BFS",
  "root_misconception": "Student confuses BFS and DFS and does not understand why BFS uses a queue.",
  "weak_concepts": ["BFS", "DFS", "Graph Traversal"],
  "repair_path": ["BFS", "DFS", "Graph Traversal", "Shortest Paths", "Dijkstra"],
  "previous_attempts": []
}
```

**Example response (truncated):**

```json
{
  "student_id": "student_001",
  "concept": "BFS",
  "root_gap": "BFS",
  "diagnosis": "...",
  "explanation": "BFS uses a QUEUE (first-in, first-out)...",
  "analogy": "Picture ripples spreading outward from a stone dropped in a pond...",
  "example": "Graph: A-B, A-C, B-D, C-D. BFS from A: ...",
  "key_points": ["...", "...", "..."],
  "practice_questions": [ { "id": "bfs_q1", "difficulty": "easy", "...": "..." }, ... ],
  "next_step": "DFS",
  "estimated_minutes": 6,
  "source": "fallback",
  "attempt_number": 1,
  "reinforced_misconceptions": []
}
```

`attempt_number` and `reinforced_misconceptions` come from
`services/student_state.py`, an in-memory (per-server-process) store keyed by
`(student_id, concept)`. If the same student has previously answered a
practice question wrong for this concept via `/practice`, the surfaced
misconception is passed back into the next `/learn` call's prompt so the
lesson explicitly re-addresses it instead of repeating the same generic
explanation — this is what closes the loop between "adaptive questioning"
and "personalized teaching." This state resets when the server restarts and
is not shared across multiple worker processes — an accepted limitation for
a hackathon MVP; swapping in a Redis- or DB-backed store later requires no
changes to callers.

### `POST /reassess` (P0 — required)

Scores a micro-assessment and returns an updated mastery estimate.

**Example request:**

```json
{
  "student_id": "student_001",
  "concept": "BFS",
  "previous_mastery": 37,
  "questions": [
    { "question_id": "bfs_01", "answer": "Queue", "correct_answer": "Queue" },
    { "question_id": "bfs_02", "answer": "Level by level", "correct_answer": "Level by level" },
    { "question_id": "bfs_03", "answer": "It explores nodes in increasing distance from the source", "correct_answer": "It explores nodes in increasing distance from the source" }
  ]
}
```

**Example response:**

```json
{
  "student_id": "student_001",
  "concept": "BFS",
  "previous_mastery": 37.0,
  "new_mastery": 81.1,
  "improvement": 44.1,
  "score": 100.0,
  "mastery_status": "mastered",
  "debt_reduced": true,
  "recommendation": "Continue to Graph Traversal.",
  "note": "Mastery is an estimated prototype metric, not a scientifically validated measurement."
}
```

#### Mastery formula (transparent, configurable)

```
score          = % of reassessment questions answered correctly
new_mastery    = (1 - MASTERY_NEW_SCORE_WEIGHT) * previous_mastery
                 + MASTERY_NEW_SCORE_WEIGHT * score
improvement    = new_mastery - previous_mastery
debt_reduced   = improvement >= DEBT_REDUCED_MIN_IMPROVEMENT OR mastery_status == "mastered"
```

The new score is weighted more heavily than prior mastery (default 70/30)
because reassessment exists specifically to measure whether *this* repair
step worked, while still not discarding the student's trajectory entirely.
Thresholds live in one place (`services/reassessment_service.py`, env
override-able) rather than scattered through the code.

### `POST /reassess/batch` (P1 — optional, implemented)

Reassesses several concepts in one call and infers which **downstream**
concepts — not directly reassessed — likely had their debt reduced too,
based on the local prerequisite graph in `data/concepts.json`. This is what
makes the core product story concrete: *"we repaired BFS, and that's why
Dijkstra improved"* instead of *"we separately reassessed five topics."*

**Example request:**

```json
{
  "assessments": [
    {
      "student_id": "student_001", "concept": "BFS", "previous_mastery": 37,
      "questions": [
        { "question_id": "q1", "answer": "Queue", "correct_answer": "Queue" },
        { "question_id": "q2", "answer": "Level by level", "correct_answer": "Level by level" },
        { "question_id": "q3", "answer": "It explores nodes in increasing distance from the source", "correct_answer": "It explores nodes in increasing distance from the source" }
      ]
    }
  ]
}
```

**Example response:**

```json
{
  "results": [
    { "student_id": "student_001", "concept": "BFS", "new_mastery": 81.1, "debt_reduced": true, "...": "..." }
  ],
  "downstream_concepts_likely_improved": ["Dijkstra", "Graph Traversal", "Shortest Paths"],
  "summary": "Debt reduced for BFS. This likely also improves Dijkstra, Graph Traversal, Shortest Paths, since they build on it in the local prerequisite graph (inferred, not separately measured)."
}
```

The `downstream_concepts_likely_improved` list is explicitly labeled as an
**inference**, not a measured result — it walks the KB's prerequisite graph,
it doesn't reassess those concepts.

### `POST /practice` (P1 — optional, implemented)

Given a single answered practice question, returns adaptive feedback:

- **Correct** → `difficulty_direction: "increase"`, encouraging feedback.
- **Incorrect** → identifies a likely misconception (LLM if configured, rule
  matching otherwise), a hint, and a targeted follow-up question — never a
  bare "Incorrect, the answer is X." The misconception is also recorded in
  `student_state` so the next `/learn` call for this student+concept can
  reinforce it (see above).

### `POST /hint` (P1 — optional, implemented)

Standalone hint generation for a given question, with a deterministic
fallback if no LLM is configured.

### `GET /concepts/{name}` (debug / integration-testing helper)

Returns the local knowledge base entry for a concept (description,
prerequisites, common misconceptions, key ideas, examples). Useful for
Member 1 and Member 3 to sanity-check what this module knows about a concept
without opening `data/concepts.json` directly. Returns 404 for an unknown
concept.

## Demo flow (matches the hackathon script)

1. Student scores poorly across Dijkstra (21%), Shortest Paths (31%), Graphs
   (43%), BFS/DFS (37%).
2. Member 1 diagnoses **root gap: BFS/DFS**, misconception: *"confuses BFS and
   DFS, doesn't understand why BFS uses a queue."*
3. Frontend calls `POST /learn` with that diagnosis → gets back a BFS-focused
   lesson (explanation, analogy, example, 3 questions, hints) — the `source`
   field shows `"fallback"` if no LLM key is set, `"llm"` otherwise.
4. Student answers the practice questions; wrong answers go to `POST /practice`
   for a targeted, misconception-aware follow-up. If the student re-attempts
   `/learn` for the same concept, the surfaced misconception is folded into
   the new lesson (`reinforced_misconceptions`, `attempt_number` in the response).
5. Frontend calls `POST /reassess` (or `POST /reassess/batch` to show the
   cascade across concepts) with the micro-assessment results → mastery moves
   from 37 toward the 80s/90s range (exact numbers depend on the transparent
   formula above; the hackathon script's 37 → 89 and 21 → 78 are illustrative
   demo values, not hardcoded). `/reassess/batch` additionally names which
   downstream concepts (e.g. Dijkstra) likely improved as a side effect of
   repairing BFS.

## How fallback mode works

`llm.py` centralizes all LLM calls behind `generate_learning_content`,
`generate_misconception_followup`, and `generate_hint`. If `LLM_API_KEY` is
empty, the HTTP call fails after retries, times out, or returns text that
isn't valid JSON, each function silently falls back to deterministic,
hand-authored content (hand-tuned for BFS, DFS, and Dijkstra — the exact demo
scenario — plus a generic template grounded in `data/concepts.json` for any
other concept). The frontend never sees a 500 error because an LLM was
unavailable.

## How Member 1 integrates with this module

Send a `POST /learn` request whose body matches `DiagnosisRequest` in
`schemas.py`:

```
student_id, concept, student_level, root_gap, root_misconception,
weak_concepts, repair_path, previous_attempts
```

This module trusts `root_gap`, `root_misconception`, and `repair_path`
completely — it never tries to re-diagnose the student. Member 1 does not
need to know anything about this module's internals beyond this JSON
contract. `GET /concepts/{name}` is available if Member 1 wants to
cross-check their knowledge graph against this module's local one.

## How Member 3 (frontend) integrates with this module

- Call `POST /learn` after Member 1's diagnosis is available; render
  `explanation` / `analogy` / `example` / `key_points`, then the
  `practice_questions` (each has `options`, `correct_answer`, `explanation`,
  `hint` — don't show `correct_answer` until after the student answers).
- Optionally call `POST /practice` per answered question for adaptive
  follow-ups instead of just checking `answer == correct_answer` client-side.
  Re-calling `/learn` afterward for the same concept will reflect any
  misconception surfaced this way.
- After the student finishes practice, call `POST /reassess` (single concept)
  or `POST /reassess/batch` (multiple concepts, to show the debt-cascade
  story) with their results to get an updated mastery estimate and a
  `recommendation` string for what to show next.
- All responses are plain, validated JSON — no raw LLM text, no internal
  prompts, no API keys are ever returned.
- CORS is enabled for all origins for local development convenience.

## Error handling

- Malformed requests (missing `root_misconception`, empty `repair_path`,
  `previous_mastery` out of `[0, 100]`, empty `questions`/`assessments`, etc.)
  return a clean `422` with `{"error": "validation_error", "detail": "<field>: <message>"}`
  via a custom `RequestValidationError` handler in `main.py`, instead of
  FastAPI's default nested error format.
- Unexpected internal errors return a `500` with a short `detail` message —
  never a raw stack trace.
- An unknown concept in `/learn` never 500s: `_build_relevant_context` always
  supplies *something* to ground the lesson, and the generic fallback
  template covers any concept not hand-authored in `llm.py`.
- LLM failures (missing key, timeout, HTTP error after retries, malformed
  JSON) always degrade to the deterministic fallback rather than surfacing
  an error to the caller.

## Security notes

- No API keys are hard-coded; `LLM_API_KEY` is read from the environment via
  `python-dotenv` / `os.getenv`.
- `.env` is git-ignored; only `.env.example` (with blank secrets) is committed.
- Internal prompts and raw LLM responses are never returned to the client —
  only validated, schema-shaped JSON.
- LLM output is always parsed and validated through Pydantic before being
  returned; malformed output triggers the deterministic fallback rather than
  being passed through.
