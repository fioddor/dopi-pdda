# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Purpose: Provide a development container.
#
# Usage..: - Place the platform wheel (debian_observer-*-py3-none-any.whl) in
#            the the repository before building the container image.
#            See docs/CONTRIBUTING.md, development set-up.
#          - Do NOT rename the wheel while copying: pip requires the wheel-name
#            convention {name}-{version}-{python}-{platform}.whl, and a copied
#            "renamed-platform.whl" fails with "Invalid wheel filename".
#          - Keep the glob on the RUN line so pip receives a valid wheel
#            filename.
#
# Design.: - The wheel location travels in the build context. `"context": ".."`
#            in .devcontainer/devcontainer.json sets it to the repository root.
#
#            --chown is required: the base image's default user is vscode, and
#            a root-owned copy cannot be removed by the vscode RUN.
# -----------------------------------------------------------------------------
FROM deb-obs-devcontainer:latest

COPY --chown=vscode:vscode debian_observer-*-py3-none-any.whl /tmp/
RUN pip install --no-cache-dir /tmp/debian_observer-*-py3-none-any.whl \
    && rm -f /tmp/debian_observer-*-py3-none-any.whl

# On container start, with the repository mounted at /workspace: install
# the plug-in editable (dev extras) and run the battery, automatically
# (the entrypoint execs the passed command afterwards).
COPY --chown=vscode:vscode .devcontainer/entrypoint-dev.sh /usr/local/bin/dopi-entrypoint-dev
ENTRYPOINT ["/usr/local/bin/dopi-entrypoint-dev"]
