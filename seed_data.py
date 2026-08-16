"""Creates the schema and seeds synthetic chip specs and test requirements.

Safe to run more than once: schema.sql uses CREATE TABLE IF NOT EXISTS, and
seeding is skipped when chip_specs already has rows.
"""
from pathlib import Path

from db import execute_validated, get_connection

CHIPS = [
    ("EdgeCortex-9", "edge-ai", "BGA-256"),
    ("AutoSense-4", "automotive", "QFN-48"),
    ("IndustrialMCU-2", "industrial", "LQFP-100"),
]

REQUIREMENTS = [
    # (chip_name, requirement_text, category, priority)
    ("EdgeCortex-9", "Chip must maintain inference throughput within 5% of spec across -40C to 125C.", "thermal", "high"),
    ("EdgeCortex-9", "Power draw during NPU-active inference must not exceed 2.1W.", "electrical", "critical"),
    ("EdgeCortex-9", "MCP tool-call round-trip latency over the on-chip interconnect must stay under 3ms.", "timing", "medium"),
    ("AutoSense-4", "Chip must pass ISO 26262 ASIL-B fault injection for the sensor-fusion pipeline.", "electrical", "critical"),
    ("AutoSense-4", "CAN bus wake-up latency must not exceed 100us under cold-start conditions.", "timing", "high"),
    ("IndustrialMCU-2", "Chip must withstand 2kV ESD per IEC 61000-4-2 on all GPIO pins.", "emc", "high"),
    ("IndustrialMCU-2", "Flash write endurance must exceed 100k cycles at rated temperature.", "electrical", "medium"),
]


def create_schema():
    """DDL, so it needs a raw connection -- execute_validated allows only SELECT/INSERT."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(Path(__file__).parent.joinpath("schema.sql").read_text())
            conn.commit()
    finally:
        conn.close()
    print("schema applied")


def seed():
    if execute_validated("select count(*) as n from chip_specs")[0]["n"]:
        print("chip_specs already populated -- skipping seed")
        return

    chip_ids = {}
    for name, market, package in CHIPS:
        rows = execute_validated(
            "insert into chip_specs (chip_name, target_market, package_type) "
            "values (%s, %s, %s) returning id",
            (name, market, package),
        )
        chip_ids[name] = rows[0]["id"]
        print(f"chip_specs: {name} -> id {rows[0]['id']}")

    for chip_name, text, category, priority in REQUIREMENTS:
        rows = execute_validated(
            "insert into test_requirements (chip_id, requirement_text, category, priority) "
            "values (%s, %s, %s, %s) returning id",
            (chip_ids[chip_name], text, category, priority),
        )
        print(f"test_requirements: [{category}] {text[:50]}... -> id {rows[0]['id']}")


if __name__ == "__main__":
    create_schema()
    seed()
