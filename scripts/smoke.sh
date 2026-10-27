#!/usr/bin/env bash
# Post-deploy smoke test:
#   SMOKE_USER=... SMOKE_PASSWORD=... scripts/smoke.sh https://your-app.vercel.app
set -euo pipefail
base="${1:?usage: smoke.sh BASE_URL}"
user="${SMOKE_USER:-demo}"; pass="${SMOKE_PASSWORD:-demo-password}"
jar="$(mktemp)"; trap 'rm -f "$jar"' EXIT

ok()   { echo "ok   $1"; }
fail() { echo "FAIL $1"; exit 1; }
status() { curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$@"; }

[ "$(status "$base/api/v1/health")" = 200 ] && ok "health is public" || fail "health"
[ "$(status "$base/api/v1/accuracy/summary")" = 401 ] && ok "data is blocked without a session" || fail "DATA IS NOT PROTECTED"
login() { # $1 = password; prints the HTTP status
  local body; body=$(printf '{"username":"%s","password":"%s"}' "$user" "$1")
  status -c "$jar" -H 'Content-Type: application/json' --data "$body" "$base/api/v1/auth/login"
}
[ "$(login "wrong-$pass")" = 401 ] && ok "bad password rejected" || fail "bad password accepted"
[ "$(login "$pass")" = 200 ] && ok "login" || fail "login with SMOKE_USER/SMOKE_PASSWORD"

check() { curl -fsS --max-time 30 -b "$jar" "$base$1" | grep -q "$2" && ok "$1" || fail "$1"; }
check /api/v1/ready '"actuals":744'
check '/api/v1/forecast?delivery_date=2026-01-15' '"points"'
check /api/v1/accuracy/summary '"mae_mw"'
curl -fsS --max-time 30 "$base/decision" | grep -q '<div id="root">' && ok "/decision (SPA fallback)" || fail "/decision"
echo "smoke passed"
