# SPDX-License-Identifier: AGPL-3.0-or-later
# The plug-in's devcontainer builds ON the platform's devcontainer
# image: the plug-in develops against an installed platform, never
# against a modified one (docs/CONTRIBUTING.md, development set-up).
# The platform is a dependency: it is INSTALLED, not cloned. Until
# the platform publishes a wheel index, pass the platform wheel as a
# build argument (default: the local wheel beside the Dockerfile).
FROM deb-obs-devcontainer:latest

ARG PLATFORM_WHEEL=debian_observer.whl
COPY ${PLATFORM_WHEEL} /tmp/platform.whl
RUN pip install --no-cache-dir /tmp/platform.whl && rm /tmp/platform.whl
