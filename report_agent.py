"""Automated report/diagram generation from validation results.

Matches the JD's "automated report/diagram generation using GenAI." Pulls
recent test runs, has the LLM summarize the pass/fail picture in plain
language, and renders a simple bar chart alongside it.
"""
from collections import Counter
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from langchain_openai import ChatOpenAI

from db import execute_validated

matplotlib.use("Agg")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

REPORT_PROMPT = """You are summarizing semiconductor chip validation results for an \
engineering lead. Write a 3-4 sentence summary of the results below: what's passing, \
what's failing, and any pattern worth flagging (e.g. one category failing more than \
others). Be specific, cite counts.

Results by status: {status_counts}
Results by category and status: {category_breakdown}
Recent failures (test case title, notes): {recent_failures}"""


TRACEABILITY_SQL = """
select cs.id as chip_id, cs.chip_name,
       treq.id as req_id, treq.category, treq.priority,
       tc.id as case_id, tc.title,
       count(tr.id) filter (where tr.status = 'pass') as passed,
       count(tr.id) filter (where tr.status = 'fail') as failed
from chip_specs cs
join test_requirements treq on treq.chip_id = cs.id
join test_cases tc on tc.requirement_id = treq.id
left join test_runs tr on tr.test_case_id = tc.id
group by cs.id, cs.chip_name, treq.id, treq.category, treq.priority, tc.id, tc.title
order by cs.id, treq.id, tc.id
"""


def _mermaid_label(text: str, limit: int = 42) -> str:
    """Make a string safe to sit inside a quoted mermaid node label."""
    flat = " ".join(str(text).split())
    if len(flat) > limit:
        flat = flat[: limit - 1].rstrip() + "…"
    # Quotes terminate the label; mermaid's own entity code is the escape.
    return flat.replace('"', "#quot;")


def _mermaid_traceability(rows: list[dict]) -> str:
    """Requirement -> test case -> outcome chain, as a mermaid flowchart.

    Built directly from query results rather than by an LLM: the rows are
    already structured, so generating the diagram in code is exact and free.
    """
    if not rows:
        return "flowchart LR\n    none[\"No test cases yet\"]"

    lines = ["flowchart LR"]
    seen_chips: set[int] = set()
    seen_reqs: set[int] = set()

    for r in rows:
        chip, req, case = f"C{r['chip_id']}", f"R{r['req_id']}", f"T{r['case_id']}"

        if r["chip_id"] not in seen_chips:
            lines.append(f'    {chip}["{_mermaid_label(r["chip_name"])}"]')
            seen_chips.add(r["chip_id"])

        if r["req_id"] not in seen_reqs:
            label = f'{r["category"]} / {r["priority"]}'
            lines.append(f'    {req}["{_mermaid_label(label)}"]')
            lines.append(f"    {chip} --> {req}")
            seen_reqs.add(r["req_id"])

        passed, failed = r["passed"], r["failed"]
        if failed:
            state, arrow = "fail", f"{failed} failed"
        elif passed:
            state, arrow = "pass", f"{passed} passed"
        else:
            state, arrow = "untested", "not run"

        lines.append(f'    {case}["{_mermaid_label(r["title"])}"]:::{state}')
        lines.append(f'    {req} -->|"{arrow}"| {case}')

    lines += [
        "    classDef pass fill:#d7f0dc,stroke:#2e7d32,color:#12321a",
        "    classDef fail fill:#f8d7da,stroke:#c62828,color:#3a1214",
        "    classDef untested fill:#eceff1,stroke:#90a4ae,color:#263238",
    ]
    return "\n".join(lines)


def generate_report(days: int = 30, output_dir: str = "reports") -> dict:
    runs = execute_validated(
        "select tr.status, tc.title, tr.notes, treq.category "
        "from test_runs tr "
        "join test_cases tc on tc.id = tr.test_case_id "
        "join test_requirements treq on treq.id = tc.requirement_id "
        "where tr.run_at >= now() - interval '%s days'",
        (days,),
    )

    status_counts = Counter(r["status"] for r in runs)
    category_breakdown = Counter((r["category"], r["status"]) for r in runs)
    recent_failures = [(r["title"], r["notes"]) for r in runs if r["status"] == "fail"][:5]

    summary = llm.invoke(
        REPORT_PROMPT.format(
            status_counts=dict(status_counts),
            category_breakdown={f"{k[0]}/{k[1]}": v for k, v in category_breakdown.items()},
            recent_failures=recent_failures,
        )
    ).content

    Path(output_dir).mkdir(exist_ok=True)
    chart_path = Path(output_dir) / "status_breakdown.png"
    _render_chart(status_counts, chart_path)

    traceability = _mermaid_traceability(execute_validated(TRACEABILITY_SQL))

    report_path = Path(output_dir) / "validation_report.md"
    report_path.write_text(
        f"# Validation Report (last {days} days)\n\n"
        f"{summary}\n\n"
        f"![Status breakdown]({chart_path.name})\n\n"
        f"## Requirement traceability\n\n"
        f"```mermaid\n{traceability}\n```\n\n"
        f"## Raw counts\n\n"
        f"{dict(status_counts)}\n"
    )

    return {
        "summary": summary,
        "chart_path": str(chart_path),
        "report_path": str(report_path),
        "mermaid": traceability,
    }


def _render_chart(status_counts: Counter, path: Path) -> None:
    statuses = list(status_counts.keys())
    counts = [status_counts[s] for s in statuses]
    colors = {"pass": "#2e7d32", "fail": "#c62828", "blocked": "#f9a825"}

    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.bar(statuses, counts, color=[colors.get(s, "#999") for s in statuses])
    ax.set_ylabel("Test runs")
    ax.set_title("Validation results by status")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    result = generate_report()
    print(f"Report written to {result['report_path']}")
    print(f"\n{result['summary']}")
