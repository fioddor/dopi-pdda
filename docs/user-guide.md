# User Guide

Quick start and operational guide for DOPI-PDDA
(Debian Observer Plug-In: Packages Deploy-Dependency Analysis).

## Installation


## Quick Start

Install, smoke tests, ...

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
