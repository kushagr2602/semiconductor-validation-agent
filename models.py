"""Response models shared by every entry point.

The agents are the product; MCP and the web app are two doors onto them. Both
doors describe their responses with these models, so the shape is defined once.
"""
from pydantic import BaseModel, Field


class TestPlanResult(BaseModel):
    test_case_id: int = Field(description="Primary key of the stored test_cases row")
    title: str = Field(description="Short title for the test case")
    steps: list[str] = Field(description="Ordered list of concrete test steps")
    expected_result: str = Field(description="What a passing run looks like")


class QueryResult(BaseModel):
    sql: str = Field(description="The SQL the agent generated")
    answer: str | None = Field(description="Plain-language answer, or null if the query failed")
    rows: list[dict] = Field(default=[], description="Raw result rows")
    error: str | None = Field(default=None, description="Guardrail or execution error, if any")


class ReportResult(BaseModel):
    summary: str = Field(description="Plain-language summary of recent validation results")
    report_path: str = Field(description="Path to the generated markdown report")
    chart_path: str = Field(description="Path to the generated status bar chart PNG")
    mermaid: str = Field(description="Requirement traceability chain as a mermaid flowchart")
