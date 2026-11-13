#!/usr/bin/env python3
"""The direct dependency network table, indexed by depender.

One row per dependency clause read: the package that depends,
its version, the clause as written, and the name the clause
points at. Nothing is decided here.

Input is the dependency events of a normalize run: --file-in
(a Parquet file, a glob, or a directory of .parquet files) or
--stream-in (one JSON event per line from stdin; or a NATS
subject with --nats-url/--nats-subject). Output is --file-out
(a Parquet path; a directory writes one file inside it) or
--stream-out (one JSON row per line to stdout; or a NATS
subject).

Which part of the archive the table describes is your choice:
the coordinate selectors --distribution, --release,
--architecture and --components are ALL OPTIONAL - one that
is not given does not filter, and none given means the table
describes everything read. --components is a '+'-separated
list (e.g. main+non-free-firmware) and applies to the
depending package's own component.

Usage::

    debian-observer-packages-deploy-deps-net-direct \\
        --file-in data/events/dependency_observed \\
        --file-out data/derived/deps_net_direct.parquet \\
        --release trixie --architecture amd64
"""

from __future__ import annotations

from pathlib import Path

import click

from debian_observer.prosumers.cli import build_sink, build_source, common_io_options
from debian_observer.prosumers.coordinates import CoordinateFilter
from dopi_pdda.dependencies import build_straight_table


@click.command()
@click.option(
    "--file-in",
    "file_in",
    type=click.Path(path_type=Path, exists=True),
    multiple=True,
    help="Input Parquet paths (repeatable; file, glob or directory).",
)
@click.option(
    "--file-out",
    "file_out",
    type=click.Path(path_type=Path),
    default=None,
    help="Output Parquet file path (or directory).",
)
@click.option(
    "--stream-in",
    "stream_in",
    is_flag=True,
    default=False,
    help="Read one JSON event per line from stdin (the dependency "
    "events of a normalize run).",
)
@click.option(
    "--stream-out",
    "stream_out",
    is_flag=True,
    default=False,
    help="Write one JSON row per line to stdout (or to a NATS "
    "subject with --nats-url and --nats-subject).",
)
@click.option("--distribution", default=None, help="Distribution family (e.g. debian). Optional.")
@click.option("--release", default=None, help="Release/pocket (e.g. trixie). Optional.")
@click.option(
    "--architecture",
    default=None,
    help="Architecture (e.g. amd64); 'all' rows ride along. Optional.",
)
@click.option(
    "--components",
    "components",
    default=None,
    help="The coordinate's component list, '+'-separated (e.g. main+non-free-firmware). Optional.",
)
@click.option(
    "--nats-url",
    default=None,
    help="NATS server URL for --stream-in/--stream-out.",
)
@click.option(
    "--nats-subject",
    default=None,
    help="NATS subject for --stream-in/--stream-out.",
)
def main(
    file_in: tuple[Path, ...],
    file_out: Path | None,
    stream_in: bool,
    stream_out: bool,
    distribution: str | None,
    release: str | None,
    architecture: str | None,
    components: str | None,
    nats_url: str | None,
    nats_subject: str | None,
) -> None:
    """Build the direct dependency network table.

    One row per dependency clause read: the package that depends,
    its version, the clause as written, and the name the clause
    points at. Nothing is decided here.

    Which part of the archive the table describes is your choice:
    every coordinate selector (--distribution, --release,
    --architecture, --components) is optional - give none and the
    table describes everything read.
    """
    if not file_in and not stream_in:
        raise click.UsageError("Must provide --file-in or --stream-in")
    if not file_out and not stream_out:
        raise click.UsageError("Must provide --file-out or --stream-out")

    ins = list(file_in)
    if stream_in:
        if ins:
            raise click.UsageError(
                "--stream-in takes no --file-in companions (one stream)"
            )
        raise click.UsageError(
            "--stream-in reads one event stream; the direct table "
            "reads the dependency lake (--file-in)"
        )
    if not ins:
        raise click.UsageError(
            "--file-in: the dependency lake (file, glob or directory)"
        )
    lake = ins[0]

    coordinate = CoordinateFilter.from_args(
        distribution=distribution,
        release=release,
        architecture=architecture,
        components=components,
    )
    table = build_straight_table(lake, coordinate)
    import pyarrow.parquet as pq

    if stream_out:
        import json
        import sys

        from debian_observer.prosumers.stream import Record

        for row in table.to_pylist():
                if nats_url and nats_subject:
                    from debian_observer.prosumers.stream import NatsSink

                    sink = NatsSink(subject=nats_subject, url=nats_url)
                    with sink:
                        sink.emit(
                            Record(
                                event_type="DependencyObserved",
                                payload=row,
                                meta={},
                            )
                        )
                else:
                    sys.stdout.write(json.dumps(row, default=str) + "\n")
    else:
        # build_straight_table returns the table; write it out the
        # platform way (parents created, atomic replace).
        out = Path(file_out)
        if out.is_dir():
            out = out / "deps_net_direct.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".parquet.tmp")
        pq.write_table(table, tmp)
        tmp.replace(out)

        n_rows = pq.read_metadata(out).num_rows
        click.echo(
            f"Direct network written: {out} ({n_rows} rows)", err=True
        )


if __name__ == "__main__":
    main()