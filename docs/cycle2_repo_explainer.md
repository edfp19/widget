# Cycle 2 Repo Explainer

This document is aimed at a reader who is comfortable with SQL, Python, caching, OLAP storage, and basic client-server design, but is otherwise new to this repo.

I could not tailor this to a fetched LinkedIn profile because that profile was not available in this workflow, so the explanations below are tuned only to the technical skill level inferred from the request itself.

## 1. What this repo is trying to prove

This repository is a prototype for an embeddable football data widget.

At a high level, it has four moving parts:

- a Tornado API that serves widget JSON endpoints and the demo/static assets
- a provider seam that lets the same handlers read from either mock JSON or ClickHouse
- a frontend widget written in vanilla JavaScript that boots from a script tag
- an operational demo stack for caching, replay, replication, backup/restore, and failover

The key architectural promise is that the widget contract stays stable even when the storage and ingest layers change.

That is why most of the interesting work in Cycle 2 happened below the handler layer rather than in the public API.

## 2. What changed from Cycle 1 to Cycle 2

### Cycle 1 in one sentence

Cycle 1 was mostly a contract-first mock system:

- Tornado handlers read JSON files from `backend/mock_data/`
- the frontend consumed those endpoints
- the demo proved embed behavior, theming, and match-phase-aware UI

The backend was intentionally simple. A request like `/api/v1/match/12345/state` effectively meant "read the corresponding file, validate it, and return it in the standard envelope."

### Cycle 2 in one sentence

Cycle 2 keeps the same widget/API contract, but replaces the storage path with:

- a provider registry
- ClickHouse-backed reads
- Redis caching
- a deterministic replay worker
- explicit recovery and operational tooling
- a two-replica ClickHouse topology coordinated by Keeper

### The important architectural shift

Cycle 1:

`handler -> mock file -> response`

Cycle 2:

`handler -> provider interface -> ClickHouse provider -> Redis/ClickHouse -> response`

That shift matters because it turns the mock-backed prototype into something closer to a real service boundary:

- handlers remain the API contract owners
- data access becomes replaceable
- hot reads get caching
- writes become explicit and replayable
- failover and recovery become testable instead of hypothetical

### What did not change

The repo is very deliberate about keeping these stable:

- endpoint URLs
- query parameters
- cache TTLs exposed through `Cache-Control`
- response envelope shape
- error code/message behavior expected by tests

This is the central Cycle 2 idea: preserve the external contract while changing the internals substantially.

## 3. The request flow through the system

There are really two request flows to understand:

1. browser-to-backend read requests
2. replay/demo write requests

### 3.1 Browser read flow

The read flow begins in the frontend widget:

1. a host page includes `/static/loader.js`
2. `frontend/loader.js` reads `data-*` attributes from the script tag
3. for match pages, it first fetches `/api/v1/match/{match_id}/state`
4. it then registers tabs and fetches the relevant endpoints for those tabs
5. `backend/server.py` routes each request to a Tornado handler
6. the handler validates inputs, applies cache headers, and calls the configured provider
7. the provider either:
   - reads mock JSON in `mock` mode, or
   - checks Redis and then queries ClickHouse in `clickhouse` mode
8. the handler wraps the result in the standard `{ meta, data, error }` envelope
9. the frontend renderer paints the returned data

The important implementation detail is that the handlers do not know whether they are reading files or ClickHouse tables. They only know they have a `WidgetDataProvider`.

### 3.2 Replay/write flow

The write flow begins either through the background worker or through the demo/admin endpoints:

1. a replay event is loaded from `backend/worker/events.py`
2. `ReplayService` receives the event
3. it checks the idempotency ledger and raw-event log
4. if the event is new, it writes the raw event to `widget.raw_match_events`
5. it marks the event as `pending` in `widget.ingest_event_ledger`
6. it updates the serving tables and any affected document payloads
7. it invalidates match-scoped Redis keys
8. it marks the event as `applied`
9. the frontend sees the new state on the next poll or next tab fetch

This separation is intentional:

- read paths are optimized for serving widget endpoints
- write paths are optimized for replayability, crash recovery, and determinism

## 4. The provider seam

The provider seam is the boundary that made Cycle 2 possible without rewriting the frontend contract.

The interface lives in [backend/providers/base.py](/C:/Users/Administrator/Downloads/Widget project/backend/providers/base.py:1). It defines methods like:

- `get_match_state`
- `get_competition_table`
- `get_competition_fixtures`
- `get_match_xg_race`
- `get_match_squads`
- `get_match_team_stats`
- `get_match_h2h`
- `get_match_h2h_players`
- `get_match_facts`

The registry in [backend/providers/registry.py](/C:/Users/Administrator/Downloads/Widget project/backend/providers/registry.py:1) chooses one concrete implementation based on `WIDGET_PROVIDER`:

- `mock` -> `MockDataProvider`
- `clickhouse` -> `ClickHouseDataProvider`

This design keeps the handlers stable. For example, [backend/handlers/state.py](/C:/Users/Administrator/Downloads/Widget project/backend/handlers/state.py:1) still does the same high-level job it did before:

- set the TTL headers
- call `self.provider.get_match_state(match_id)`
- validate required fields
- return the standard envelope

That means the public API surface remains anchored in the handler layer, while data plumbing can evolve underneath it.

## 5. Redis cache: what is cached and why

Redis exists here to absorb the hottest widget reads and to align backend behavior with the public TTL contract already defined in `API.md`.

### Why Redis is not just a nice-to-have in this repo

The frontend polls match state frequently, and some tabs are refreshed during live play. Without a cache layer, every widget request would hit ClickHouse directly even when the API contract already says the data can be served stale for a small bounded interval.

### How the cache is implemented

[backend/services/cache.py](/C:/Users/Administrator/Downloads/Widget project/backend/services/cache.py:1) provides:

- an in-memory fallback backend for local/non-Redis runs
- a minimal Redis RESP client implementation for real Redis use
- key builders under `CacheKeys`
- `get_or_set` and pattern-based invalidation helpers

The ClickHouse provider uses this service directly. The pattern is:

1. compute a stable cache key
2. try Redis
3. on miss, query ClickHouse
4. serialize the JSON result back into Redis with the documented TTL

### Current TTL policy

The implementation mirrors the public cache semantics:

- match state: 5 seconds
- xG race: 10 seconds
- facts: 15 seconds
- match team stats: 120 seconds for `live`
- team stats: 120 seconds
- competition fixtures: 60 seconds
- competition table: 300 seconds
- H2H and H2H players: 300 seconds
- squads: 60 seconds

One subtle choice is worth calling out: `match_team_stats` only caches the `live` split in the ClickHouse provider. Other splits are read directly from the document payload. That reflects the fact that the live split is the one expected to change during replay-driven match progression.

### Invalidation policy

When replay updates a match, `ReplayService` calls `invalidate_match_live_keys(match_id)`, which deletes every Redis key with that match prefix.

That is deliberately simple and coarse:

- it avoids stale live state
- it does not need per-resource dependency tracking
- it matches the scope of replay events, which are match-centric

This is a good trade-off for a demo/prototype, even though a production system might adopt more selective invalidation.

## 6. ClickHouse schema: why each table exists

Cycle 2 does not store everything as a single JSON blob. It uses a mixed strategy:

- normalized serving tables where the access pattern is clearly row-oriented
- document snapshots where the payload is nested and mostly read whole
- a raw append-only event log for rebuild and audit
- an idempotency ledger for ingest control

The schema lives in [sql/001_init.sql](/C:/Users/Administrator/Downloads/Widget project/sql/001_init.sql:1).

### `widget.raw_match_events`

Purpose:

- append-only event log
- replay/audit source of truth for the demo ingest path
- rebuild source for live serving tables

Columns:

- `match_id`
- `event_id`
- `event_ts`
- `event_type`
- `payload_json`

This is the table that makes "rebuild from raw" possible.

### `widget.ingest_event_ledger`

Purpose:

- idempotency control
- crash recovery
- observability for replay progress and failure state

Columns:

- `event_id`
- `match_id`
- `status`
- `updated_at`
- `last_error`

This is the repo's ingest ledger. It answers "have we seen this event?" and "did we finish applying it?"

### `widget.match_state_latest`

Purpose:

- serve the latest scoreboard/header state per match

This table is optimized for the endpoint that polls the most. It stores the newest known state row for a match and uses a replacing engine so readers can select the latest logical version.

### `widget.match_xg_events`

Purpose:

- store ordered xG time-series rows for chart rendering

This is naturally append-like: each new point extends the series.

### `widget.match_facts`

Purpose:

- store ordered match facts/commentary rows

The schema includes `sort_index`, `fact_ts`, `category`, and `event_type`, which lets the API preserve presentation order and still support filtering.

### `widget.competition_table_rows`

Purpose:

- store competition standings snapshots in row form

This is a good OLAP fit because table rows are naturally queryable and sortable by competition, snapshot, and position.

### `widget.competition_fixture_rows`

Purpose:

- store competition fixtures/results snapshots in row form

This similarly benefits from a row model because the endpoint filters by competition and sometimes by status.

### `widget.widget_documents`

Purpose:

- hold nested snapshot documents that are not worth deeper normalization in this repo

Today this table backs payloads such as:

- squads
- match team stats
- team stats
- H2H
- a fallback facts document

The rule of thumb is simple: if the widget consumes a nested payload mostly as a whole document, the repo stores it as a document.

## 7. Why some resources are normalized and others are documents

This is one of the more important design choices in Cycle 2.

The repo is not trying to prove "everything belongs in one perfect relational model." Instead, it is matching storage shape to access pattern.

Normalized tables are used where:

- ordering and filtering matter
- row-level scans are natural
- the endpoint shape maps cleanly to rows

That is why:

- standings live in `competition_table_rows`
- fixtures live in `competition_fixture_rows`
- facts and xG live in append-style event tables

Document storage is used where:

- the payload is nested
- the widget reads it whole
- writes are infrequent or low-volume
- extra normalization would mostly add complexity without improving reads

That is why:

- squads
- H2H player payloads
- aggregate team stats documents

are still stored in `widget_documents`.

This is a very pragmatic OLAP-oriented schema choice, not an accident.

## 8. Replicated tables and Keeper

### The topology

The local Cycle 2 stack uses:

- one logical shard
- two ClickHouse replicas
- one Keeper node

You can see this in [docker-compose.yml](/C:/Users/Administrator/Downloads/Widget project/docker-compose.yml:1) and the ClickHouse config under `docker/clickhouse/`.

Replica-specific macros are defined as:

- shard `01`
- replica `clickhouse1` or `clickhouse2`

Those macros are then referenced in the replicated table engines:

- `ReplicatedMergeTree('/clickhouse/tables/{shard}/...', '{replica}')`
- `ReplicatedReplacingMergeTree('/clickhouse/tables/{shard}/...', '{replica}', version_column)`

### What Keeper is doing here

Keeper is the coordination service for the replicated tables. In practical terms, it stores the metadata the replicas need to agree on:

- replication paths
- replica identity
- log/snapshot coordination state

Without Keeper, the replicated table engines in this repo would not have a shared coordination layer.

### Why one Keeper node is acceptable here but not ideal in production

For this repo:

- it keeps the demo lightweight
- it is enough to exercise replicated-table mechanics

For production:

- a single Keeper node is a single point of failure
- you would usually run an odd-sized ensemble, commonly 3 nodes

The README already reflects that production recommendation.

### Why replicas instead of sharding

The candidate-style problem here is mainly about:

- availability
- failover behavior
- operational recovery

not about large-scale horizontal distribution. So the repo chooses replica redundancy over distributed-query complexity.

## 9. Read failover behavior

The ClickHouse HTTP client in [backend/services/clickhouse_http.py](/C:/Users/Administrator/Downloads/Widget project/backend/services/clickhouse_http.py:1) is intentionally simple and explicit.

It accepts a list of hosts, and for each request it:

1. tries the first host
2. if that host errors or times out, tries the next
3. raises only if every configured host fails

This means reads are "freshness-first" and "ordered-host fallback," not balanced round-robin reads across replicas.

That choice aligns with the demo goals:

- keep behavior predictable
- keep implementation small
- show continuity during node loss

It does not try to implement stronger guarantees like global sequential consistency across replicas. That would be a different design problem.

## 10. Write behavior and quorum

The ClickHouse HTTP client also supports runtime `insert_quorum` injection on write queries.

In this repo's Compose setup:

- `INSERT_QUORUM=1`

That means writes are intentionally easy to accept in local/demo mode, even if one replica is down.

This is important for the failover demo: if one replica stops, replay can still continue through the surviving node.

The trade-off is obvious:

- easier availability in local/demo mode
- weaker durability guarantees than a higher quorum

The repo documentation is upfront that production would likely raise quorum for the most important writes if the latency budget permits it.

## 11. Replay worker: what it actually does

The replay worker is the repo's deterministic ingest engine.

The implementation lives mainly in:

- [backend/services/replay_service.py](/C:/Users/Administrator/Downloads/Widget project/backend/services/replay_service.py:1)
- [backend/worker/replay.py](/C:/Users/Administrator/Downloads/Widget project/backend/worker/replay.py:1)
- [backend/worker/events.py](/C:/Users/Administrator/Downloads/Widget project/backend/worker/events.py:1)

### Why replay exists

Instead of building a queue, a consumer group, and a complex event vocabulary, this repo uses a deterministic demo event stream that mirrors resource updates the widget actually cares about:

- match state changes
- xG points
- facts
- live team stats

That makes the live demo:

- reproducible
- easy to reset
- easy to reason about
- easy to rebuild from raw

### Batching policy

The worker does not flush every event immediately by default. It batches conservatively:

- flush when there are 2 queued events, or
- flush when the oldest queued event is 250 ms old

That is not a throughput-maximizing strategy. It is a small, explicit stance on batching that keeps local behavior deterministic while still showing that the system thinks in batches rather than purely one-row-at-a-time.

### Event application sequence

For each event:

1. check ledger status
2. if already `applied`, skip it
3. if raw event is missing, insert it into `raw_match_events`
4. mark ledger row as `pending`
5. update `match_state_latest`
6. append xG/fact rows if that event contributes them and they are not already present
7. update the live portion of the `match_team_stats:{match_id}` document if present
8. invalidate Redis match keys
9. mark ledger row as `applied`

This ordering is one of the key architectural choices in the repo.

## 12. The idempotency ledger

The idempotency ledger is the mechanism that makes replay safe across retries and partial failures.

### What problem it solves

Imagine the worker crashes after:

- writing the raw event, but before
- fully updating the serving tables

Without a ledger and existence checks, a retry could double-apply the logical update.

### How this repo avoids that

It combines three checks:

1. `ingest_event_ledger` tracks whether an event is already `applied`
2. `raw_match_events` tracks whether the raw event was already persisted
3. serving tables like `match_xg_events` and `match_facts` carry `source_event_id`, so replay can detect whether that logical write already happened

That means the system can recover from "raw persisted, serving update interrupted" without blindly duplicating logical side effects.

### What it is not trying to solve

This is not a full concurrent multi-writer coordination scheme.

The repo explicitly supports:

- one replay worker
- retries
- crash recovery

It does not claim to support:

- many concurrent workers racing on the same event stream
- distributed exactly-once semantics across multiple independent writers

That limitation is explicit and appropriate for the scope.

## 13. Rebuild from raw

The rebuild path lives in [scripts/rebuild_from_raw.py](/C:/Users/Administrator/Downloads/Widget project/scripts/rebuild_from_raw.py:1) and delegates to `ReplayService.rebuild_from_raw()`.

### What rebuild does

It:

1. truncates the live serving tables:
   - `widget.match_state_latest`
   - `widget.match_xg_events`
   - `widget.match_facts`
2. reads `widget.raw_match_events` in event order
3. replays those raw payloads back through the serving-table update logic
4. clears cache keys before and after the rebuild

### What rebuild is for

This is the recovery path for reconstructed live state, especially after:

- a restore
- an intentional serving-table clear
- a partial failure that left live tables suspect

The important nuance is that rebuild does not reseed from mock JSON. It rebuilds from the persisted raw event stream.

That is exactly what makes `raw_match_events` operationally meaningful instead of just archival.

## 14. Seed vs replay vs rebuild

These three flows are related but not identical:

### Seed

`backend/worker/seed.py` loads the baseline mock data into ClickHouse:

- latest state
- initial xG rows
- initial facts
- standings snapshot
- fixtures snapshot
- document payloads

This gives the ClickHouse-backed provider a known starting point.

### Replay

Replay applies incremental demo updates on top of that baseline.

### Rebuild

Rebuild reconstructs only the live serving state from `raw_match_events` without going back to the mock files.

That separation is a healthy design because:

- seed initializes baseline reference data
- replay simulates live change
- rebuild recovers live state from persisted event history

## 15. Backup and restore

The operational scripts are:

- [scripts/backup_clickhouse.py](/C:/Users/Administrator/Downloads/Widget project/scripts/backup_clickhouse.py:1)
- [scripts/restore_clickhouse.py](/C:/Users/Administrator/Downloads/Widget project/scripts/restore_clickhouse.py:1)

### Backup strategy

Backups are JSON exports of the widget tables. The backup script:

1. creates a timestamped backup directory
2. runs `SELECT *` against each table
3. writes each table to a JSON file
4. writes a `manifest.json`
5. updates `latest.json`
6. prunes older backups based on retention count

The Compose stack also includes a `backup` service that runs this on a schedule and writes to the `backups-data` volume.

### Why this backup strategy is reasonable here

This is not pretending to be a production-grade snapshot orchestration system. It is a runnable operational story for the assessment:

- simple
- inspectable
- easy to test
- independent of extra infrastructure

### Restore strategy

The restore script:

1. ensures schema exists
2. truncates all widget tables on all hosts
3. reads the backup JSON files
4. re-inserts rows into the corresponding tables

This restores stored state, but if you specifically want to reconstruct the live serving tables from raw replay history after a restore, you can still run rebuild-from-raw as a separate recovery step.

### Replication vs backup

This repo correctly treats these as different protections:

- replication protects against node loss
- backup/restore protects against bad writes, accidental destructive operations, or broader table loss

That distinction is important and often misunderstood.

## 16. Failover story

The repo's failover demo is intentionally concrete rather than theoretical. See [scripts/failover_demo.sh](/C:/Users/Administrator/Downloads/Widget project/scripts/failover_demo.sh:1).

The script does this:

1. reset replay state
2. stop `clickhouse1`
3. apply the next replay event through the API
4. read live state through the API while one replica is down
5. start `clickhouse1` again
6. wait for the node to accept HTTP requests
7. query `system.replicas` to inspect replication health
8. read live state again

### What the demo is proving

It is proving that:

- the API can continue serving when one configured ClickHouse host is unavailable
- replay writes can still progress in this demo topology because write quorum is 1
- the restarted replica can rejoin the replicated-table topology

### What it is not proving

It is not proving:

- zero data loss under every possible split-brain or Keeper failure mode
- production-grade quorum policy
- multi-node Keeper resilience

That is fine. The repo is clear about where it is production-shaped and where it is intentionally simplified.

## 17. How the frontend/demo interacts with the backend

The frontend is not a separate SPA. It is an embeddable widget plus a demo host page.

### Loader boot path

[frontend/loader.js](/C:/Users/Administrator/Downloads/Widget project/frontend/loader.js:1) is the entry point.

It:

1. resolves config from the loader script tag
2. derives the API base
3. loads `renderers.js`, `canvas_chart.js`, and `container.js`
4. fetches initial match state for match pages
5. optionally fetches squads to enrich context with team ids
6. instantiates `WidgetContainer`
7. registers tab definitions and their endpoint bindings
8. starts polling state for match pages

### Container responsibilities

[frontend/container.js](/C:/Users/Administrator/Downloads/Widget project/frontend/container.js:1) owns widget state and lifecycle:

- shell rendering
- active tab management
- phase visibility rules
- polling
- tab refresh on live updates
- visible error/retry states

This is where phase transitions become UI behavior:

- pre-match-only tabs can hide during live play
- live-only tabs like `xg-race` can appear when the phase enters live play
- squads can switch from pre-match roster mode to live pitch/formation mode

### Renderer responsibilities

[frontend/renderers.js](/C:/Users/Administrator/Downloads/Widget project/frontend/renderers.js:1) turns API payloads into DOM for:

- standings
- fixtures
- team stats
- H2H
- facts
- squads
- live formation/pitch view

The frontend is therefore split cleanly into:

- boot/orchestration
- container/state
- rendering

### Demo page behavior

[frontend/index.html](/C:/Users/Administrator/Downloads/Widget project/frontend/index.html:1) is the demo host page served at `/example`.

It does two different things:

1. host-page simulation
   - shows how a third-party page would embed the widget
   - passes context through `data-*` attributes
2. demo controls
   - local phase override buttons
   - auto-simulate controls
   - backend replay reset/step buttons

That second set of controls is where the frontend and backend architecture meet most visibly.

When the user clicks "Replay Next Backend Event":

1. the page POSTs to `/api/admin/replay/step`
2. the backend applies the next replay event
3. the page then calls `pollMatchState()`
4. the widget sees the updated state and refreshes the live-sensitive tab content

So the demo is not just changing frontend mocks. It can exercise the actual replay, cache invalidation, and ClickHouse-backed read path.

## 18. The Tornado layer is still the contract owner

Even though Cycle 2 is mostly about storage and operations, the Tornado layer is still structurally important.

[backend/server.py](/C:/Users/Administrator/Downloads/Widget project/backend/server.py:1) does three distinct jobs:

- wire the API routes
- construct runtime services like provider/cache/replay
- serve the frontend demo/static assets

That makes the API server the meeting point of:

- public widget contract
- data-provider configuration
- admin replay controls
- demo page hosting

The handler base class in [backend/handlers/base.py](/C:/Users/Administrator/Downloads/Widget project/backend/handlers/base.py:1) is what keeps the external contract consistent:

- CORS
- JSON content type
- cache headers
- response envelope
- error envelope

This is why the frontend does not need to care whether the backend is in `mock` mode or `clickhouse` mode.

## 19. A useful mental model of the whole architecture

If you want one compact model of the system, use this:

- the handlers define the contract
- the provider seam hides the storage implementation
- Redis protects the hot read path
- ClickHouse stores both serving state and replayable history
- Keeper coordinates replicated tables
- the replay worker is the write/update path
- the ledger and raw log make replay safe to retry
- rebuild-from-raw reconstructs live state
- backup/restore protects against broader storage failures
- the frontend demo exercises all of this through a stable browser contract

## 20. What is intentionally simplified vs production-shaped

### Production-shaped ideas in this repo

- provider abstraction under stable handlers
- explicit cache layer with TTL alignment
- replicated ClickHouse tables
- raw event log plus idempotency ledger
- app-level host failover
- scheduled backup flow
- rebuild-from-raw recovery story

### Intentional simplifications

- one shard only
- a single Keeper node
- write quorum set to 1 for demo convenience
- deterministic replay events instead of a real upstream feed
- single replay worker instead of concurrent ingestion
- JSON export/import backups rather than object-storage snapshots
- some nested resources still stored as documents instead of fully normalized tables

These are sensible simplifications. They keep the repo runnable and explainable while still demonstrating the right architectural instincts.

## 21. If you are reading the code for the first time

The shortest productive reading order is:

1. [backend/server.py](/C:/Users/Administrator/Downloads/Widget project/backend/server.py:1)
2. [backend/handlers/base.py](/C:/Users/Administrator/Downloads/Widget project/backend/handlers/base.py:1)
3. [backend/providers/base.py](/C:/Users/Administrator/Downloads/Widget project/backend/providers/base.py:1)
4. [backend/providers/registry.py](/C:/Users/Administrator/Downloads/Widget project/backend/providers/registry.py:1)
5. [backend/providers/clickhouse.py](/C:/Users/Administrator/Downloads/Widget project/backend/providers/clickhouse.py:1)
6. [backend/services/cache.py](/C:/Users/Administrator/Downloads/Widget project/backend/services/cache.py:1)
7. [backend/services/clickhouse_http.py](/C:/Users/Administrator/Downloads/Widget project/backend/services/clickhouse_http.py:1)
8. [backend/services/replay_service.py](/C:/Users/Administrator/Downloads/Widget project/backend/services/replay_service.py:1)
9. [sql/001_init.sql](/C:/Users/Administrator/Downloads/Widget project/sql/001_init.sql:1)
10. [frontend/loader.js](/C:/Users/Administrator/Downloads/Widget project/frontend/loader.js:1)
11. [frontend/container.js](/C:/Users/Administrator/Downloads/Widget project/frontend/container.js:1)
12. [frontend/renderers.js](/C:/Users/Administrator/Downloads/Widget project/frontend/renderers.js:1)
13. [frontend/index.html](/C:/Users/Administrator/Downloads/Widget project/frontend/index.html:1)

If you read in that order, the architecture will usually "click" faster than if you start from the SQL alone or the frontend alone.

## 22. Bottom line

Cycle 1 proved the widget contract and embed model.

Cycle 2 keeps that contract intact, then adds a more serious backend architecture under it:

- provider indirection
- Redis-backed hot reads
- ClickHouse serving tables plus raw replay history
- replicated storage coordinated by Keeper
- replay-driven updates
- idempotent ingest tracking
- rebuild-from-raw recovery
- scheduled backup/restore
- demoable failover

That is the core story of this repo.
