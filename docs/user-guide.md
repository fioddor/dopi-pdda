# User Guide

Quick start and operational guide for DOPI-PDDA
(Debian Observer Plug-In: Packages Deploy-Dependency Analysis).

## Installation

DOPI-PDDA is a plug-in: the Debian Observer platform is a
prerequisite. Install the platform wheel first, then the plug-in.

```shell
pipx install debian_observer-0.1.0-py3-none-any.whl   # the platform
pipx install dopi_pdda-0.1.0-py3-none-any.whl          # the plug-in
```

Or, inside one virtual environment:

```shell
pip install debian_observer-0.1.0-py3-none-any.whl
pip install dopi_pdda-0.1.0-py3-none-any.whl
```

Or, pointing pip at the directory that holds the platform wheel
(PIP_FIND_LINKS: no index server involved):

```shell
PIP_FIND_LINKS=/path/to/wheels pip install dopi-pdda
PIP_FIND_LINKS=/path/to/wheels pipx install dopi-pdda
```

pip resolves the platform version range from the plug-in's manifest.

The plug-in installs two console scripts, without the platform's
prefix (they are the application's commands, not the platform's):

- `packages-deploy-deps-net-direct` — the dependency network table,
  one row per clause, indexed by depender.
- `packages-deploy-deps-net-reverse` — the same table reindexed by
  target, for the "who depends on this package?" questions.

## Quick Start

The fastest path: the development container. It installs the plug-in
and runs the battery automatically on start (see
The Development Container below); with the image built:

```shell
docker run --rm -it -v $PWD:/workspace dopi-pdda-dev
```

The battery output on start IS the smoke test: the plug-in's console
scripts land on PATH, the editable install resolves against the
platform, and the suite runs against both.

Smoke test without containers (platform wheel + plug-in, one
environment):

```shell
pip install /path/to/debian_observer-*-py3-none-any.whl
pip install -e '.[dev]'
pytest tests/ -q
packages-deploy-deps-net-direct --help
packages-deploy-deps-net-reverse --help
```

Both `--help` calls succeeding is the smoke signal: platform and
plug-in resolve each other.

## The Development Container

The plug-in develops against an installed platform. The devcontainer
image builds on the platform's own devcontainer image, and the platform
wheel travels in the build context (no index server, no clone).

Build the image (the platform wheel in the build-context root — the
repository root, per .devcontainer/devcontainer.json; the wheel keeps
its own filename: pip requires the wheel-name convention and the
Dockerfile installs it by glob):

```shell
python3 -m build --wheel /path/to/debian-observer   # or download the wheel
cp /path/to/debian-observer/dist/debian_observer-*-py3-none-any.whl .
docker build -t dopi-pdda-dev -f .devcontainer/Dockerfile .
rm debian_observer-*-py3-none-any.whl   # it does not belong to the repository
```

Run the container — the image entrypoint installs the plug-in
editable (with its dev extras) and runs the battery automatically on
every container start, then hands over to your command:

```shell
docker run --rm -it -v $PWD:/workspace dopi-pdda-dev
# entrypoint output: pip editable install + battery, then your shell
```

The battery is a diagnostic, not a gate: its verdict is reported and
the container starts regardless (coverage artifacts stay in /tmp —
the bind-mounted workspace is not writable by the container user).

## The Data Flow

As previously stated, DOPI-PDDA is a plug-in for the Debian Observer platform.

The platform gathers data from public Debian sources and stores it as observations.
Read its documentation to learn:

  - How do observations materialise the data:
    the observation schema and observation types.
  - For the sake of scalability, big-dat-processing usually is designed as pipelines
    where data is processed in stages/steps as it flows through.
    Prosumers are software pieces that perform processing steps. They take data to
    process from their upstream pipe and dump processed data downstream back to
    the pipe, where other prosumers process them further. The word 'prosumer' is a
    contraction of 'producer' and 'consumer'.
  - Debian Observer's documentation explains this and how to pipe the prosumers.

## The analysis

This repository is a collection of prosumers for a specifc purpose: analyzing
Debian's Package Deploy-Dependencies.

Debian is a Linux distribution. It distrbutes its software as packages. Packages
expect other packages (called dependencies) to be installed on the system before
the are installed or run. This kind of dependencies are the deploy dependencies.

There are other dependencies. For example, packages needed to build the package.
These and other non-deploy dependencies aren't targeted in this analysis.

1. This analysis will use a prosumer to extract the deploy-dependencies
   observations to create a `packages_deploy_dependencies` table.
2. Another one will create a copy indexed in reverse.
3. A third will calculate some statistical metrics.
4. A fourth one will crawl the straight and reverse networks to generate
   the dependency network for a specfic package in specific Debian coordinates.

See the [project document](docs/release2.project.v0.2.md) for more details.


## Debian Observer

See its documentation to learn how to

  1. Ingest data
  2. Normalize it as observations
  3. Serve the observations to consumers.
