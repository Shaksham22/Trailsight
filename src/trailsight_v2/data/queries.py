"""Stable WP01 query surfaces for downstream detector preparation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb


DETECTOR_EDGE_DAY_SQL = """
SELECT edge_day, account_ref_a, account_ref_b
FROM detector_edge_day_deltas
ORDER BY edge_day, account_ref_a, account_ref_b
""".strip()


def fetch_detector_edge_day_deltas(
    connection: "duckdb.DuckDBPyConnection",
) -> list[tuple[object, str, str]]:
    """Return canonical first-observed undirected relationships in deterministic order."""
    return connection.execute(DETECTOR_EDGE_DAY_SQL).fetchall()
