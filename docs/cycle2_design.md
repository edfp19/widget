# Cycle 2 Design Notes

## Architecture summary

Cycle 2 keeps the Tornado handlers and widget contract stable, then swaps the data source underneath them:

- handlers still own validation, cache headers, and response envelopes
- a provider registry selects `mock` or `clickhouse`
- ClickHouse stores:
  - raw replayable events
  - an ingest ledger for idempotency and recovery
  - latest match state
  - ordered xG rows
  - ordered fact rows
  - row-oriented competition table snapshots
  - row-oriented competition fixtures snapshots
  - snapshot-style JSON documents for the remaining slower or more nested resources
- Redis sits in front of the hottest reads with TTLs matching `API.md`
- a replay service applies deterministic demo events and invalidates match-scoped cache keys

## Storage decisions

- `raw_match_events` uses a replicated append-only table for replay, audit, and recovery.
- `ingest_event_ledger` tracks whether an `event_id` is `pending` or `applied`, which lets replay resume safely after partial failures.
- `match_state_latest` uses a replicated replacing table keyed by `match_id` because the API needs one freshest row.
- `match_xg_events` and `match_facts` use replicated append-style tables because ordered time-series reads fit ClickHouse naturally.
- `competition_table_rows` and `competition_fixture_rows` are normalized because these resources are naturally row-shaped, queryable by competition and status, and a better fit for analytical storage than opaque blobs.
- `widget_documents` remains for squads, H2H payloads, and team aggregate stats, where the widget consumes nested snapshots as whole payloads and write pressure is low.

## Partitioning and ordering

- `raw_match_events` partitions by event date and orders by `(match_id, event_ts, event_id)` so replay and audit scans stay cheap.
- `match_state_latest` orders by `match_id` because the API always resolves one freshest state per match.
- `match_xg_events` orders by `(match_id, event_ts)` to support time-ordered chart reads.
- `match_facts` orders by `(match_id, sort_index, fact_ts)` so the API can preserve feed order while still keeping fact timestamps.
- `competition_table_rows` orders by `(competition_id, snapshot_ts, position)`.
- `competition_fixture_rows` orders by `(competition_id, status, fixture_date, match_id)`.

## Ingestion and idempotency

- The primary ingest path is a deterministic replay worker.
- Payloads mirror API resource slices instead of inventing a separate event vocabulary.
- `event_id` is the dedupe key across the raw-event log, the ingest ledger, and serving-table updates.
- The worker batches conservatively: flush when it accumulates `2` events or when the queue is `250ms` old.
- The worker writes raw data first, marks the ledger `pending`, updates serving tables, updates live team-stats documents when needed, invalidates Redis keys for the affected match, then marks the ledger `applied`.
- If the worker crashes after raw-event persistence but before serving-table completion, replay can safely resume because raw-event existence and serving-table `source_event_id` checks prevent double-application.
- The seed path writes a synthetic baseline event history into `raw_match_events`, so rebuild-from-raw can restore both the seeded live baseline and later replay mutations.
- Backfill and recovery replay from `raw_match_events` in event order through an explicit rebuild script that reuses the replay service's serving-table logic.
- The supported ingest topology is one replay worker. This repo intentionally does not implement true concurrent multi-writer coordination.

## Read/write and migration stance

- Local/demo writes enforce `insert_quorum = 1` on ClickHouse write paths to keep bring-up simple and predictable.
- The production-shaped recommendation is to raise quorum for the most critical live writes if the latency budget allows it.
- Reads are freshness-first rather than replica-balanced: the API tries configured hosts in order and falls back quickly on connection failure.
- Strict cross-replica sequential consistency is not the local default; the design optimizes for continuity and low operational friction in the assessment environment.
- Additive schema changes should use `ALTER` when they are safe and low-risk.
- Incompatible schema changes should use new-table-then-cutover rather than risky in-place rewrites.
- If Keeper quorum is lost, writes should be considered unavailable; read-only fallback is acceptable and should be surfaced operationally.

## Failover and backup

- The local stack uses one shard, two replicas, and ClickHouse Keeper.
- The API prefers freshness-first reads by trying the host list in order and falling back on failure.
- `scripts/failover_demo.sh` demonstrates replica loss during replay, then verifies the restarted replica rejoins and reports healthy replication status.
- Backup and restore are handled by `scripts/backup_clickhouse.py` and `scripts/restore_clickhouse.py`, which export/import the widget tables as JSON snapshots.
- `scripts/rebuild_from_raw.py` rebuilds the normalized live serving tables from `raw_match_events` without reseeding mock data.
- The Compose stack also includes a `backup` service that runs those backup exports on a fixed interval, writes them to a local volume, prunes old snapshots, and updates a machine-readable `latest.json` status file.
- Replication protects against node loss; the backup scripts protect against table loss or bad writes.

## Production-shaped vs simplified

Production-shaped parts of this repo:

- provider-based contract preservation
- normalized live-path tables
- explicit ingest idempotency
- app-side replica failover
- scheduled backup flow

Intentional simplifications for the assessment:

- one shard instead of a distributed topology
- local-volume backups instead of object storage
- a two-event / 250ms batching policy tuned for demo reliability, not maximum throughput
- document-backed nested resources that do not yet justify deeper normalization
- single-worker replay instead of true multi-writer ingestion coordination
