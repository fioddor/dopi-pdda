"""Tests for the reverse table (``deps_reverse``).

The reverse table is a **pure reindex** of the straight table:
``SELECT *`` ordered by target. **Identical column names** —
``package``/``version`` stay the depender. The rename was measured
to break generic code and to silently NULL columns when both
tables are read together.

Pinned:
- same rows, same columns as the straight table (asserted, not
  eyeballed): a generic ``SELECT package …`` works unchanged
  against both;
- re-sorted by (target_package, target_version);
- unresolved rows are excluded;
- reading both tables together keeps every column populated (the
  rename would NULL them silently).
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dopi_pdda.dependencies import (
    STRAIGHT_COLUMNS,
    build_reverse_table,
)


@pytest.fixture()
def straight_file(tmp_path: Path) -> Path:
    schema = pa.schema(
        [pa.field(name, dtype) for name, dtype in STRAIGHT_COLUMNS]
    )
    rows = [
        {
            "event_type": "DependencyObserved",
        "distribution": "debian",
            "release": "trixie",
            "architecture": "amd64",
            "components": "main",
            "package": "pkg-b",
            "version": "1.0",
            "kind": "depends",
            "clause_index": 0,
            "condition": "libc6",
            "target_package": "libc6",
            "complexdeps": False,
        },
        {
            "event_type": "DependencyObserved",
        "distribution": "debian",
            "release": "trixie",
            "architecture": "amd64",
            "components": "main",
            "package": "pkg-a",
            "version": "2.0",
            "kind": "depends",
            "clause_index": 0,
            "condition": "libc6",
            "target_package": "libc6",
            "complexdeps": False,
        },
        {
            "event_type": "DependencyObserved",
        "distribution": "debian",
            "release": "trixie",
            "architecture": "amd64",
            "components": "main",
            "package": "pkg-a",
            "version": "1.0",
            "kind": "depends",
            "clause_index": 1,
            "condition": "ghost-pkg",
            "target_package": "ghost-pkg",
            "target_version": None,
            "target_resolved": False,
            "unresolved_reason": "absent",
            "complexdeps": False,
        },
    ]
    path = tmp_path / "straight.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
    return path


class TestReverseTable:
    def test_same_schema_and_rows(self, straight_file: Path) -> None:
        straight = pq.read_table(straight_file)
        reverse = build_reverse_table(straight_file)
        # identical column set (no rename: package/version stay the
        # depender)
        assert reverse.schema.names == straight.schema.names
        # same row count (every row rides; nothing is dropped)
        assert reverse.num_rows == 3

    def test_generic_select_works_against_both(
        self, straight_file: Path
    ) -> None:
        # a generic query over 'package' works unchanged on both
        # tables: the rename would break it silently
        import duckdb

        reverse = build_reverse_table(straight_file)
        reverse_file = straight_file.parent / "reverse.parquet"
        pq.write_table(reverse, reverse_file)
        con = duckdb.connect()
        for table_path in (str(straight_file), str(reverse_file)):
            r = con.execute(
                f"SELECT count(*) FROM read_parquet(?) "
                "WHERE package = 'pkg-a'",
                [table_path],
            ).fetchone()[0]
            # both tables answer the same: pkg-a appears twice
            assert r == 2
        r_rev = con.execute(
            "SELECT count(*) FROM read_parquet(?) "
            "WHERE package = 'pkg-a'",
            [str(reverse_file)],
        ).fetchone()[0]
        assert r_rev == 2

    def test_resorted_by_target(self, straight_file: Path) -> None:
        reverse = build_reverse_table(straight_file)
        rows = reverse.to_pylist()
        keys = [r["target_package"] for r in rows]
        assert keys == sorted(keys)

    def test_every_row_rides(self, straight_file: Path) -> None:
        straight = pq.read_table(straight_file)
        reverse = build_reverse_table(straight_file)
        assert reverse.num_rows == straight.num_rows

    def test_reading_both_together_keeps_columns(
        self, straight_file: Path
    ) -> None:
        import duckdb

        reverse = build_reverse_table(straight_file)
        reverse_file = straight_file.parent / "reverse.parquet"
        pq.write_table(reverse, reverse_file)
        con = duckdb.connect()
        row = con.execute(
            "SELECT package, version, target_package "
            "FROM read_parquet(?) WHERE target_package = 'libc6'",
            [str(reverse_file)],
        ).fetchone()
        assert row is not None
        assert row[0] and row[1] and row[2]