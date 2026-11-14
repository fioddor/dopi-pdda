#!/usr/bin/env bash
# scripts/generate-sbom.sh - regenerate docs/SBOM.spdx.json (ported
# from debian-observer, adapted to the plug-in's tooling).
#
# Purpose: produce the SBOM of the development environment (the Python
#          dependencies installed in the devcontainer image) as SPDX
#          2.3 JSON.
# Design.: the plug-in has no compose file — the scan runs in an
#          EPHEMERAL container of the built devcontainer image
#          (dopi-pdda-dev), whose site-packages path is DERIVED at
#          run time (never hardcoded). A PINNED syft is downloaded
#          into the container's /tmp and scans those site-packages.
#          Tool invocations bypass the image's dev entrypoint (the
#          auto battery) via --entrypoint. syft emits extracted
#          license TEXTS (hasExtractedLicensingInfos) for
#          package-declared licenses it cannot map to an SPDX
#          identifier; this SBOM must carry SPDX identifiers and
#          purls only, so the script strips those texts and rewrites
#          their LicenseRef-* references to NOASSERTION.
#          THE SBOM IS NOT COMMITTED: the platform tracks it in git,
#          but the plug-in's front proxy (nginx -> gitea HTTPS)
#          rejects pushes of bodies this large (HTTP 413); the
#          generation is the product, the artifact stays local
#          (see .gitignore and the SBOM rules in CONTRIBUTING).
# When:   run it whenever [project].dependencies changes.
# Usage:  scripts/generate-sbom.sh   (from the repository root, with
#          the devcontainer image built:
#          docker build -f .devcontainer/Dockerfile -t dopi-pdda-dev .)
#
# syft pin: v1.54.1 — https://github.com/anchore/syft
set -euo pipefail

SYFT_VERSION="v1.54.1"
SYFT_NUMBER="${SYFT_VERSION#v}"
IMAGE="dopi-pdda-dev:latest"
OUT="docs/SBOM.spdx.json"

cd "$(dirname "$0")/.."

# The devcontainer image must exist.
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "ERROR: image '${IMAGE}' not found." >&2
    echo "       Build it first: docker build -f .devcontainer/Dockerfile -t ${IMAGE%%:*} ." >&2
    exit 1
fi

# Detect the container architecture (syft publishes amd64 and arm64).
# --entrypoint bypasses the image's dev entrypoint (auto battery):
# as a tool container we only want uname, not an install+pytest run.
case "$(docker run --rm --entrypoint /bin/sh "$IMAGE" -c 'uname -m')" in
    x86_64) SYFT_ARCH="amd64" ;;
    aarch64 | arm64) SYFT_ARCH="arm64" ;;
    *)
        echo "ERROR: unsupported container architecture for the syft download." >&2
        exit 1
        ;;
esac
SYFT_URL="https://github.com/anchore/syft/releases/download/${SYFT_VERSION}/syft_${SYFT_NUMBER}_linux_${SYFT_ARCH}.tar.gz"

# 1. Derive the site-packages path empirically, inside the image.
SITE_PACKAGES="$(docker run --rm --entrypoint /bin/sh "$IMAGE" -c 'python -m site --user-site')"
echo "[sbom] devcontainer site-packages: ${SITE_PACKAGES}"

# 2+3. Download the pinned syft into an ephemeral container's /tmp and
#      scan the installed dependencies into a raw document.
RAW="$(mktemp)"
trap 'rm -f "$RAW"' EXIT
echo "[sbom] scanning installed dependencies (pinned syft ${SYFT_VERSION}, linux_${SYFT_ARCH}) ..."
docker run --rm --entrypoint /bin/bash "$IMAGE" -c "
    curl -sfSL '${SYFT_URL}' -o /tmp/syft.tar.gz
    tar -xzf /tmp/syft.tar.gz -C /tmp syft
    /tmp/syft '${SITE_PACKAGES}' -o spdx-json --source-name 'dopi-pdda-dev-deps'
" > "$RAW"

# 4. Normalize the document: SPDX identifiers and purls only.
python3 - "$RAW" "$OUT" <<'PY'
import json
import sys

doc = json.load(open(sys.argv[1], encoding="utf-8"))

def only_spdx_ids(value):
    """LicenseRef-* references dangle once the texts are stripped."""
    return "NOASSERTION" if value and "LicenseRef" in value else value


for package in doc.get("packages", []):
    package["licenseConcluded"] = only_spdx_ids(package.get("licenseConcluded"))
    package["licenseDeclared"] = only_spdx_ids(package.get("licenseDeclared"))
for entry in doc.get("files", []):
    entry["licenseConcluded"] = only_spdx_ids(entry.get("licenseConcluded"))
    entry["licenseDeclared"] = only_spdx_ids(entry.get("licenseDeclared"))
doc.pop("hasExtractedLicensingInfos", None)

with open(sys.argv[2], "w", encoding="utf-8") as f:
    json.dump(doc, f, separators=(",", ":"))
    f.write("\n")
print("[sbom] normalized: no hasExtractedLicensingInfos, LicenseRef-* -> NOASSERTION")
PY

# 5. Sanity-check the produced document.
python3 - "$OUT" <<'PY'
import json
import sys

text = open(sys.argv[1], encoding="utf-8").read()
doc = json.loads(text)
assert doc["spdxVersion"] == "SPDX-2.3", doc["spdxVersion"]
assert doc["dataLicense"] == "CC0-1.0", doc["dataLicense"]
assert not doc.get("hasExtractedLicensingInfos"), "license texts must not be embedded"
assert "LicenseRef" not in text, "LicenseRef-* must not remain"
assert doc.get("packages"), "no packages found"
print(f"[sbom] OK: {len(doc['packages'])} packages, spdxVersion={doc['spdxVersion']}")
PY
echo "[sbom] wrote ${OUT} (local artifact: .gitignored, not committed)"