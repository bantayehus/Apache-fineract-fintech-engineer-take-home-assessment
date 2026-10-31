#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CUSTOM="$ROOT/fineract-customization"
TAG="1.15.0"
IMAGE="fineract-custom:${TAG}-assessment"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not available in this environment."
  echo
  echo "Build the image on your local machine (see fineract-customization/BUILD.md):"
  echo
  echo "  cd fineract-customization"
  echo "  docker build --build-arg FINERACT_TAG=${TAG} -t ${IMAGE} ."
  echo
  echo "Requirements: ≥ 8 GB RAM for the Docker daemon, ≥ 15 GB free disk, 10–25 min."
  exit 1
fi

echo "==> Building customized Fineract image: $IMAGE"
echo "    Pin: Apache Fineract ${TAG} | JDK 21"
echo "    This clones the official tag, applies Part A customisation, and builds."
echo "    Expect 10–25 minutes and ≥ 4 GB RAM for the daemon."
echo

cd "$CUSTOM"
docker build \
  --build-arg FINERACT_TAG="$TAG" \
  --build-arg GRADLE_OPTS="-Dorg.gradle.daemon=false -Dorg.gradle.jvmargs=-Xmx3g -Dorg.gradle.parallel=false" \
  -t "$IMAGE" \
  .

echo
echo "==> Image built successfully: $IMAGE"
echo "    Next:"
echo "      docker compose up -d"
echo "      ./scripts/wait-for-services.sh"
echo "      ./scripts/seed-fineract.sh"