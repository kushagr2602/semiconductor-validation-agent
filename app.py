"""Web door onto the validation agents.

Third entry point alongside main.py (script) and mcp_server.py (AI clients).
Same agent functions underneath -- this file only handles HTTP.

Run: uv run uvicorn app:app --reload
"""
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import limits
from db import execute_validated
from maintenance_agent import ask as maintenance_ask
from models import QueryResult, ReportResult, TestPlanResult
from report_agent import generate_report
from test_plan_agent import generate_test_plan

app = FastAPI(title="NXP Validation Agent")
STATIC = Path(__file__).parent / "static"
REPORTS = Path(__file__).parent / "reports"

# Set DEMO_MODE=1 on the public deployment. It caps spend and refuses the one
# operation that always costs a fresh LLM call (forced regeneration).
DEMO_MODE = os.getenv("DEMO_MODE", "").lower() in {"1", "true", "yes"}


def client_ip(request: Request) -> str:
    """Real client IP. Hosting proxies put it first in X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def spend_guard(request: Request) -> None:
    """Dependency for every endpoint that can trigger an OpenAI call."""
    if not DEMO_MODE:
        return
    try:
        limits.check_and_consume(client_ip(request))
    except limits.RateLimited as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


class AskRequest(BaseModel):
    question: str


class TestPlanRequest(BaseModel):
    requirement_id: int
    regenerate: bool = False


@app.get("/api/requirements")
def list_requirements() -> list[dict]:
    """Requirements joined to their chip, plus whether a test case exists yet."""
    return execute_validated(
        "select treq.id, treq.requirement_text, treq.category, treq.priority, "
        "cs.chip_name, count(tc.id) as case_count "
        "from test_requirements treq "
        "join chip_specs cs on cs.id = treq.chip_id "
        "left join test_cases tc on tc.requirement_id = treq.id "
        "group by treq.id, treq.requirement_text, treq.category, treq.priority, cs.chip_name "
        "order by cs.chip_name, treq.id"
    )


@app.get("/api/demo-status")
def demo_status() -> dict:
    """Lets the UI show the visitor what the limits are before they hit one."""
    return {"demo_mode": DEMO_MODE, **(limits.usage() if DEMO_MODE else {})}


@app.post("/api/test-plan")
def api_test_plan(req: TestPlanRequest, _=Depends(spend_guard)) -> TestPlanResult:
    if DEMO_MODE and req.regenerate:
        raise HTTPException(
            status_code=403,
            detail="Regeneration is disabled in the public demo -- it forces a fresh "
                   "LLM call every time. Existing plans are shown instead.",
        )
    try:
        return TestPlanResult(**generate_test_plan(req.requirement_id, regenerate=req.regenerate))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/ask")
def api_ask(req: AskRequest, _=Depends(spend_guard)) -> QueryResult:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if len(req.question) > 500:
        raise HTTPException(status_code=400, detail="Question is too long (500 character limit).")
    return QueryResult(**maintenance_ask(req.question))


@app.post("/api/report")
def api_report(days: int = 30, _=Depends(spend_guard)) -> ReportResult:
    return ReportResult(**generate_report(days=days))


@app.get("/api/chart")
def chart():
    path = REPORTS / "status_breakdown.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No chart yet -- generate a report first.")
    return FileResponse(path, media_type="image/png")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
