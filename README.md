# NXP Validation Agent (demo/learning project)

A small, synthetic version of what NXP's Validation Innovation Team builds —
made to prep for a Working Student interview, not a production system. All
data (chip specs, requirements, test results) is fabricated; nothing here
uses real or confidential NXP information.

It mirrors the job posting's three deliverables directly:

| JD deliverable | This project |
|---|---|
| "Maintenance agent for a PostgreSQL database" | `maintenance_agent.py` — natural language -> SQL -> guardrails -> answer |
| "Automated test plan generation using LLMs" | `test_plan_agent.py` — requirement -> structured test plan |
| "Automated report/diagram generation using GenAI" | `report_agent.py` — test runs -> summary + chart |
| MCP tool exposure | `mcp_server.py` — wraps all three as MCP tools |

## Architecture

```
requirement (DB row)
      |
      v
test_plan_agent.py --(Claude, structured output)--> test_cases (DB)
      |
      v
main.py seeds a couple of fake test_runs
      |
      v
maintenance_agent.py --(Claude generates SQL)--> db.py guardrails --> answer
      |
      v
report_agent.py --(Claude summarizes)--> reports/validation_report.md + chart
```

`db.py` is the guardrails layer every agent routes through: only `SELECT`/
`INSERT` are allowed, every statement gets an `EXPLAIN` dry-run before real
execution, and multi-statement injection is blocked. Same shape as the ERP
Data Analyst Agent's guardrails, applied to a different domain.

## Setup

1. Create a free [Supabase](https://supabase.com) project, grab the Postgres
   connection string (Project Settings -> Database -> Connection string).
2. `cp .env.example .env` and fill in `DATABASE_URL` + `ANTHROPIC_API_KEY`.
3. Run the schema against your Supabase project (SQL editor, or `psql
   "$DATABASE_URL" -f schema.sql`).
4. `uv sync`
5. `uv run python seed_data.py` — seeds chip specs + requirements.
6. `uv run python test_db_guardrails.py` — sanity-checks the guardrails
   layer with no DB/API calls needed.
7. `uv run python main.py` — runs the full pipeline end to end.

## Running the MCP server

```
uv run python mcp_server.py
```

Point any MCP client at it (Claude Desktop's config, or a custom client)
to call `generate_test_plan_tool`, `query_validation_db`, and
`generate_validation_report` directly.

## What's simplified vs. a real system

- Schema is injected directly into prompts instead of chunked/embedded —
  fine at this size, wouldn't scale to a real multi-hundred-table schema.
- No auth/multi-tenancy on the MCP server — a real deployment would need it.
- Eval coverage is limited to the guardrails logic (`test_db_guardrails.py`);
  a production version would want labeled eval cases for the SQL-generation
  and test-plan-generation steps too, same as the Polymarket eval harness.
