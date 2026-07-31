#!/usr/bin/env bash
# P3-59 probe — driver de afvisninger admissionsreglen udvalgte.
# Samme script bruges til før- og efter-måling, så instrumentet er identisk.
# Brug: ./probe.sh <label>   (label bruges i outputfilnavne)
set -u
S="$(cd "$(dirname "$0")" && pwd)"
LABEL="${1:-run}"
TA=$(cat "$S/tok_p359a")
TB=$(cat "$S/tok_p359b")
KEY_BAD="definitely-not-the-key"
SAGA_OTHER="e9fcf992-d9f9-482a-9d08-95a7b5cbb1c4"   # ejet af user 1
SAGA_NOUSER="${SAGA_NOUSER:-}"                       # sættes af caller hvis probe-rækken findes
RANDUUID="00000000-0000-4000-8000-000000000999"

hit() { # navn metode url [headers...]
  local name="$1" method="$2" url="$3"; shift 3
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' -X "$method" "$url" "$@")
  printf '%-34s %s %s\n' "$name" "$code" "$url"
}

echo "########## P3-59 PROBE ($LABEL) ##########"

echo "--- shared/auth ---"
hit "AUTH1 udekodbar token (SKAL logge)" GET  http://localhost:8006/api/v1/goals \
    -H "Authorization: Bearer not.a.valid.token" -H "X-Account-ID: 511"
hit "AUTH2 manglende header (NEG)"       GET  http://localhost:8006/api/v1/goals \
    -H "X-Account-ID: 511"
hit "AUTH3 malformet Bearer (NEG)"       GET  http://localhost:8006/api/v1/goals \
    -H "Authorization: Basic abc" -H "X-Account-ID: 511"

echo "--- user ---"
hit "U1 forkert password (401)"  POST http://localhost:8001/api/v1/users/login \
    -H 'Content-Type: application/json' -d '{"username_or_email":"p359a","password":"WrongPass123!"}'
hit "U2 forkert nuv. password"   PUT  http://localhost:8001/api/v1/users/me/password \
    -H "Authorization: Bearer $TA" -H 'Content-Type: application/json' \
    -d '{"current_password":"WrongPass123!","new_password":"Probe12345!"}'
hit "U3 dobbelt-registrering"    POST http://localhost:8001/api/v1/users/register \
    -H 'Content-Type: application/json' \
    -d '{"username":"p359a","email":"p359a@example.com","password":"Probe12345!"}'
hit "U4 intern nøgle forkert"    GET  "http://localhost:8001/api/v1/users/497" \
    -H "X-Internal-API-Key: $KEY_BAD"
hit "U5 intern nøgle mangler"    GET  "http://localhost:8001/api/v1/users/497"

echo "--- account ---"
hit "AC1 GET fremmed konto (403)" GET http://localhost:8004/api/v1/accounts/512 \
    -H "Authorization: Bearer $TA"
hit "AC2 PUT fremmed konto (403)" PUT http://localhost:8004/api/v1/accounts/512 \
    -H "Authorization: Bearer $TA" -H 'Content-Type: application/json' \
    -d '{"name":"hijack","saldo":0,"budget_start_day":1}'
hit "AC3 intern nøgle forkert"    GET "http://localhost:8004/api/v1/internal/accounts/511/exists" \
    -H "x-internal-api-key: $KEY_BAD"
hit "AC4 intern nøgle mangler"    GET "http://localhost:8004/api/v1/internal/accounts/511/exists"

echo "--- goal ---"
hit "G1 fremmed X-Account-ID(403)" GET http://localhost:8006/api/v1/goals \
    -H "Authorization: Bearer $TA" -H "X-Account-ID: 512"
hit "G2 X-Account-ID=abc (400)"    GET http://localhost:8006/api/v1/goals \
    -H "Authorization: Bearer $TA" -H "X-Account-ID: abc"
hit "G3 fremmed goal (404!)"       GET http://localhost:8006/api/v1/goals/50 \
    -H "Authorization: Bearer $TA"
hit "G4 ordinær 404 som ejer(NEG)" GET http://localhost:8006/api/v1/goals/999999 \
    -H "Authorization: Bearer $TB"

echo "--- notification ---"
hit "N1 read ukendt id (404)"   POST "http://localhost:8008/api/v1/notifications/$RANDUUID/read" \
    -H "Authorization: Bearer $TA"
hit "N2 dismiss ukendt id (404)" DELETE "http://localhost:8008/api/v1/notifications/$RANDUUID" \
    -H "Authorization: Bearer $TA"
hit "N3 limit=0 -> 422 (NEG)"    GET "http://localhost:8008/api/v1/notifications?limit=0" \
    -H "Authorization: Bearer $TA"

echo "--- saga ---"
hit "S1 fremmed saga (403)" GET "http://localhost:8011/api/v1/sagas/$SAGA_OTHER" \
    -H "Authorization: Bearer $TA"
if [ -n "$SAGA_NOUSER" ]; then
  hit "S2 korrupt context (403)" GET "http://localhost:8011/api/v1/sagas/$SAGA_NOUSER" \
      -H "Authorization: Bearer $TA"
fi
echo "########## SLUT ($LABEL) ##########"
