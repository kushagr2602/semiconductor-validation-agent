"""MCP server exposing the validation agent's tools.

Same exposure pattern as the Polymarket Signal Analyser's MCP server: wrap
existing agent functions as MCP tools so any MCP-compatible client (Claude
Desktop, an orchestrator, another agent) can call them directly.

Return types are Pydantic models rather than bare dicts so each tool publishes
an outputSchema — the calling client knows the response shape before it calls.
"""
from mcp.server.fastmcp import FastMCP

from maintenance_agent import ask as maintenance_ask
from models import QueryResult, ReportResult, TestPlanResult
from report_agent import generate_report
from test_plan_agent import generate_test_plan

mcp = FastMCP("nxp-validation-agent")


@mcp.tool()
def generate_test_plan_tool(requirement_id: int) -> TestPlanResult:
    """Generate a structured test plan from a test_requirements row and store it."""
    return TestPlanResult(**generate_test_plan(requirement_id))


@mcp.tool()
def query_validation_db(question: str) -> QueryResult:
    """Ask a natural-language question about the validation database. Guardrailed: only SELECT/INSERT."""
    return QueryResult(**maintenance_ask(question))


@mcp.tool()
def generate_validation_report(days: int = 30) -> ReportResult:
    """Generate a markdown report + chart summarizing recent test-run results."""
    return ReportResult(**generate_report(days=days))


if __name__ == "__main__":
    mcp.run()
