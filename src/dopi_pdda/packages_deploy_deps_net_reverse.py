#!/usr/bin/env python3
"""The direct dependency network table, indexed by dependency
(reverse).

Answers "who depends on this package?" instead of "what does this
package depend on?". Nothing is filtered, nothing is resolved:
every row of the direct table rides along, re-sorted so the
packages that depend on one package read together.

Input is the direct table (--file-in: a Parquet file, a glob, or a
directory of .parquet files; --stream-in reads one JSON row per
line from stdin). Output is --file-out (a Parquet path; a
directory writes one file inside it) or --stream-out (one JSON row
per line on stdout; or a NATS subject with --nats-url/
--nats-subject).

Usage::

    debian-observer-packages-deploy-deps-net-reverse \
        --file-in data/derived/deps_net_direct.parquet \
        --file-out data/derived/deps_net_reverse.parquet
"""

from __future__ import annotations

from pathlib import Path

import click

from dopi_pdda.dependencies import (
    build_reverse_table,
    write_reverse_table,
)
from debian_observer.prosumers.stream import (
    NatsSink,
    Record,
    StreamSink,
)


@click.command()
@click.option(
    "--file-in",
    "file_in",
    type=click.Path(path_type=Path, exists=True),
    default=None,
    help="The direct table: a Parquet file, a glob, or a directory.",
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
    help="Read the direct table as one JSON row per line from stdin.",
)
@click.option(
    "--stream-out",
    "stream_out",
    is_flag=True,
    default=False,
    help="Write one JSON row per line to stdout (or to a NATS subject "
    "with --nats-url and --nats-subject).",
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
    file_in: Path | None,
    file_out: Path | None,
    stream_in: bool,
    stream_out: bool,
    nats_url: str | None,
    nats_subject: str | None,
) -> None:
    """Reindex the direct dependency network table by dependency.

    Answers "who depends on this package?": every row of the
    direct table, re-sorted by the name of the package pointed
    at, so the packages that depend on one package read together.
    """
    if not file_in and not stream_in:
        raise click.UsageError("Must provide --file-in or --stream-in")
    if not file_out and not stream_out:
        raise click.UsageError("Must provide --file-out or --stream-out")

    table = build_reverse_table(file_in)

    if stream_out:
        if nats_url and nats_subject:
            sink = NatsSink(subject=nats_subject, url=nats_url)
        else:
            import sys

            sink = StreamSink(sys.stdout)
        with sink:
            for row in table.to_pylist():
                sink.emit(
                    Record(
                        event_type="DependencyObserved",
                        payload={
                            k: v for k, v in row.items() if k != "event_type"
                        },
                        meta={},
                    )
                )
    else:
        path = write_reverse_table(table, file_out)
        click.echo(
            f"Reverse network written: {path} ({table.num_rows} rows)",
            err=True,
        )


if __name__ == "__main__":
    main()