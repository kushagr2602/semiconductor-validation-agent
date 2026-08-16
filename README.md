# Semiconductor Validation Agent

GenAI tooling over a PostgreSQL chip-validation database: generate test plans
from requirements, answer questions about test results in natural language, and
produce reports with a requirement-traceability diagram.

Built to prepare for a Working Student interview on a semiconductor validation
team — a demo, not a production system. **All data is fabricated** (chip specs,
requirements, test results); nothing here uses real or confidential information
from any company.

It maps onto the job posting's deliverables:

| JD deliverable | This project |
|---|---|
| "Maintenance agent for a PostgreSQL database" | `maintenance_agent.py` — question → SQL → guardrails → answer |
| "Automated test plan generation using LLMs" | `test_plan_agent.py` — requirement → structured test plan |
| "Automated report/diagram generation using GenAI" | `report_agent.py` — runs → summary + chart + mermaid traceability |
| MCP tool exposure | `mcp_server.py` — all three as MCP tools |

## Architecture

The agents are the product. Everything else is a door onto them:

```
  main.py            mcp_server.py          app.py
  (CLI demo)         (MCP clients)          (FastAPI + web UI)
       \                   |                    /
        \                  |                   /
         +----------- the agents --------------+
              test_plan · maintenance · report
                          |
                     db.py guardrails
                          |
                      PostgreSQL
```

Delete any one entry point and the other two still work — none of them holds
business logic. `models.py` defines the response shapes once, so the MCP tools
and the HTTP endpoints describe themselves identically.

Two models are used, deliberately:

- **`gpt-4o`** for SQL generation. `gpt-4o-mini` degenerates into a repetition
  loop on this task (repeating column names until it hits the token ceiling),
  at temperature 0 and 0.2 alike.
- **`gpt-4o-mini`** for prose — test plans and report summaries — where it is
  reliable and cheaper.

The mermaid traceability diagram is built **in code**, not by an LLM. The rows
come back structured from SQL, so a model would only re-derive what is already
known, adding cost and a chance of inventing nodes.

## Guardrails

`db.py` is the layer every agent routes through. LLM-generated SQL passes:

1. a leading-keyword allow-list (`SELECT` / `INSERT` / `WITH`), rejection of
   multi-statement input, and a blocked-keyword regex;
2. an `EXPLAIN` dry-run, which makes Postgres parse and plan the statement
   without executing it;
3. real execution, with parameters bound separately from the query text.

**Known gap, stated plainly:** a regex cannot classify SQL. `SELECT` is not a
synonym for read-only, so `select pg_terminate_backend(...)`, `select pg_sleep(...)`,
and a bulk `insert ... select from generate_series(...)` that forges passing
test runs all pass the check today. It also produces false positives — a test
note containing the word "delete" is rejected.

The correct fix is a read-only Postgres role plus a `statement_timeout`, so the
database enforces the boundary and there is nothing to bypass; the Python check
then stays as a cheap first filter. That is **not implemented yet**.

## Setup

```bash
uv sync
cp .env.example .env          # then fill in DATABASE_URL and OPENAI_API_KEY
uv run python seed_data.py    # creates the schema and seeds it; safe to re-run
```

### Connection note

Supabase's direct host (`db.<ref>.supabase.co`) is **IPv6-only**. On a network
without IPv6 routing it fails with `could not translate host name`, which reads
like a typo but means "no reachable address family". Use the transaction pooler
instead — note the port and the username format:

```
postgresql://postgres.<project-ref>:<password>@aws-1-<region>.pooler.supabase.com:6543/postgres
```

The username carries the project ref because one pooler fronts many tenants.

## Running it

```bash
uv run python main.py                              # full pipeline, end to end
uv run uvicorn app:app --reload --port 8000        # web UI at localhost:8000
uv run python mcp_server.py                        # MCP server (stdio)
```

The web UI generates test plans per requirement, answers questions about the
database (showing the generated SQL, not just the answer), and renders the
report with its traceability diagram.

Point any MCP client at the server to call `generate_test_plan_tool`,
`query_validation_db`, and `generate_validation_report`.

## Tests

No database or API key required — all three run offline:

```bash
uv run python test_db_guardrails.py    # allow-list and blocked-keyword behaviour
uv run python test_mcp_contract.py     # every tool publishes an outputSchema;
                                       # models accept success and error shapes
uv run python test_report_diagram.py   # mermaid escaping and node de-duplication
```

## What's simplified vs. a real system

- **Guardrails are not a real security boundary** — see above. The database role
  is the missing piece.
- **The schema is injected straight into the prompt** rather than chunked or
  embedded. Fine at four tables; would not scale to a few hundred.
- **No auth or multi-tenancy** on the MCP server or the web app.
- **Every query opens two connections** (dry-run, then execute). Harmless here,
  wasteful through a pooler.
- **Eval coverage is structural, not behavioural.** The tests check guardrail
  logic, tool contracts, and diagram generation. A production version would want
  labelled eval cases for SQL-generation and test-plan quality — the parts where
  the model can be confidently wrong rather than obviously broken.
