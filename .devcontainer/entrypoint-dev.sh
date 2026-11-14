#!/bin/sh
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Purpose: Development container entrypoint: Set up a development environment.
#
# Design.: With the repository bind-mounted at /workspacce, install the plug-in
#          (editable, with its dev extras) and run the battery automatically,
#          on every container start as a diagnostic.
#          The test are no gate: The container starts regardless of the test
#          results.
# -----------------------------------------------------------------------------
set -e
export PATH="$HOME/.local/bin:$PATH"

# The workspace bind-mount is root-owned: coverage cannot write its
# data file or the html report there. Keep both in /tmp instead
# (the battery verdict is the same; the artifacts are ephemeral).
export COVERAGE_FILE=/tmp/.coverage

cd /workspace
pip install --user -q -e '.[dev]'
pytest tests/ -q -p no:cacheprovider \
    --cov-report=term-missing --cov-report=html:/tmp/htmlcov \
    || echo "battery: FAIL (see report above; the container starts anyway)"

# With no command passed, stay alive: docker run -d mounts the
# repository and the container must keep running for the developer
# to exec into it (exec of an empty "$@" exits 0 immediately).
if [ "$#" -eq 0 ]; then
    echo "dev container ready: docker exec -it <cid> bash"
    exec sleep infinity
fi
exec "$@"
