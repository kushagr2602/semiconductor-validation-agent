"""End-to-end demo: generate a test plan, ask the maintenance agent about it,
seed a couple of fake runs, then generate a report. Run after seed_data.py.
"""
from db import execute_validated
from maintenance_agent import ask
from report_agent import generate_report
from test_plan_agent import generate_test_plan


def main():
    print("1. Generating a test plan for requirement #1...")
    plan = generate_test_plan(1)
    print(f"   -> test_case_id {plan['test_case_id']}: {plan['title']}")

    print("\n2. Recording two fake test runs...")
    # Literal % must be doubled to %% -- psycopg2 reads a single % as the start
    # of a placeholder whenever params are supplied.
    execute_validated(
        "insert into test_runs (test_case_id, status, measured_value, notes) "
        "values (%s, 'pass', '4.8%% deviation', 'within spec')",
        (plan["test_case_id"],),
    )
    execute_validated(
        "insert into test_runs (test_case_id, status, measured_value, notes) "
        "values (%s, 'fail', '7.2%% deviation', 'exceeded 5%% threshold at 125C')",
        (plan["test_case_id"],),
    )
    print("   -> done")

    print("\n3. Asking the maintenance agent a question...")
    result = ask("Which test cases have failing runs, and why?")
    print(f"   SQL: {result['sql']}")
    print(f"   Answer: {result.get('answer')}")

    print("\n4. Generating a report...")
    report = generate_report(days=1)
    print(f"   -> {report['report_path']}")
    print(f"   {report['summary']}")


if __name__ == "__main__":
    main()
