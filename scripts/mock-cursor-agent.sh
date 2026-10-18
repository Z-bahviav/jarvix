#!/usr/bin/env bash
# Place on PATH as cursor-agent for local testing (see scripts/run-verification.sh)
if [[ "${1:-}" == "-p" ]]; then
  echo "Title: Mock Cursor Task"
  echo "Mock cursor-agent completed successfully."
  echo "Brief length: ${#2} chars"
  exit 0
fi
echo "mock cursor-agent — use -p <brief>" >&2
exit 1
