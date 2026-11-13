"""Regression: the components column carries the OBSERVATION's
component when the coordinate filter does not say one.

build_straight_table wrote the CoordinateFilter's components value
into the components column. A run without --components has None
there, and the whole column came out None — poisoning every join,
filter and group-by downstream (measured: the T5 statistics join
produced zero rows on real data).

Pinned:
- no --components: the column carries the event's component;
- with --components: the column carries the filter's list (the
  coordinate the run asked for);
- component absent from the event: None (the observation did not
  carry one), never an invented value.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from debian_observer.prosumers.coordinates import CoordinateFilter
from dopi_pdda.dependencies import build_straight_table

SCHEMA = pa.schema(
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


def _event(component: str = "main") -> dict:
    return {
        "event_type": "DependencyObserved",
        "distribution": "debian",
        "release": "trixie",
        "architecture": "amd64",
        "component": component,
        "package": "pkg-a",
        "version": "1.0",
        "kind": "depends",
        "clause_index": 0,
        "condition": "libc6 (>= 2.36)",
        "is_complex": False,
        "alternatives": 1,
    }


@pytest.fixture()
def lake(tmp_path: Path) -> Path:
    d = tmp_path / "dependency_observed"
    d.mkdir()
    pq.write_table(pa.Table.from_pylist([_event()], schema=SCHEMA), d / "run-001.parquet")
    return d


class TestComponentsFromObservation:
    def test_no_filter_carries_the_events_component(self, lake: Path) -> None:
        table = build_straight_table(lake)
        row = table.to_pylist()[0]
        assert row["components"] == "main"

    def test_filter_carries_the_filters_list(self, lake: Path) -> None:
        coordinate = CoordinateFilter(
            distribution="debian", release="trixie",
            architecture="amd64", components="main+contrib",
        )
        table = build_straight_table(lake, coordinate)
        row = table.to_pylist()[0]
        assert row["components"] == "main+contrib"

    def test_event_without_component_is_none(self, lake: Path) -> None:
        rows = pa.Table.from_pylist([_event(component=None)], schema=SCHEMA).to_pylist()
        pq.write_table(
            pa.Table.from_pylist(rows, schema=SCHEMA), lake / "run-002.parquet"
        )
        table = build_straight_table(lake)
        values = {str(r["components"]) for r in table.to_pylist()}
        assert values == {"main", "None"}


class TestWrongLakeRejected:
    def test_a_non_dependency_lake_is_refused(self, tmp_path: Path) -> None:
        d = tmp_path / "package_version_observed"
        d.mkdir()
        row = {
            "event_id": "e1", "event_type": "PackageVersionObserved",
            "source": "udddump", "entity_id": "pkg-a:amd64",
            "package_id": "pkg-a:amd64", "source_package": "pkg-a",
            "version": "1.0", "distribution": "debian",
            "release": "trixie", "architecture": "amd64",
            "component": "main", "section": "admin",
            "priority": "optional", "suite": None,
        }
        schema = pa.Table.from_pylist([row]).schema
        pq.write_table(pa.Table.from_pylist([row], schema=schema), d / "run-001.parquet")
        with pytest.raises(ValueError, match="[Dd]ependency"):
            build_straight_table(d)