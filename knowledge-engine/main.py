"""
Knowledge Debt — Knowledge Graph & Diagnostic Engine (Member 1's module).

Run with:
    uvicorn main:app --reload --port 8001

Docs at http://127.0.0.1:8001/docs
"""

from fastapi import FastAPI

app = FastAPI(
    title="Knowledge Debt — Knowledge Graph & Diagnostic Engine",
    description=(
        "Member 1's module. Diagnoses a student against the concept "
        "prerequisite graph and returns the root gap + repair path."
    ),
    version="1.0.0",
)


@app.get("/")
def root():
    return {"status": "ok", "service": "knowledge-debt-diagnostic-engine"}