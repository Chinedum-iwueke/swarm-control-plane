#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS." >&2
  exit 2
fi
if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this installer as the logged-in Mac user, not root." >&2
  exit 2
fi

start=false
if [[ "${1:-}" == "--start" ]]; then
  start=true
elif [[ -n "${1:-}" ]]; then
  echo "Usage: $0 [--start]" >&2
  exit 2
fi

repo="$(cd "$(dirname "$0")/../.." && pwd)"
app_root="${HOME}/Library/Application Support/Hermes Mission Control"
venv="${app_root}/venv"
env_file="${app_root}/mission-control.env"
token_file="${app_root}/orchestrator.token"
wrapper="${app_root}/run"
label="com.invariance.hermes-mission-control"
plist="${HOME}/Library/LaunchAgents/${label}.plist"

python="${HERMES_PYTHON:-$(command -v python3)}"
"$python" -c 'import sys; raise SystemExit(sys.version_info < (3, 9))' || {
  echo "Python 3.9 or newer is required." >&2
  exit 2
}

install -d -m 0700 \
  "$app_root" \
  "${app_root}/data/sources" \
  "${app_root}/data/research-inbox" \
  "${HOME}/Library/LaunchAgents"
if [[ ! -f "$env_file" || ! -f "$token_file" ]]; then
  cat >&2 <<EOF
Create these protected files before installation:
  ${env_file}
  ${token_file}
See mission-control/README.md for their exact contents.
EOF
  exit 2
fi
chmod 0600 "$env_file" "$token_file"

"$python" -m venv --clear "$venv"
"$venv/bin/python" -m pip install --upgrade pip
"$venv/bin/python" -m pip install "$repo/mission-control"

cat >"$wrapper" <<EOF
#!/usr/bin/env bash
set -euo pipefail
set -a
source '${env_file}'
set +a
exec '${venv}/bin/hermes-mission-control' run
EOF
chmod 0700 "$wrapper"

cat >"$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${label}</string>
  <key>ProgramArguments</key>
  <array><string>${wrapper}</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>${app_root}/mission-control.log</string>
  <key>StandardErrorPath</key><string>${app_root}/mission-control.error.log</string>
  <key>Umask</key><integer>63</integer>
</dict>
</plist>
EOF
chmod 0600 "$plist"
plutil -lint "$plist"

if "$start"; then
  launchctl bootout "gui/${UID}/${label}" 2>/dev/null || true
  launchctl bootstrap "gui/${UID}" "$plist"
  launchctl kickstart -k "gui/${UID}/${label}"
  echo "Installed and started ${label}."
else
  echo "Installed ${label}; it was not started."
fi
