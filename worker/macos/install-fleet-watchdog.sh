#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS." >&2
  exit 2
fi
if [[ ${EUID} -eq 0 ]]; then
  echo "Run this installer as the logged-in Mac user, not root." >&2
  exit 2
fi

repo="$(cd "$(dirname "$0")/../.." && pwd)"
root="${HOME}/Library/Application Support/Invariance Fleet Watchdog"
env_file="${root}/fleet-watchdog.env"
token_file="${root}/telegram.token"
state_file="${root}/state.json"
venv="${root}/venv"
wrapper="${root}/run"
label="com.invariance.fleet-watchdog"
plist="${HOME}/Library/LaunchAgents/${label}.plist"

install -d -m 0700 "$root" "${HOME}/Library/LaunchAgents"
if [[ ! -f "$env_file" || ! -f "$token_file" ]]; then
  printf 'Create protected files before installation:\n  %s\n  %s\n' "$env_file" "$token_file" >&2
  exit 2
fi
chmod 0600 "$env_file" "$token_file"
grep -q '^SWARM_WATCHDOG_TARGETS=' "$env_file"
grep -q '^SWARM_WATCHDOG_WATCHER_ID=' "$env_file"
grep -q '^SWARM_WATCHDOG_FOUNDER_CHAT_ID=' "$env_file"

python3 -m venv --clear "$venv"
"$venv/bin/pip" install --disable-pip-version-check "$repo/worker"

cat >"$wrapper" <<EOF
#!/usr/bin/env bash
set -euo pipefail
set -a
source '${env_file}'
set +a
export SWARM_WATCHDOG_TELEGRAM_TOKEN_FILE='${token_file}'
export SWARM_WATCHDOG_STATE_PATH='${state_file}'
exec '${venv}/bin/invariance-swarm-fleet-watchdog' run
EOF
chmod 0700 "$wrapper"

cat >"$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>${label}</string>
  <key>ProgramArguments</key><array><string>${wrapper}</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>StandardOutPath</key><string>${root}/watchdog.log</string>
  <key>StandardErrorPath</key><string>${root}/watchdog.error.log</string>
  <key>Umask</key><integer>63</integer>
</dict></plist>
EOF
chmod 0600 "$plist"
plutil -lint "$plist"
launchctl bootout "gui/${UID}/${label}" 2>/dev/null || true
launchctl bootstrap "gui/${UID}" "$plist"
launchctl kickstart -k "gui/${UID}/${label}"
echo "Distributed fleet watchdog installed and started on macOS."
