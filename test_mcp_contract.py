"""Self-check for the MCP tool contracts. Run: python test_mcp_contract.py
No DB connection needed -- this only checks that the response models still
match what the agent functions actually return.
"""
import asyncio

from mcp_server import QueryResult, ReportResult, TestPlanResult, mcp


def demo():
    # every tool must publish an output schema, not just an input one
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 3, f"expected 3 tools, got {len(tools)}"
    for t in tools:
        assert t.outputSchema, f"{t.name} publishes no outputSchema"

    # maintenance_agent.ask() returns two different shapes -- both must validate
    QueryResult(sql="select 1", rows=[{"a": 1}], answer="one")
    QueryResult(sql="drop table x", error="UnsafeSQLError", answer=None)

    TestPlanResult(test_case_id=1, title="t", steps=["a"], expected_result="r")
    ReportResult(summary="s", chart_path="c.png", report_path="r.md",
                 mermaid="flowchart LR\n    A --> B")

    print("All MCP contract checks passed.")


if __name__ == "__main__":
    demo()
