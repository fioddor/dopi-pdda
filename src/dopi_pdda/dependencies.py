"""Prosumers: the straight dependency table.

Turns the ``DependencyObserved`` lake into the direct dependency
network **indexed by depender** (what does X need?): one row per
clause, **as observed**. The tables do not resolve: they carry
the depender, the clause verbatim and the target name the clause
names (its first alternative) — which version satisfies the
clause is a downstream, coordinate-dependent question.

Complex clauses (alternatives) are simplified to their FIRST
alternative and flagged ``complexdeps`` — a documented
simplification of the *direct* tables; the OR structure stays in
the lake (and in the complex/cycles views that unfold it).

The coordinate (distribution, release, architecture, components)
travels in the **columns**: every derived file is self-describing,
no path parsing, no Hive partitioning (ADR-016).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from debian_observer.prosumers.coordinates import CoordinateFilter
from debian_observer.prosumers.lake import fold_lake, read_lake_batches

#: Columns of the straight (and reverse) table. The coordinate and
#: the components list travel in the columns (ADR-016).
STRAIGHT_COLUMNS: tuple[tuple[str, Any], ...] = (
    ("distribution", pa.string()),
    ("release", pa.string()),
    ("architecture", pa.string()),
    ("components", pa.string()),
    ("package", pa.string()),
    ("version", pa.string()),
    ("kind", pa.string()),
    ("clause_index", pa.int64()),
    ("condition", pa.string()),
    ("target_package", pa.string()),
    ("complexdeps", pa.bool_()),
)

_STRAIGHT_SCHEMA = pa.schema(
    [pa.field(name, dtype) for name, dtype in STRAIGHT_COLUMNS]
)

#: A clause: ``name[:arch] [(op version)]``. Whitespace inside the
#: parentheses optional (Policy §7.1).
_ALT_RE = re.compile(
    r"^\s*(?P<name>[a-z0-9][a-z0-9+.-]*)"
    r"(:(?P<archqual>[a-z0-9-]+))?\s*"
    r"(\(\s*(?P<op><<|<=|=|>=|>>)\s*"
    r"(?P<version>[^)\s]+)\s*\))?\s*$"
)


@dataclass(frozen=True)
class Clause:
    """One clause of a relationship field, as observed."""

    condition: str
    clause_index: int

    @property
    def alternatives(self) -> list[str]:
        return [a.strip() for a in self.condition.split("|") if a.strip()]

    @property
    def is_complex(self) -> bool:
        return "|" in self.condition

    def first_alternative(self) -> dict[str, str | None]:
        """Parse the FIRST alternative into its parts."""
        alt = self.alternatives[0] if self.alternatives else self.condition
        match = _ALT_RE.match(alt.strip())
        if match is None:
            return {"name": None, "op": None, "version": None}
        return {
            "name": match.group("name"),
            "op": match.group("op"),
            "version": match.group("version"),
        }


def parse_relationship_field(
    field: str | None,
) -> list[Clause]:
    """Split a relationship field into clauses (Policy §7.1).

    A field is a comma-separated list of clauses; the clause text
    stays verbatim inside its clause. ``None``/empty → no clauses.
    """
    if not field or not str(field).strip():
        return []
    return [
        Clause(condition=part.strip(), clause_index=i)
        for i, part in enumerate(str(field).split(","))
        if part.strip()
    ]





def build_straight_table(
    lake: Path | str,
    coordinate: CoordinateFilter | None = None,
) -> pa.Table:
    """Build the straight table of one coordinate.

    One row per observed clause: the depender, the clause verbatim
    and the target name the clause names (its first alternative,
    flagged ``complexdeps``). No resolution — the tables observe;
    which version satisfies a clause is downstream.
    Sorted by (package, version).
    """
    coordinate = coordinate or CoordinateFilter()
    rows: list[dict[str, Any]] = []

    from debian_observer.prosumers.lake import lake_files

    seen_dependency = False

    def step(acc, ev):
        nonlocal seen_dependency
        event_type = str(ev.get("event_type") or "")
        if event_type and event_type != "DependencyObserved":
            # The table reads the DEPENDENCY lake; a lake of other
            # events has no clauses and would build rows of all-None
            # columns — refuse it instead of passing silently.
            raise ValueError(
                f"not a dependency lake: found {event_type} events "
                f"(this table reads the DependencyObserved lake)"
            )
        if event_type == "DependencyObserved":
            seen_dependency = True
        if not coordinate.selects(ev):
            return acc
        clause = Clause(
            condition=ev.get("condition") or "",
            clause_index=int(ev.get("clause_index") or 0),
        )
        alt = clause.first_alternative()
        acc.append(
            {
                "distribution": ev.get("distribution"),
                "release": ev.get("release"),
                "architecture": coordinate.architecture or ev.get(
                    "architecture"
                ),
                "components": (
                    # The coordinate the run asked for when the
                    # filter says one; the observation's own
                    # component when it does not (a column of None
                    # would poison every join and group-by
                    # downstream — the filter's absence is not the
                    # observation's absence).
                    coordinate.components
                    if coordinate.components is not None
                    else ev.get("component")
                ),
                "package": ev.get("package"),
                "version": ev.get("version"),
                "kind": ev.get("kind"),
                "clause_index": ev.get("clause_index"),
                "condition": ev.get("condition"),
                "target_package": alt["name"],
                "complexdeps": clause.is_complex,
            }
        )
        return acc

    files = lake_files(lake)
    if not files:
        raise ValueError(
            f"not a dependency lake: no .parquet files under {lake}"
        )
    rows = fold_lake(lake, initial=rows, step=step)
    if not seen_dependency:
        raise ValueError(
            "not a dependency lake: no DependencyObserved events "
            f"under {lake} (found no event_type column)"
        )
    rows.sort(key=lambda r: (r["package"] or "", r["version"] or ""))
    return pa.Table.from_pylist(rows, schema=_STRAIGHT_SCHEMA)





def build_reverse_table(straight: Path | str) -> "pa.Table":
    """Reindex the straight table by target (a pure reindex).

    ``SELECT *`` ordered by target_package, **column names
    identical** —
    ``package``/``version`` stay the depender (a rename would
    break generic queries and silently NULL columns when both
    tables are read together). Row-group min/max statistics give
    the target pruning a sorted table buys.
    """
    from debian_observer.prosumers.lake import lake_files

    files = lake_files(straight)
    import duckdb

    con = duckdb.connect()
    paths = [str(f) for f in files]
    rows = con.execute(
        "SELECT * FROM read_parquet(?)"
        " ORDER BY target_package",
        [paths],
    ).fetchall()
    columns = [c[0] for c in con.description]
    con.close()
    data = [dict(zip(columns, r)) for r in rows]
    return pa.Table.from_pylist(data, schema=_STRAIGHT_SCHEMA)


def write_reverse_table(table: "pa.Table", file_out: Path) -> Path:
    """Write one reverse-table Parquet file (atomic replace)."""
    file_out = Path(file_out)
    file_out.parent.mkdir(parents=True, exist_ok=True)
    tmp = file_out.with_suffix(".parquet.tmp")
    pq.write_table(table, tmp)
    tmp.replace(file_out)
    return file_out


def write_straight_table(
    table: pa.Table, file_out: Path
) -> Path:
    """Write one straight-table Parquet file (atomic replace)."""
    file_out = Path(file_out)
    file_out.parent.mkdir(parents=True, exist_ok=True)
    tmp = file_out.with_suffix(".parquet.tmp")
    pq.write_table(table, tmp)
    tmp.replace(file_out)
    return file_out
