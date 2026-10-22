#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work" "$root/cytoscape.min.js"' EXIT

package="$(cd "$work" && npm pack cytoscape@3.34.4 --silent)"
tar -xzf "$work/$package" -C "$work"
cp "$work/package/dist/cytoscape.min.js" "$root/cytoscape.min.js"

browser="${CHROME_BIN:-$(command -v google-chrome || command -v chromium)}"
dump="$work/dom.html"
"$browser" --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --allow-file-access-from-files --dump-dom \
  "file://$root/benchmark.html" > "$dump"

python3 - "$dump" <<'PY'
import html
import json
import re
import sys

document = open(sys.argv[1], encoding="utf-8").read()
match = re.search(r'<pre id="results"[^>]*data-complete="true"[^>]*>(.*?)</pre>', document, re.S)
if not match:
    raise SystemExit("benchmark did not complete")
payload = json.loads(html.unescape(match.group(1)))
print(json.dumps(payload, indent=2, sort_keys=True))
PY
