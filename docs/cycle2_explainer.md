# Cycle 2 Explainer

## Who this is for

This document is for someone who:

- understands Python and SQL
- knows the basic ideas behind caching, OLAP systems, replication, and client-server architecture
- can read code, but does not yet have a strong mental model of this repo

I also need to be explicit about one limitation: I could not reliably fetch the LinkedIn profile URL that was shared because LinkedIn blocked access from this environment. The tailoring here is based on your resume, your questions, and the way you reasoned through the project with me.

## How this maps to your background

Your background is actually a strong fit for understanding this repo.

If you think in data-platform terms, the project maps roughly like this:

- Tornado handlers are the API-facing delivery layer
- provider methods are like domain-facing access contracts
- ClickHouse serving tables are like small serving marts
- `widget_documents` is a lightweight document zone for nested payloads
- `raw_match_events` is a replayable bronze-like event history
- the replay service is a deterministic micro-batch update job
- Redis is a low-latency cache in front of the serving layer
- `/example` is an operator-facing validation surface

Another useful framing:

- Cycle 1 was like serving product behavior from static extracts
- Cycle 2 is like serving it from a live warehouse plus cache plus replayable update path

So the biggest new thing here is not the data ideas themselves. The new thing is how they are packaged into a small backend service architecture.

## The short version

Cycle 1 was mostly a widget and API contract prototype backed by mock JSON files.

Cycle 2 keeps the same public API and frontend behavior, but swaps the backend internals so the system behaves much more like a real live-data service:

- requests still hit the same Tornado API routes
- handlers still return the same response shapes
- but data now flows through a provider layer
- the main provider reads from ClickHouse instead of local JSON
- Redis caches hot responses
- a replay worker simulates incoming live events
- replayed events update database tables and invalidate cache
- backups, restore, failover, and recovery tooling now exist

The core idea is:

**we preserved the product contract while replacing the data engine underneath it**

## The system at a glance

```text
Browser / Widget
    |
    v
Tornado API handlers
    |
    v
Provider registry
    |--------------------> Mock provider (Cycle 1 behavior)
    |
    `-------------------> ClickHouse provider (Cycle 2 behavior)
                               |
                               +--> Redis cache
                               |
                               `--> ClickHouse tables
                                         |
                                         +--> raw event log
                                         +--> serving tables
                                         `--> document snapshots

Replay worker
    |
    v
raw events + serving updates + cache invalidation
```

## What problem Cycle 2 is solving

Mock JSON is great for:

- frontend development
- API shape iteration
- smoke testing

Mock JSON is weak for:

- live updates
- recovery after partial failures
- replica failover
- backups
- cache invalidation
- reasoning about event-driven state changes

Cycle 2 is the step where the project becomes operationally believable.

## What did not change

We intentionally did **not** change:

- API routes
- response envelope shape
- cache-control TTL headers
- frontend widget behavior
- the ability to fall back to the mock provider

This is a classic backend migration strategy:

**keep the surface area stable, replace the internals gradually**

## The provider seam

Before the refactor, handlers were too close to the mock JSON files.

That makes migration hard because every handler knows too much about where data lives.

So we introduced a provider layer:

- handlers ask for data by meaning
- providers decide where the data comes from

Examples:

- match state
- competition table
- xG race
- facts

The handler no longer cares whether the answer came from:

- a local JSON file
- ClickHouse
- a cache
- something else later

This is useful because it:

- keeps handlers focused on HTTP concerns
- isolates data-access logic
- preserves rollback to `mock`
- makes testing easier
- makes future data-source changes less invasive

The provider seam is the architectural hinge that made the rest of Cycle 2 possible.

## How one request flows now

Let's use:

`GET /api/v1/match/12345/state`

### Step 1: browser calls the API

The widget or example page requests match state.

### Step 2: Tornado routes to the state handler

The handler still does HTTP-oriented work:

- validate inputs
- choose TTL headers
- format the response envelope
- handle errors consistently

### Step 3: handler asks the provider for state

The handler does not load files directly anymore.

It asks the active provider:

- mock provider in mock mode
- ClickHouse provider in ClickHouse mode

### Step 4: ClickHouse provider checks Redis

For hot endpoints like state:

- first look in Redis
- if cache hit, return fast
- if cache miss, query ClickHouse

### Step 5: provider queries the serving table

It reads from the live-serving table that stores the latest known state for a match.

### Step 6: provider stores the fresh result in Redis

It writes the response into Redis with the endpoint's TTL.

### Step 7: handler wraps and returns it

The handler emits the same public JSON contract as before.

That is the key principle:

**the client sees continuity while the backend uses a more realistic data path**

## Why Redis is here

Redis is not the system of record.

ClickHouse is where the durable data lives.

Redis is here because some reads are:

- frequent
- repetitive
- latency-sensitive

Examples:

- match state
- xG race
- facts
- live team stats

Redis gives us:

- lower latency
- less repeated load on ClickHouse
- TTL-based freshness control
- explicit invalidation when replay events arrive

### What TTL-based cache means here

If `state` has a short TTL, then:

- repeated reads within that window are cheap
- after the TTL expires, the next read refreshes from ClickHouse

But TTL alone is not enough for live data.

So the replay path also invalidates match-scoped live keys when an event changes the match.

That means the system uses:

- time-based freshness
- plus event-based invalidation

That combination is much stronger than waiting for the cache to expire by itself.

## Why ClickHouse

ClickHouse is an OLAP-oriented database.

That makes it a good fit for:

- analytical read patterns
- append-heavy event tables
- derived serving tables
- time-ordered sports/event data
- replication demos

It is not being used here as "the perfect database for everything."

It is being used because this project needs to plausibly support:

- replayable events
- queryable history
- predictable live reads
- backup and failover

## How the data is modeled

The system has three kinds of storage.

### 1. Raw event log

Table:

- `widget.raw_match_events`

Purpose:

- durable replay history
- audit trail
- recovery source

Think of this as:

"what happened?"

### 2. Serving tables

Tables:

- `widget.match_state_latest`
- `widget.match_xg_events`
- `widget.match_facts`
- `widget.competition_table_rows`
- `widget.competition_fixture_rows`

Purpose:

- fast reads shaped around API needs

Think of these as:

"what should the API read quickly?"

These are not raw logs. They are query-friendly tables built around endpoint access patterns.

### 3. Snapshot document table

Table:

- `widget.widget_documents`

Purpose:

- store nested payloads that are still easiest to serve as snapshots

Used for things like:

- squads
- H2H payloads
- team aggregate stats

## Why some resources are normalized and others are not

We did **not** normalize every resource just because "relational is good."

Instead:

- live mutable data that benefits from analytical querying was normalized
- slower nested payloads stayed snapshot-shaped

Good candidates for normalization:

- match state
- xG points
- facts feed
- competition table rows
- competition fixtures

Good candidates to keep as snapshots:

- squads
- H2H structures
- some aggregate team stats payloads

This is a pragmatic architecture choice, not a purity choice.

## Replication, replicas, and Keeper

There are two ClickHouse replicas:

- `clickhouse1`
- `clickhouse2`

They are copies of the same logical tables.

If one replica goes down, the API can keep reading from the other.

ClickHouse Keeper coordinates the replicated tables. It stores the metadata replicas need to agree on things like:

- replica identity
- replication paths
- replication state

One of the runtime issues we debugged came from Keeper state not being persisted across full volume resets. That caused replicas to restart in a broken readonly posture because:

- ClickHouse data volumes still existed
- but Keeper's coordination state did not

Persisting Keeper fixed the topology so cold restarts behave properly.

Why two replicas and not shards:

- the assignment is about resilience and operational judgment
- replicas solve availability and failover
- shards would add complexity with little benefit here

So the design intentionally chooses:

**one shard, two replicas**

## What the replay worker does

The replay worker simulates incoming live events.

Instead of integrating with a real feed or queue, it replays scripted events. That is a good design for this assessment because it gives:

- deterministic demos
- repeatability
- lower operational complexity
- a clear end-to-end live update story

An event can include slices such as:

- updated match state
- an xG point
- a fact feed item
- live team stats

This is intentionally close to the API resource model.

## Event application order

When an event is processed, the system conceptually does this:

1. check whether the `event_id` is already applied
2. if not, write raw event data
3. mark the ingest ledger as `pending`
4. update serving tables and any needed live documents
5. invalidate match-scoped Redis keys
6. mark the ingest ledger as `applied`

That ordering matters because it gives recovery semantics.

## What the ingest ledger is for

Table:

- `widget.ingest_event_ledger`

Purpose:

- track whether an event is pending or applied
- support retry and crash recovery
- make idempotency explicit

Without this, a crash in the middle of applying an event could leave you uncertain about whether retrying would duplicate the logical effect.

## Idempotency in plain English

Idempotency means:

**if the same event is replayed more than once, it should not produce the logical effect more than once**

In this repo, that is handled through:

- `event_id`
- raw-event existence checks
- ledger status
- `source_event_id` checks in serving tables

Important nuance:

This repo's idempotency model is designed for:

- replay retries
- crash recovery
- the single replay worker model

It is **not** a full multi-writer distributed ingestion system.

That boundary is intentional and documented.

## Batching

The worker does not flush every event individually as its final design.

Instead it uses a very small conservative batch policy:

- flush after `2` events
- or after `250ms`

This is not about throughput benchmarking. It is about:

- deterministic local behavior
- visible live updates
- a concrete answer to "what is your batching policy?"

This is a good example of "production-shaped but simplified."

## Rebuild-from-raw

This is one of the key operator-oriented features.

Script:

- `scripts/rebuild_from_raw.py`

Purpose:

- clear the live serving tables
- read raw events in deterministic order
- rebuild live serving state from the raw log

This proves the raw event log is useful for recovery, not just for storage.

### Current behavior

The seed path now writes a synthetic baseline event history into `raw_match_events`.

That means rebuild-from-raw can reconstruct:

- the seeded live baseline
- later replayed live mutations

So the rebuild story is now:

- seed establishes the initial world
- raw events preserve the rebuildable live history
- replay adds incremental mutations
- rebuild replays the baseline plus mutations back into the live serving tables

If you rebuild immediately after a clean reset, you should now see a non-zero replay count because the baseline itself is represented as raw events.

## Backup and restore

Scripts:

- `scripts/backup_clickhouse.py`
- `scripts/restore_clickhouse.py`

Backup does this:

- export key widget tables as JSON files
- write them into a timestamped backup directory
- generate a manifest
- update `latest.json`
- prune older backups beyond the retention limit

Restore does this:

- ensure schema exists
- truncate current tables
- load rows back from a chosen backup directory

Compose also runs a scheduled `backup` service that writes into a Docker volume.

`latest.json` matters because it gives a lightweight machine-readable health artifact that tells you:

- whether the latest backup succeeded
- when it ran
- which directory it wrote
- how many rows/tables were included

Replication and backup solve different problems:

- replication protects against node loss
- backup/restore protects against bad writes or broader storage loss

## Failover

The failover script demonstrates:

- one replica can go down
- replay can still happen
- the API still serves state
- the replica can come back
- replication health can be checked again

This matters because redundancy is not just about "having two containers." It is about proving the system still behaves sensibly when one copy disappears.

## Why the example page matters

`/example` is not just a demo page.

It is effectively a small operator console for this exercise.

It helps prove:

- the widget still renders through the same public contract
- the backend replay path changes what the widget sees
- resets and replay steps are visible without manual database inspection

That makes it easier to connect:

- infrastructure work
- backend work
- user-visible behavior

## The most important code areas to read first

If you want to understand the system without reading every file, read in this order:

1. `backend/server.py`
2. `backend/providers/registry.py`
3. `backend/providers/clickhouse.py`
4. `backend/services/clickhouse_http.py`
5. `backend/services/replay_service.py`
6. `backend/worker/seed.py`
7. `sql/001_init.sql`
8. `scripts/backup_clickhouse.py`
9. `scripts/restore_clickhouse.py`
10. `scripts/rebuild_from_raw.py`

Why this order works:

- first understand runtime wiring
- then understand data access
- then understand storage
- then understand operations

## What changed from a software-engineering perspective

This repo went through a classic transition.

Before:

- tightly coupled mock reads
- simpler demo behavior
- less operational realism

After:

- decoupled provider layer
- cache-aware read path
- replicated database topology
- event replay
- recovery tooling
- backup/restore
- failover demo

This is not "just more code."

It is a shift from:

**prototype data plumbing**

to:

**small but coherent service architecture**

## The biggest idea to internalize

If you only remember one thing, make it this:

The system now separates three concerns that were previously blended together:

1. **HTTP contract**
   - handlers, validation, envelopes, TTL headers

2. **Data access**
   - provider seam, cache, ClickHouse reads

3. **State change / live ingestion**
   - replay worker, raw events, serving updates, invalidation, recovery

That separation is why the architecture now feels much more real.

## Residual gaps you should know about

This project is in good shape, but not perfect.

The biggest architectural gap has been closed: rebuild-from-raw can now restore the seeded live baseline because seed writes synthetic baseline events into the raw log.

What remains are smaller caveats:

- the ingest topology is intentionally single-worker, not multi-writer
- some resources remain document-backed by design
- the local backup flow is practical, not full production ops
- the batching policy is small and demo-oriented, not throughput-optimized
- the local topology still uses a single Keeper node

These are reasonable tradeoffs for the assignment, but they are worth understanding.

## If you want to build intuition by running things

Try this sequence:

1. open `/example`
2. hit replay reset
3. inspect `/api/v1/match/12345/state`
4. hit replay step
5. inspect state again
6. inspect xG race or facts
7. run backup
8. run failover demo
9. run rebuild-from-raw

That sequence maps the architecture to visible behavior.

## Final mental model

Think of the system like this:

- **Tornado handlers** are the HTTP shell
- **providers** are the data-source abstraction
- **Redis** is the fast front cache
- **ClickHouse** is the durable analytical store
- **raw events** are the replayable history
- **serving tables** are optimized answers for the widget
- **the replay worker** is the simulated live feed
- **the ledger** is the safety record for ingest
- **backup/restore/rebuild** are the recovery toolbox
- **replicas + Keeper** are the resilience layer

That is the core of what we built in Cycle 2.
