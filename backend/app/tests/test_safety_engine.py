"""Attacks the Safety Engine to prove it defends.

Run from backend/:  python -m pytest app/tests/test_safety_engine.py -v
(or just run this file:  python app/tests/test_safety_engine.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # make 'app' importable

from app.services.safety_engine import SafetyError, validate

COLS = {"order_date", "region", "product", "revenue", "units_sold", "cost"}
TABLE = "sales"


def v(sql: str) -> str:
    return validate(sql, TABLE, COLS, row_limit=5000)


# ---- queries that SHOULD pass ----
GOOD = [
    "SELECT region, SUM(revenue) AS total FROM sales GROUP BY region",
    "SELECT * FROM sales WHERE region = 'North'",
    "SELECT product, AVG(units_sold) FROM sales GROUP BY product ORDER BY 2 DESC",
    "WITH t AS (SELECT region, revenue FROM sales) SELECT region, SUM(revenue) FROM t GROUP BY region",
]

# ---- attacks that MUST be blocked ----
BAD = [
    ("drop table",          "DROP TABLE sales"),
    ("delete rows",         "DELETE FROM sales"),
    ("update rows",         "UPDATE sales SET revenue = 0"),
    ("insert rows",         "INSERT INTO sales VALUES (1)"),
    ("stacked query",       "SELECT * FROM sales; DROP TABLE sales"),
    ("cross-table (users)", "SELECT * FROM users"),
    ("hallucinated column", "SELECT secret_salary FROM sales"),
    ("alter table",         "ALTER TABLE sales ADD COLUMN x int"),
    ("truncate",            "TRUNCATE sales"),
    ("garbage",             "this is not sql at all !!!"),
]


def run():
    passed = failed = 0

    print("\n--- Queries that SHOULD pass ---")
    for sql in GOOD:
        try:
            out = v(sql)
            assert "LIMIT" in out.upper(), "expected a LIMIT to be injected"
            print(f"  [OK]      {sql[:55]}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL]    {sql[:55]}  -> wrongly blocked: {e}")
            failed += 1

    print("\n--- Attacks that MUST be blocked ---")
    for label, sql in BAD:
        try:
            v(sql)
            print(f"  [FAIL]    {label}: NOT blocked! -> {sql}")
            failed += 1
        except SafetyError:
            print(f"  [BLOCKED] {label}")
            passed += 1
        except Exception as e:
            # parse errors on garbage also count as blocked
            print(f"  [BLOCKED] {label}  ({type(e).__name__})")
            passed += 1

    print(f"\nRESULT: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
