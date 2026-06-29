"""Query Safety Engine.

Sits between "the LLM wrote some SQL" and "we run it on the database".
NOTHING reaches the database without passing through validate().

Approach: parse the SQL into an Abstract Syntax Tree (AST) with sqlglot and
ALLOWLIST a single SELECT against this dataset's own columns. We reason about
what the query *does* structurally, not how it's spelled -- regex filtering is
bypassable; AST validation is not.
"""
import sqlglot
from sqlglot import exp

# Statement node types that are never allowed (write/DDL/admin operations).
FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create,
    exp.Command, exp.TruncateTable, exp.Grant, exp.Merge,
)


class SafetyError(Exception):
    """Raised when SQL fails validation. The router turns this into a 400."""


def validate(sql: str, allowed_table: str, allowed_columns: set[str], row_limit: int) -> str:
    """Validate LLM-generated SQL and return a safe, LIMIT-bounded SQL string.

    Raises SafetyError on anything that isn't a single, read-only SELECT that
    touches only this dataset's table and columns.
    """
    # 1) Must parse. Garbage in -> reject (don't guess what it meant).
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except Exception as e:
        raise SafetyError(f"Could not parse SQL: {e}")

    # 2) Exactly ONE statement. Blocks stacked-query injection:
    #    "SELECT * FROM sales; DROP TABLE users" is two statements -> rejected.
    if len(statements) != 1:
        raise SafetyError("Only a single statement is allowed.")
    tree = statements[0]

    # 3) The single statement must be a SELECT (allowlist, not blocklist).
    #    WITH ... SELECT (CTEs) are fine as long as the body is a SELECT.
    root = tree
    if isinstance(root, exp.With):
        root = root.this
    if not isinstance(root, (exp.Select, exp.Union, exp.Subquery)):
        raise SafetyError("Only SELECT queries are allowed.")

    # 4) Walk the ENTIRE tree (incl. subqueries/CTEs). Any forbidden op -> reject.
    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise SafetyError(f"Operation not allowed: {type(node).__name__}.")

    # 5) Every referenced table must be THIS dataset's table (no users table, etc.).
    #    CTE names (WITH t AS ...) are query-local aliases, so they're allowed too.
    cte_names = {c.alias for c in tree.find_all(exp.CTE) if c.alias}
    allowed_tables = {allowed_table} | cte_names
    for table in tree.find_all(exp.Table):
        if table.name and table.name not in allowed_tables:
            raise SafetyError(f"Table '{table.name}' is not allowed.")

    # 6) Every referenced column must exist in this dataset (blocks hallucinated cols).
    #    Skip when CTEs are present: tables are already locked to this dataset, and a
    #    CTE can rename/compute columns, so a strict name match would wrongly reject.
    if allowed_columns and not cte_names:
        alias_names = {a.alias for a in tree.find_all(exp.Alias) if a.alias}
        for col in tree.find_all(exp.Column):
            if col.name and col.name != "*" and col.name not in allowed_columns and col.name not in alias_names:
                raise SafetyError(f"Unknown column '{col.name}'.")

    # 7) Enforce a LIMIT so a valid query can't pull millions of rows.
    select_node = tree.find(exp.Select)
    if select_node is not None:
        existing = select_node.args.get("limit")
        if existing is None:
            select_node.limit(row_limit, copy=False)
        else:
            try:
                if int(existing.expression.name) > row_limit:
                    select_node.limit(row_limit, copy=False)
            except (AttributeError, ValueError):
                select_node.limit(row_limit, copy=False)

    # 8) Re-render from the validated AST -- we run THIS, never the LLM's raw text.
    return tree.sql(dialect="postgres")
