"""Self-check for the guardrails layer. Run: python test_db_guardrails.py
No DB connection needed -- this only tests the safety-check logic itself.
"""
from db import UnsafeSQLError, is_safe_statement


def demo():
    # allowed
    is_safe_statement("select * from test_runs")
    is_safe_statement("insert into test_cases (title) values ('x')")

    # blocked
    for bad_sql in [
        "drop table test_runs",
        "delete from test_runs",
        "update test_runs set status = 'pass'",
        "select 1; drop table test_runs",
        "truncate test_runs",
    ]:
        try:
            is_safe_statement(bad_sql)
            raise AssertionError(f"should have blocked: {bad_sql}")
        except UnsafeSQLError:
            pass

    print("All guardrail checks passed.")


if __name__ == "__main__":
    demo()
