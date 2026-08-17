"""Self-check for the demo spend guards. Run: python test_limits.py
No network, no DB. This is the code standing between a public URL and a bill,
so it gets a test.
"""
import limits


def demo():
    limits.reset()
    original = (limits.PER_IP_LIMIT, limits.GLOBAL_DAILY_LIMIT)
    limits.PER_IP_LIMIT, limits.GLOBAL_DAILY_LIMIT = 3, 5

    try:
        # a single IP is cut off at its own limit
        for _ in range(3):
            limits.check_and_consume("1.1.1.1")
        try:
            limits.check_and_consume("1.1.1.1")
            raise AssertionError("per-IP limit did not trigger")
        except limits.RateLimited:
            pass

        # a different visitor is unaffected by the first one's usage
        limits.check_and_consume("2.2.2.2")

        # ...until the global daily budget is gone, which stops everyone
        limits.check_and_consume("3.3.3.3")
        try:
            limits.check_and_consume("4.4.4.4")
            raise AssertionError("global limit did not trigger")
        except limits.RateLimited as exc:
            assert "daily budget" in str(exc), "global refusal should say why"

        u = limits.usage()
        assert u["global_used"] == 5 and u["global_limit"] == 5

        # the window slides: ageing every timestamp out frees the budget again
        limits.reset()
        limits.check_and_consume("1.1.1.1")
        for bucket in (limits._by_ip["1.1.1.1"], limits._global):
            bucket[0] -= limits.PER_IP_WINDOW_S + 1
        limits.check_and_consume("1.1.1.1")
        assert len(limits._by_ip["1.1.1.1"]) == 1, "expired entry was not pruned"

        print("All rate-limit checks passed.")
    finally:
        limits.PER_IP_LIMIT, limits.GLOBAL_DAILY_LIMIT = original
        limits.reset()


if __name__ == "__main__":
    demo()
