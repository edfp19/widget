# Sporting Risk Data Widget Prototype

Cycle 2 of the football widget prototype keeps the public widget contract stable while swapping the backend data layer from mock JSON files to a provider-based stack backed by ClickHouse and Redis. The repo still supports the original mock provider as a rollback and test path.

## Prerequisites

- Docker with Docker Compose support
- Python 3.11
- `uv` for local Python workflow
- Node.js 20+ for browser verification

## Quickstart

### Docker Compose

From the project root:

```bash
docker compose up --build
```

If your WSL user does not yet have Docker socket access, you may need:

```bash
sudo docker compose up --build
```

The app will be available on port `8080`.

If you have previously brought the stack down without persisting Keeper state and the ClickHouse replicas come back in readonly mode, do one clean reset:

```bash
docker compose down -v
docker compose up --build
```

The Compose file now persists Keeper metadata so future cold restarts should keep the replicated-table topology intact.

Default Compose behavior now starts:

- `api`
- `worker`
- `redis`
- `clickhouse1`
- `clickhouse2`
- `keeper`
- `backup`

The API runs in `clickhouse` mode in Compose by default.

The API, worker, and backup services now wait for both ClickHouse replicas to pass an HTTP healthcheck before they start. On a cold boot, give the replicas a little time to become healthy before running manual recovery or backup commands.

For the cleanest manual verification after a cold boot:

```bash
until curl -sf http://127.0.0.1:8080/api/health >/dev/null; do
  sleep 2
done
```

### Local `uv` workflow

Create or refresh the environment:

```bash
uv sync --all-groups
```

Run the backend locally:

```bash
uv run python backend/server.py
```

Run the ClickHouse seed script locally:

```bash
uv run python backend/worker/seed.py
```

Run backend API contract tests:

```bash
uv run python -m unittest discover -s tests -p 'test_api_smoke.py'
```

Run the extended Cycle 2 unit suite:

```bash
uv run python -m unittest discover -s tests -p 'test_*.py'
```

Install browser test dependencies:

```bash
npm install
```

Install the Playwright browser used by the verification suite:

```bash
npm run test:browser:install
```

Run the browser verification suite:

```bash
npm run test:browser
```

The Playwright config starts the Tornado server with `uv run python backend/server.py`.
If the app is already running through Docker Compose or a local `uv` session, Playwright
reuses the existing server on port `8080`.

## URL Index

- `/example` - example operator page with the embedded widget and dev phase toggles
- `/config` - standalone configurator with live preview and generated CSS overrides
- `/api/health` - health endpoint for local checks and container health probes
- `/api/admin/replay/reset` - reset ClickHouse-backed demo state to the seeded baseline
- `/api/admin/replay/step` - apply the next deterministic replay event

## Project Layout

- `backend/` - Tornado application, handlers, providers, services, mock data, and replay/seed utilities
- `frontend/` - embeddable widget loader, container shell, renderers, styles, and example page
- `configurator/` - theming tool for generating CSS variable overrides
- `sql/` - ClickHouse bootstrap schema
- `docs/` - Cycle 2 contract and design notes
- `scripts/` - backup, restore, and failover demo helpers
- `tests/` - API contract tests and legacy browser smoke scaffolding
- `tests/e2e/` - Playwright end-to-end checks for the example page and configurator

## Verification Checklist

### `/example`

- Confirms the script-tag embed boots successfully
- Shows the persistent match header with score and phase/minute context
- Demonstrates tab switching for all implemented widget views
- Includes phase controls for pre-match, confirmed line-ups, live, half-time, and full-time
- Exercises live-only behavior such as xG race visibility and live squads/facts rendering

### `/config`

- Re-mounts the widget preview for match, competition, or homepage contexts
- Generates an embed snippet from the selected page type, pinned ids, visible tabs, and default tab
- Generates CSS variable overrides for light and dark theme variants
- Lets reviewers verify tab ordering and default tab changes without editing widget source code

## Architecture Summary

### Why Tornado

Tornado fits the widget backend well because the API is I/O-oriented, small, and phase-aware. Its async request handling keeps the server responsive while we simulate or later replace mock JSON reads with real upstream calls, caches, or data services.

### Why vanilla JavaScript

The widget is intended to be embedded into third-party pages with minimal integration cost. Vanilla JavaScript keeps the payload simple, avoids framework coupling, and makes the widget easier to drop into operator environments that may already have their own frontend stack.

### Why CSS variables instead of Shadow DOM

CSS custom properties let the widget stay themeable from the host page and from the configurator without needing a compile step. That is a better fit for an embeddable betting/media widget than strict style isolation, because operators usually want branding control more than hard encapsulation.

## Cycle 2 Data Architecture

The public API contract is unchanged. Handlers still own validation, response envelopes, and TTL headers. Data access now flows through a provider registry:

- `mock` provider: preserves Cycle 1 file-backed behavior for tests and rollback
- `clickhouse` provider: serves data from ClickHouse and Redis

The ClickHouse mode uses two storage layers:

- serving tables for hot live reads:
  - `widget.match_state_latest`
  - `widget.match_xg_events`
  - `widget.match_facts`
- normalized row-oriented slower resources:
  - `widget.competition_table_rows`
  - `widget.competition_fixture_rows`
- snapshot documents for the remaining slower or more nested resources:
  - `widget.widget_documents`

Raw replay events are also written to `widget.raw_match_events`, and `widget.ingest_event_ledger` tracks replay progress so the ingest path is replayable, inspectable, and recoverable after partial failure. The seed/reset path now writes a synthetic baseline event history into `raw_match_events` as well, so rebuild-from-raw can restore both the seeded live baseline and later replay mutations.

## Ingest and Live Demo

The primary Cycle 2 ingest path is deterministic replay rather than a queue transport. That keeps the payload model close to the API resources and makes the live demo easy to reproduce.

Replay is now intentionally small-batch instead of per-event:

- flush after `2` queued events, or
- flush after `250ms`, whichever comes first

That keeps local operation simple while still giving the design a concrete batching and backlog stance. Duplicate events are keyed by `event_id`; replay checks the raw-event log, ingest ledger, and serving-table `source_event_id` fields so the same event does not double-apply logical updates.

The supported ingest topology remains a single replay worker. The current idempotency model is designed for replay retry and crash recovery, not true concurrent multi-writer ingestion.

Reset the backend to the seeded baseline:

```bash
curl -X POST http://127.0.0.1:8080/api/admin/replay/reset
```

Apply the next replay event:

```bash
curl -X POST http://127.0.0.1:8080/api/admin/replay/step
```

You can also use the new replay buttons on `/example`. The example page now polls state every second so the backend replay path is visible without a full page reload.

To verify that rebuild-from-raw now restores the seeded live baseline as well as later replay mutations:

```bash
curl http://127.0.0.1:8080/api/health
curl -X POST http://127.0.0.1:8080/api/admin/replay/reset
docker compose exec -T api python -u scripts/rebuild_from_raw.py
```

Expected behavior:

- `/api/health` returns `{"status":"ok"}`
- replay reset returns `{"status":"ok"}`
- rebuild reports a non-zero number of replayed events, because the baseline itself is now represented in `raw_match_events`

## Cache Policy

Redis enforces the same per-endpoint TTLs documented in `API.md`, not just `Cache-Control` headers.

Hot keys are:

- `state` - 5s
- `xg-race` - 10s
- `facts` - 15s
- `team-stats` - 120s

Replay events invalidate all match-scoped live keys for the affected match.

## Replication and Failover

The local topology uses:

- one shard
- two ClickHouse replicas
- ClickHouse Keeper for coordination

This project intentionally prefers replicas over sharding because the candidate task is about redundancy and operational judgment, not scale-out complexity.

Reads are freshness-first for the live path. The API prefers the configured hosts in order and falls back to the next host if the first one is unavailable.

Local/demo writes now enforce `INSERT_QUORUM=1` at runtime for ClickHouse write paths so bring-up stays easy and deterministic. For a production deployment, the safer recommendation is to raise quorum for the most critical live writes if the latency budget allows it.

Demo failover with:

```bash
./scripts/failover_demo.sh
```

That script:

1. resets replay state
2. stops `clickhouse1`
3. applies the next replay event
4. reads live state through the API
5. starts `clickhouse1` again
6. waits for the replica to rejoin
7. checks replication health from `system.replicas`

## Backup and Restore

Backup and restore are handled by JSON snapshot scripts so the operational path is runnable without extra tooling.

Compose now includes a lightweight scheduled backup service that runs:

- `python scripts/backup_clickhouse.py --output-dir /backups`

on a fixed interval and writes artifacts to the `backups-data` volume.

The backup flow now also:

- keeps the latest `5` backup directories by default
- writes `latest.json` with backup status, timestamp, backup directory, table count, and total row count
- records failure state in `latest.json` if a scheduled backup fails

Create a backup:

```bash
uv run python scripts/backup_clickhouse.py --output-dir backups
```

Restore a backup:

```bash
uv run python scripts/restore_clickhouse.py backups/widget-backup-<timestamp>
```

Rebuild the live serving path from the raw event log:

```bash
uv run python scripts/rebuild_from_raw.py
```

Replication protects against node loss. The backup scripts protect against table loss, bad writes, or schema mistakes.

The rebuild script is the explicit recovery path for the normalized live serving tables. Use it after restoring a backup or after intentionally clearing live serving tables when you want to reconstruct `state`, `xg-race`, `facts`, and the live team-stats overlay from `raw_match_events`.

For the repo deliverable, backups target a local Docker volume. For a production deployment, object storage such as S3 is the recommended target.

## Testing

Contract safety:

- `tests/test_api_smoke.py`

Cycle 2 additions:

- `tests/test_provider_registry.py`
- `tests/test_provider_cache.py`
- `tests/test_clickhouse_provider.py`
- `tests/test_clickhouse_failover.py`
- `tests/test_clickhouse_http.py`
- `tests/test_replay_service.py`
- `tests/test_backup_restore.py`

Browser verification:

```bash
npm run test:browser
```

The Playwright suite now includes a backend replay case that verifies the live widget updates after replayed events.

## Development Notes

- The example page at `/example` includes force-phase buttons for local demo behavior.
- The example page also includes backend replay reset/step controls for the ClickHouse live path.
- The backend serves frontend assets from `/static/*`.
- `backend/mock_data/` still powers the `mock` provider and the ClickHouse seed script.
- Set `WIDGET_PROVIDER=mock` to roll back to the original data path instantly.
- Additive schema changes should prefer `ALTER` when safe; incompatible changes should use new-table-then-cutover.
- If Keeper quorum is lost, writes should be treated as unavailable; read-only fallback is the acceptable degraded mode.

## AWS Deployment Note

For a production-shaped deployment:

- run the API layer on ECS Fargate or EKS
- distribute static widget assets through CloudFront
- place Redis on ElastiCache
- deploy ClickHouse replicas in separate AZs
- run an odd-sized Keeper ensemble, ideally 3 nodes in production
- use distinct DB users for API reads, ingestion, and admin tasks

For more detail, see:

- [`docs/cycle2_contract_notes.md`](docs/cycle2_contract_notes.md)
- [`docs/cycle2_design.md`](docs/cycle2_design.md)
