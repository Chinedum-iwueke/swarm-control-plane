#!/usr/bin/env bash
set -euo pipefail

label="com.invariance.hermes-mission-control"
plist="${HOME}/Library/LaunchAgents/${label}.plist"
remove_service=false
if [[ "${1:-}" == "--stop" ]]; then
  remove_service=true
elif [[ -n "${1:-}" ]]; then
  echo "Usage: $0 [--stop]" >&2
  exit 2
fi

if "$remove_service"; then
  launchctl bootout "gui/${UID}/${label}" 2>/dev/null || true
fi
rm -f "$plist"
echo "Removed the launchd definition."
echo "Credentials, knowledge data, logs, and the virtual environment were preserved."

