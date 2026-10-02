#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image_name="trends-pipeline:smoke"
temporary_dir="$(mktemp -d)"
trap 'rm -rf "$temporary_dir"' EXIT
mkdir -p "$temporary_dir/processed" "$temporary_dir/reports"

docker build -t "$image_name" "$repo_root"
docker run --rm \
  -v "$repo_root/tests/fixtures/synthetic:/input:ro" \
  -v "$temporary_dir/processed:/output" \
  -v "$temporary_dir/reports:/reports" \
  "$image_name" run \
  --input /input/trends.csv \
  --manifest /input/manifest.yaml \
  --output-dir /output \
  --report /reports/validation.json

test -s "$temporary_dir/processed/time_series.csv"
test -s "$temporary_dir/processed/features.csv"
grep -q '"valid": true' "$temporary_dir/reports/validation.json"
printf '%s\n' 'Docker smoke test passed with the synthetic fixture.'