#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "==> Java unit tests for Part A customization"
echo "    (requires a local checkout of Fineract 1.15.0 with the patch applied)"
echo
echo "Recommended commands once the source is patched:"
echo
echo "  cd /path/to/fineract"
echo "  ./gradlew :fineract-core:test --tests GLAccountExternalReferenceTest"
echo "  ./gradlew :fineract-accounting:test   # or the module that contains the write service"
echo
echo "The unit test class lives at:"
echo "  fineract-customization/src/test/java/.../GLAccountExternalReferenceTest.java"
echo
echo "Copy it into the corresponding test source set of the patched tree and run."
echo
echo "Integration test (full HTTP) is demonstrated by scripts/demo-gl-sync.sh"
echo "against the running custom Docker image."