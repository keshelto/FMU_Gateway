#!/usr/bin/env bash
set -euo pipefail

OUTPUT="${1:-fmu_gateway.bundle}"

echo "Creating git bundle at ${OUTPUT}"
# Include all refs reachable from the current repository
if git bundle create "${OUTPUT}" --all; then
  echo "Bundle created: ${OUTPUT}"
  echo "Transfer this file to a machine with remote access and clone from it using:"
  echo "  git clone ${OUTPUT} FMU_Gateway"
else
  echo "Failed to create bundle" >&2
  exit 1
fi
