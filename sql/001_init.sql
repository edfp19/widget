CREATE DATABASE IF NOT EXISTS widget;

CREATE TABLE IF NOT EXISTS widget.raw_match_events
(
    match_id String,
    event_id String,
    event_ts DateTime64(3),
    event_type LowCardinality(String),
    payload_json String
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/raw_match_events', '{replica}')
PARTITION BY toDate(event_ts)
ORDER BY (match_id, event_ts, event_id);

CREATE TABLE IF NOT EXISTS widget.ingest_event_ledger
(
    event_id String,
    match_id String,
    status LowCardinality(String),
    updated_at DateTime64(3),
    last_error String
)
ENGINE = ReplicatedReplacingMergeTree(
    '/clickhouse/tables/{shard}/ingest_event_ledger',
    '{replica}',
    updated_at
)
ORDER BY (event_id);

CREATE TABLE IF NOT EXISTS widget.match_state_latest
(
    match_id String,
    version_ts DateTime64(3),
    competition_id String,
    phase LowCardinality(String),
    clock UInt16,
    home_score UInt8,
    away_score UInt8,
    home_team String,
    away_team String,
    lineups_confirmed UInt8,
    kickoff_utc String
)
ENGINE = ReplicatedReplacingMergeTree(
    '/clickhouse/tables/{shard}/match_state_latest',
    '{replica}',
    version_ts
)
ORDER BY (match_id);

CREATE TABLE IF NOT EXISTS widget.match_xg_events
(
    match_id String,
    source_event_id String,
    event_ts DateTime64(3),
    minute UInt16,
    home_team String,
    away_team String,
    home_xg_cumulative Float32,
    away_xg_cumulative Float32
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/match_xg_events', '{replica}')
PARTITION BY toDate(event_ts)
ORDER BY (match_id, source_event_id, minute, event_ts);

CREATE TABLE IF NOT EXISTS widget.match_facts
(
    match_id String,
    source_event_id String,
    fact_id String,
    sort_index UInt32,
    fact_ts DateTime64(3),
    minute UInt16,
    category LowCardinality(String),
    text String,
    event_type LowCardinality(String)
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/match_facts', '{replica}')
PARTITION BY toDate(fact_ts)
ORDER BY (match_id, source_event_id, sort_index, fact_ts, fact_id);

CREATE TABLE IF NOT EXISTS widget.competition_table_rows
(
    competition_id String,
    snapshot_ts DateTime64(3),
    position UInt16,
    previous_position UInt16,
    team_name String,
    played UInt16,
    won UInt16,
    drawn UInt16,
    lost UInt16,
    gf UInt16,
    ga UInt16,
    gd Int16,
    points UInt16,
    form_json String,
    home_json String,
    away_json String
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/competition_table_rows', '{replica}')
PARTITION BY toYYYYMM(snapshot_ts)
ORDER BY (competition_id, snapshot_ts, position);

CREATE TABLE IF NOT EXISTS widget.competition_fixture_rows
(
    competition_id String,
    snapshot_ts DateTime64(3),
    match_id String,
    fixture_date String,
    home_team String,
    away_team String,
    home_score Nullable(UInt8),
    away_score Nullable(UInt8),
    status LowCardinality(String)
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/competition_fixture_rows', '{replica}')
PARTITION BY toYYYYMM(snapshot_ts)
ORDER BY (competition_id, status, fixture_date, match_id);

CREATE TABLE IF NOT EXISTS widget.widget_documents
(
    document_key String,
    payload_json String,
    updated_at DateTime64(3)
)
ENGINE = ReplicatedReplacingMergeTree(
    '/clickhouse/tables/{shard}/widget_documents',
    '{replica}',
    updated_at
)
ORDER BY (document_key);
