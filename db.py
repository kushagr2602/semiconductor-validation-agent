"""Postgres connection + guardrails.

Same pattern as the ERP Data Analyst Agent: an LLM-generated SQL statement
never touches the database directly. It goes through a dry-run (EXPLAIN)
first, then an allow-listed execution path. This is the guardrails layer
that lets a "maintenance agent" be trusted against real data.
"""
import os
import re

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# Hosting dashboards routinely capture a trailing newline when a secret is
# pasted. The OpenAI client sends the key verbatim, so that stray character
# turns a valid key into a failing one. Strip the keys once, at import, before
# any client is constructed -- db.py is imported by every agent.
for _key_var in ("OPENAI_API_KEY", "DATABASE_URL"):
    _val = os.environ.get(_key_var)
    if _val and _val != _val.strip():
        os.environ[_key_var] = _val.strip()

# "with" allows read-only CTEs. Postgres does permit data-modifying CTEs
# (with x as (delete ... returning *) select ...), but the keyword regex below
# still catches those.
ALLOWED_LEADING_KEYWORDS = ("select", "insert", "with")


class UnsafeSQLError(Exception):
    pass


def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def _leading_keyword(sql: str) -> str:
    parts = sql.strip().split(None, 1)
    return parts[0].lower().rstrip(";") if parts else ""


def is_safe_statement(sql: str) -> None:
    """Raises UnsafeSQLError if the statement isn't allowed. No return value."""
    stripped = sql.strip()
    if ";" in stripped.rstrip(";"):
        raise UnsafeSQLError("Multiple statements in one call are not allowed.")
    keyword = _leading_keyword(stripped)
    if keyword not in ALLOWED_LEADING_KEYWORDS:
        raise UnsafeSQLError(
            f"Statement type '{keyword}' is not allowed. Only SELECT and INSERT are permitted."
        )
    if re.search(r"\b(drop|truncate|delete|update|alter|grant)\b", stripped, re.IGNORECASE):
        raise UnsafeSQLError("Statement contains a disallowed keyword.")


def dry_run(sql: str, params: tuple | None = None) -> None:
    """Runs EXPLAIN against the statement to catch syntax/plan errors before real execution.

    Params must be passed through: psycopg2 only substitutes placeholders when
    it is given values, so EXPLAIN would otherwise receive a literal '%s' and
    fail to parse. Plain EXPLAIN plans the statement without executing it.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"EXPLAIN {sql}", params)
    finally:
        conn.close()


def execute_validated(sql: str, params: tuple | None = None) -> list[dict]:
    """Guardrailed execution: safety check -> dry-run -> real execute.

    Returns rows as a list of dicts. For INSERT statements, include a
    RETURNING clause if you want the inserted row back.
    """
    is_safe_statement(sql)
    dry_run(sql, params)

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            conn.commit()
            if cur.description is None:
                return []
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
