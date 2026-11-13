"""End-to-end tests of the direct/reverse dependency-network CLIs.

The lake is a synthetic Parquet of dependency events; the CLIs run
through click's runner in-process (the same main() the console
scripts invoke). The reverse CLI consumes the direct CLI's output:
the two CLIs compose.
"""

from __future__ import annotations

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from click.testing import CliRunner

from dopi_pdda.packages_deploy_deps_net_direct import main as direct_main
from dopi_pdda.packages_deploy_deps_net_reverse import main as reverse_main


EVENT_SCHEMA = pa.schema(
    [
        ("event_type", pa.string()),
        ("distribution", pa.string()),
        ("release", pa.string()),
        ("architecture", pa.string()),
        ("package", pa.string()),
        ("version", pa.string()),
        ("kind", pa.string()),
        ("clause_index", pa.int64()),
        ("condition", pa.string()),
    ]
)

EVENTS = [
    # two clauses of app-alpha, one complex (alternatives)
    {
        "event_type": "DependencyObserved",
        "distribution": "debian",
        "release": "trixie",
        "architecture": "amd64",
        "package": "app-alpha",
        "version": "1.0-1",
        "kind": "depends",
        "clause_index": 0,
        "condition": "libfoo",
    },
    {
        "event_type": "DependencyObserved",
        "distribution": "debian",
        "release": "trixie",
        "architecture": "amd64",
        "package": "app-alpha",
        "version": "1.0-1",
        "kind": "depends",
        "clause_index": 1,
        "condition": "libbar (>= 2) | libbaz",
    },
    # one clause of app-beta, depending on app-alpha's target
    {
        "event_type": "DependencyObserved",
        "distribution": "debian",
        "release": "trixie",
        "architecture": "amd64",
        "package": "app-beta",
        "version": "2.0-1",
        "kind": "depends",
        "clause_index": 0,
        "condition": "libfoo",
    },
    # another release: filtered out by the coordinate selectors
    {
        "event_type": "DependencyObserved",
        "distribution": "debian",
        "release": "bookworm",
        "architecture": "amd64",
        "package": "app-gamma",
        "version": "3.0-1",
        "kind": "depends",
        "clause_index": 0,
        "condition": "libfoo",
    },
]


@pytest.fixture()
def lake(tmp_path):
    path = tmp_path / "dependency_events"
    path.mkdir()
    pq.write_table(
        pa.Table.from_pylist(EVENTS, schema=EVENT_SCHEMA),
        path / "dependency_observed.parquet",
    )
    return path


def test_direct_writes_one_row_per_clause(lake, tmp_path):
    out = tmp_path / "direct.parquet"
    result = CliRunner().invoke(
        direct_main,
        [
            "--file-in", str(lake),
            "--file-out", str(out),
        ],
    )
    assert result.exit_code == 0, result.output

    table = pq.read_table(out)
    rows = table.to_pylist()
    # one row per clause read, none decided away
    assert len(rows) == 4
    # sorted by (package, version)
    assert [r["package"] for r in rows] == [
        "app-alpha", "app-alpha", "app-beta", "app-gamma",
    ]
    # the clause's first alternative is the target; complex flagged
    alpha = rows[0]
    assert alpha["target_package"] == "libfoo"
    assert alpha["complexdeps"] is False
    complex_row = rows[1]
    assert complex_row["target_package"] == "libbar"
    assert complex_row["complexdeps"] is True


def test_direct_coordinate_selectors_filter(lake, tmp_path):
    out = tmp_path / "direct_trixie.parquet"
    result = CliRunner().invoke(
        direct_main,
        [
            "--file-in", str(lake),
            "--file-out", str(out),
            "--release", "trixie",
        ],
    )
    assert result.exit_code == 0, result.output

    rows = pq.read_table(out).to_pylist()
    assert {r["package"] for r in rows} == {"app-alpha", "app-beta"}


def test_direct_requires_input(tmp_path):
    result = CliRunner().invoke(
        direct_main, ["--file-out", str(tmp_path / "x.parquet")]
    )
    assert result.exit_code != 0
    assert "--file-in" in result.output


def test_reverse_reindexes_by_target(lake, tmp_path):
    direct_out = tmp_path / "direct.parquet"
    assert (
        CliRunner()
        .invoke(
            direct_main,
            ["--file-in", str(lake), "--file-out", str(direct_out)],
        )
        .exit_code
        == 0
    )

    reverse_out = tmp_path / "reverse.parquet"
    result = CliRunner().invoke(
        reverse_main,
        ["--file-in", str(direct_out), "--file-out", str(reverse_out)],
    )
    assert result.exit_code == 0, result.output

    rows = pq.read_table(reverse_out).to_pylist()
    # same clauses, re-sorted by the pointed-at name
    assert len(rows) == 4
    targets = [r["target_package"] for r in rows]
    assert targets == sorted(targets)
    # who depends on libfoo: alpha and beta (bookworm's gamma rides
    # along unless filtered - the reverse CLI has no selectors)
    libfoo_dependers = [
        r["package"] for r in rows if r["target_package"] == "libfoo"
    ]
    assert set(libfoo_dependers) == {"app-alpha", "app-beta", "app-gamma"}


def test_reverse_stream_out_emits_json_rows(lake, tmp_path):
    import io

    direct_out = tmp_path / "direct.parquet"
    assert (
        CliRunner()
        .invoke(
            direct_main,
            ["--file-in", str(lake), "--file-out", str(direct_out)],
        )
        .exit_code
        == 0
    )

    result = CliRunner().invoke(
        reverse_main,
        ["--file-in", str(direct_out), "--stream-out"],
    )
    assert result.exit_code == 0, result.output

    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    records = [json.loads(ln) for ln in lines]
    # the stream envelope: _event_type + _meta + payload flattened
    assert all(r["_event_type"] == "DependencyObserved" for r in records)
    targets = [r["target_package"] for r in records]
    assert len(records) == 4
    assert targets == sorted(targets)


def test_reverse_requires_input(tmp_path):
    result = CliRunner().invoke(
        reverse_main, ["--file-out", str(tmp_path / "y.parquet")]
    )
    assert result.exit_code != 0
    assert "--file-in" in result.output