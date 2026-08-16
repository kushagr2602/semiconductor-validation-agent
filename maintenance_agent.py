"""Maintenance agent for the PostgreSQL validation database.

Same pattern as the ERP Data Analyst Agent: natural-language question ->
LLM generates SQL grounded in the schema -> guardrails (db.execute_validated)
-> LLM formats the raw rows into a readable answer.

# ponytail: schema is small enough to inject directly as context instead of
# chunking/embedding it (real RAG). Swap in a vector store if the schema
# grows past what fits in a prompt.
"""
from pathlib import Path

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from db import execute_validated

SCHEMA = Path(__file__).parent.joinpath("schema.sql").read_text()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


class SQLQuery(BaseModel):
    sql: str = Field(description="A single SELECT or INSERT statement, no trailing semicolon issues")
    reasoning: str = Field(description="One sentence on why this query answers the question")


# Schema-grounded SQL generation needs the larger model: gpt-4o-mini reliably
# degenerates into a repetition loop here (repeating column names until it hits
# the token ceiling), at both temperature 0 and 0.2. max_tokens caps the damage
# if a future model regresses the same way -- one statement never needs 500.
sql_llm = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=500).with_structured_output(SQLQuery)

SQL_PROMPT = """You are a database agent for a semiconductor validation system. \
Given the schema below and a question, write ONE PostgreSQL statement (SELECT or \
INSERT only) that answers it.

Schema:
{schema}

Question: {question}"""

ANSWER_PROMPT = """Question: {question}

Query result (JSON rows):
{rows}

Answer the question in plain language, citing specific numbers from the result. \
If the result is empty, say so plainly instead of guessing. Write prose only -- \
no markdown, no asterisks, no bullet points; the answer is rendered as plain text."""


def ask(question: str) -> dict:
    query: SQLQuery = sql_llm.invoke(SQL_PROMPT.format(schema=SCHEMA, question=question))

    try:
        rows = execute_validated(query.sql)
    except Exception as exc:
        return {"sql": query.sql, "error": str(exc), "answer": None}

    answer = llm.invoke(ANSWER_PROMPT.format(question=question, rows=rows)).content

    return {"sql": query.sql, "rows": rows, "answer": answer}


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "How many high-priority thermal requirements do we have?"
    result = ask(q)
    print(f"SQL: {result['sql']}\n")
    if result.get("error"):
        print(f"Error: {result['error']}")
    else:
        print(f"Answer: {result['answer']}")
