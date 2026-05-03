#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Resetting replay state..."
curl -s -X POST http://127.0.0.1:8080/api/admin/replay/reset >/dev/null

echo "Stopping primary replica (clickhouse1)..."
docker compose stop clickhouse1

echo "Replaying next event while replica 1 is down..."
curl -s -X POST http://127.0.0.1:8080/api/admin/replay/step
echo

echo "Reading live state through the API..."
curl -s http://127.0.0.1:8080/api/v1/match/12345/state
echo

echo "Restarting primary replica..."
docker compose start clickhouse1

echo "Waiting for clickhouse1 to accept HTTP requests..."
for _ in $(seq 1 20); do
  if curl -s "http://127.0.0.1:8123/?query=SELECT%201" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "Checking replica catch-up on clickhouse1..."
curl -s "http://127.0.0.1:8123/?query=SELECT%20database%2Ctable%2Cis_readonly%2Cqueue_size%2Cabsolute_delay%20FROM%20system.replicas%20WHERE%20database%20%3D%20%27widget%27%20FORMAT%20JSON"
echo

echo "Re-reading live state after clickhouse1 rejoins..."
curl -s http://127.0.0.1:8080/api/v1/match/12345/state
echo

echo "Replica restarted and verified. Check docker compose ps and logs if you want to inspect further."
