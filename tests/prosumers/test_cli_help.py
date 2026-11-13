"""Tests for the direct/reverse CLIs' help text."""

from __future__ import annotations

import subprocess
import sys

import pytest

DIRECT = "dopi_pdda.packages_deploy_deps_net_direct"
REVERSE = "dopi_pdda.packages_deploy_deps_net_reverse"


def _help(module: str) -> str:
    return subprocess.run(
        [sys.executable, "-m", module, "--help"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

def _test_module_docstring_names_the_inputs(module: str) -> None:
    """Docstrings mention the standard input/output parameters

    The help must tell the user how to use --stream-in (stdin ND-JSON or
    NATS subject with --nats-url/--nats-subject)
    """
    import importlib

    mod = importlib.import_module(module)
    doc = mod.__doc__ or ""
    assert "--stream-in" in doc
    assert "--file-in" in doc
    assert "--nats-url" in doc
    assert "--nats-subject" in doc

def _test_help_documents_the_coordinate_selectors(module: str) -> None:
    """Docstrings mention the standard coordinate parameters"""
    out = _help(module)
    for flag in (
        "--distribution",
        "--release",
        "--architecture",
        "--components",
    ):
        assert flag in out

class TestStandards:
    def test_help(self) -> None:

        _test_module_docstring_names_the_inputs(DIRECT)
        _test_help_documents_the_coordinate_selectors(DIRECT)

        _test_module_docstring_names_the_inputs(REVERSE)


def _test_direct_help_names_the_event_lake(module: str) -> None:
    """The direct CLI names the dependency event lake it reads.

    Ported from the platform (where the deps-net CLIs lived
    until the dismantle): the docstring must name the
    dependency event lake the platform normalize writes
    (data/events/dependency_observed, one directory per event
    type) and the rendered --help must document the --file-in
    that reads it.
    """
    import importlib

    doc = importlib.import_module(module).__doc__ or ""
    assert "data/events/dependency_observed" in doc
    assert "--file-in" in _help(module)


def _test_reverse_help_names_the_direct_table(module: str) -> None:
    """The reverse CLI names the direct table it re-indexes.

    The reverse reads P1 (the direct table), not the lake; its
    docstring names that input and the rendered --help
    documents the --file-in that reads it.
    """
    import importlib

    doc = importlib.import_module(module).__doc__ or ""
    assert "data/derived/deps_net_direct.parquet" in doc
    assert "--file-in" in _help(module)


class TestEventLakeNaming:
    def test_direct_help_names_the_lake(self) -> None:
        _test_direct_help_names_the_event_lake(DIRECT)

    def test_reverse_help_names_the_direct_table(self) -> None:
        _test_reverse_help_names_the_direct_table(REVERSE)
