"""Tests for the straight table (``prosumers/dependencies.py``).

The straight table turns the ``DependencyObserved`` lake into the
direct dependency network, **indexed by depender** — one row per
observed clause, **as observed**. The tables do not resolve: no
version evaluation, no picked target version. They carry the
depender, the clause verbatim and the target name the clause
names (its first alternative, flagged ``complexdeps``).

Pinned:
- one row per clause, target = the first alternative\'s name;
- a complex clause contributes its FIRST alternative with
  ``complexdeps = True`` and no other alternative;
- the coordinate travels in the columns;
- the table reads back sorted by (package, version).
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from debian_observer.prosumers.coordinates import CoordinateFilter
from dopi_pdda.dependencies import (
    build_straight_table,
    parse_relationship_field,
)


def _event(
    package: str,
    version: str,
    arch: str,
    release: str,
    condition: str,
    kind: str = "depends",
    clause_index: int = 0,
    component: str = "main",
) -> dict:
    return {
        "event_type": "DependencyObserved",
        "distribution": "debian",
        "release": release,
        "architecture": arch,
        "component": component,
        "package": package,
        "version": version,
        "kind": kind,
        "clause_index": clause_index,
        "condition": condition,
        "is_complex": "|" in condition,
        "alternatives": len([a for a in condition.split("|") if a.strip()]),
    }


@pytest.fixture()
def lake(tmp_path: Path) -> Path:
    events = [
        _event("pkg-a", "1.0", "amd64", "trixie", "libc6 (>= 2.0)"),
        _event("pkg-b", "1.0", "amd64", "trixie", "doc-common"),
        _event(
            "pkg-c",
            "1.0",
            "amd64",
            "trixie",
            "libc6 | nonreal-pkg",
        ),
        _event("pkg-d", "1.0", "amd64", "trixie", "nonexistent-pkg"),
        # outside the coordinate: stays out
        _event("pkg-e", "1.0", "arm64", "trixie", "libc6"),
        _event("pkg-f", "1.0", "amd64", "bookworm", "libc6"),
    ]
    schema = pa.schema(
        [
            ("event_type", pa.string()),
            ("distribution", pa.string()),
            ("release", pa.string()),
            ("architecture", pa.string()),
            ("component", pa.string()),
            ("package", pa.string()),
            ("version", pa.string()),
            ("kind", pa.string()),
            ("clause_index", pa.int64()),
            ("condition", pa.string()),
            ("is_complex", pa.bool_()),
            ("alternatives", pa.int64()),
        ]
    )
    lake = tmp_path / "lake"
    lake.mkdir()
    pq.write_table(
        pa.Table.from_pylist(events, schema=schema),
        lake / "run-001.parquet",
    )
    return lake


COORD = CoordinateFilter(
    distribution="debian",
    release="trixie",
    architecture="amd64",
    components="main",
)


class TestParseRelationshipField:
    def test_simple(self) -> None:
        clauses = parse_relationship_field("libc6 (>= 2.36)")
        assert len(clauses) == 1
        assert clauses[0].condition == "libc6 (>= 2.36)"

    def test_two_clauses(self) -> None:
        clauses = parse_relationship_field("libc6 (>= 2.36), libc-bin")
        assert len(clauses) == 2

    def test_null_and_empty(self) -> None:
        assert parse_relationship_field(None) == []
        assert parse_relationship_field("") == []


class TestBuildStraightTable:
    def test_one_row_per_clause_target_is_first_alternative_name(
        self, lake: Path
    ) -> None:
        table = build_straight_table(lake, COORD)
        rows = table.to_pylist()
        # 4 events of the coordinate (arm64 and bookworm stay out)
        assert len(rows) == 4
        a = [r for r in rows if r["package"] == "pkg-a"][0]
        assert a["target_package"] == "libc6"
        # no resolution columns at all
        assert not any(
            c in table.schema.names
            for c in ("target_version", "target_resolved",
                      "unresolved_reason")
        )

    def test_complex_clause_takes_the_first_alternative(
        self, lake: Path
    ) -> None:
        table = build_straight_table(lake, COORD)
        rows = table.to_pylist()
        c_rows = [r for r in rows if r["package"] == "pkg-c"]
        assert len(c_rows) == 1
        assert c_rows[0]["complexdeps"] is True
        assert c_rows[0]["target_package"] == "libc6"

    def test_unresolvable_target_keeps_its_row_as_observed(
        self, lake: Path
    ) -> None:
        # the tables do not resolve: an absent target is still a row
        table = build_straight_table(lake, COORD)
        rows = table.to_pylist()
        d = [r for r in rows if r["package"] == "pkg-d"][0]
        assert d["target_package"] == "nonexistent-pkg"
        assert "target_version" not in d

    def test_coordinate_travels_in_columns(self, lake: Path) -> None:
        table = build_straight_table(lake, COORD)
        for row in table.to_pylist():
            assert row["distribution"] == "debian"
            assert row["release"] == "trixie"
            assert row["architecture"] == "amd64"
            assert row["components"] == "main"

    def test_no_filters_selects_everything(self, lake: Path) -> None:
        table = build_straight_table(lake)
        assert table.num_rows == 6

    def test_sorted_by_depender(self, lake: Path) -> None:
        table = build_straight_table(lake, COORD)
        keys = [(r["package"], r["version"]) for r in table.to_pylist()]
        assert keys == sorted(keys)
