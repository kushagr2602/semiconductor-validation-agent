"""Self-check for mermaid traceability generation. Run: python test_report_diagram.py
No DB or LLM needed -- this only tests the string building.
"""
from report_agent import _mermaid_label, _mermaid_traceability


def row(**kw):
    base = dict(chip_id=1, chip_name="EdgeCortex-9", req_id=1, category="thermal",
                priority="high", case_id=1, title="Thermal check", passed=0, failed=0)
    return {**base, **kw}


def demo():
    # a double quote would terminate the label and corrupt the diagram
    assert '"' not in _mermaid_label('Chip "A" test'), "quote not escaped"

    # long titles get truncated so nodes stay readable
    assert len(_mermaid_label("x" * 200)) <= 42

    # newlines would break mermaid's line-based parser
    assert "\n" not in _mermaid_label("line one\nline two")

    # empty input still returns a parseable diagram, not an empty string
    assert _mermaid_traceability([]).startswith("flowchart LR")

    # a failing run marks the node fail, even alongside passes
    out = _mermaid_traceability([row(passed=3, failed=1)])
    assert ":::fail" in out and ":::pass" not in out

    out = _mermaid_traceability([row(passed=2)])
    assert ":::pass" in out

    out = _mermaid_traceability([row()])
    assert ":::untested" in out

    # two cases under one requirement must not redeclare the chip/req nodes
    out = _mermaid_traceability([row(case_id=1), row(case_id=2)])
    assert out.count('C1["EdgeCortex-9"]') == 1, "chip node declared twice"
    assert out.count("C1 --> R1") == 1, "chip->req edge duplicated"

    print("All diagram checks passed.")


if __name__ == "__main__":
    demo()
