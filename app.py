"""Web door onto the validation agents.

Third entry point alongside main.py (script) and mcp_server.py (AI clients).
Same agent functions underneath -- this file only handles HTTP.

Run: uv run uvicorn app:app --reload
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from db import execute_validated
from maintenance_agent import ask as maintenance_ask
from models import QueryResult, ReportResult, TestPlanResult
from report_agent import generate_report
from test_plan_agent import generate_test_plan

app = FastAPI(title="NXP Validation Agent")
STATIC = Path(__file__).parent / "static"
REPORTS = Path(__file__).parent / "reports"


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


@app.post("/api/test-plan")
def api_test_plan(req: TestPlanRequest) -> TestPlanResult:
    try:
        return TestPlanResult(**generate_test_plan(req.requirement_id, regenerate=req.regenerate))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/ask")
def api_ask(req: AskRequest) -> QueryResult:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    return QueryResult(**maintenance_ask(req.question))


@app.post("/api/report")
def api_report(days: int = 30) -> ReportResult:
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
