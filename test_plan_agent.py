"""Test-plan generation: natural-language requirement -> structured test plan.

Matches the JD's "automated test plan generation using LLMs." Uses LangChain's
structured output so the LLM can't return anything except the shape we need.
"""
import json

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from db import execute_validated

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


class TestPlan(BaseModel):
    title: str = Field(description="Short title for the test case")
    steps: list[str] = Field(description="Ordered list of concrete test steps")
    expected_result: str = Field(description="What a passing run looks like, measurable if possible")


structured_llm = llm.with_structured_output(TestPlan)

PROMPT = """You are a semiconductor validation engineer. Turn the requirement below \
into a concrete, executable test case. Steps must be specific enough that a test \
engineer could run them without asking follow-up questions.

Requirement: {requirement_text}
Category: {category}
Priority: {priority}"""


def generate_test_plan(requirement_id: int, regenerate: bool = False) -> dict:
    """Return the stored plan for a requirement, generating one if absent.

    Idempotent by default -- calling twice for the same requirement returns the
    same test case instead of inserting a duplicate (and skips the LLM call).
    Pass regenerate=True to force a fresh plan.
    """
    rows = execute_validated(
        "select id, requirement_text, category, priority from test_requirements where id = %s",
        (requirement_id,),
    )
    if not rows:
        raise ValueError(f"No requirement with id {requirement_id}")
    req = rows[0]

    if not regenerate:
        existing = execute_validated(
            "select id, title, steps, expected_result from test_cases "
            "where requirement_id = %s order by id limit 1",
            (requirement_id,),
        )
        if existing:
            e = existing[0]
            return {
                "test_case_id": e["id"],
                "title": e["title"],
                "steps": e["steps"],
                "expected_result": e["expected_result"],
            }

    plan: TestPlan = structured_llm.invoke(
        PROMPT.format(
            requirement_text=req["requirement_text"],
            category=req["category"],
            priority=req["priority"],
        )
    )

    inserted = execute_validated(
        "insert into test_cases (requirement_id, title, steps, expected_result, generated_by_llm) "
        "values (%s, %s, %s, %s, true) returning id",
        (requirement_id, plan.title, json.dumps(plan.steps), plan.expected_result),
    )
    return {"test_case_id": inserted[0]["id"], **plan.model_dump()}


if __name__ == "__main__":
    import sys

    req_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    result = generate_test_plan(req_id)
    print(json.dumps(result, indent=2))
