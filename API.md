# API Contract

Base URL for widget endpoints: `/api/v1`

All widget endpoints are `GET` endpoints and return the same envelope:

```json
{
  "meta": {
    "endpoint": "/api/v1/...",
    "timestamp": "2026-04-18T16:35:14Z",
    "cache_ttl": 60,
    "version": "1.0"
  },
  "data": {},
  "error": null
}
```

## Embed Contract

The widget is embedded with a script tag plus a root container:

```html
<div id="sr-widget-root"></div>
<script
  src="https://widgets.sportingrisk.com/v1/loader.js"
  data-client="boylesports"
  data-page-type="match"
  data-match-id="{{page.match_id}}"
  data-theme="light"
  data-default-tab="table"
  data-visible-tabs="table,fixtures,squads,team-stats,h2h,facts,xg-race">
</script>
```

Supported `data-*` attributes:

- `data-client`: operator identifier
- `data-page-type`: `match`, `competition`, or `homepage`
- `data-match-id`: required for match pages
- `data-competition-id`: required for competition pages
- `data-theme`: `light` or `dark`
- `data-default-tab`: tab id to open first
- `data-visible-tabs`: comma-separated tab ids to register
- `data-lineup-view`: optional squads pre-live view preference, `pitch` or `list`
- `data-poll-interval-ms`: optional match-state polling interval

Notes:

- `homepage` does not require a context id in the embed itself.
- `data-visible-tabs` is optional; if omitted, the loader registers the default tab set for the current page type.
- The loader still tolerates the old `data-entity-id` fallback, but the current documented contract is `data-match-id` / `data-competition-id`.

## 1. Match State

- Path: `/api/v1/match/{match_id}/state`
- Method: `GET`
- Query params: none
- TTL: `5` seconds
- ClickHouse note: single-row object payload; easy to hydrate from a latest-state table keyed by `match_id`

Example request:

```http
GET /api/v1/match/12345/state HTTP/1.1
Host: localhost:8080
```

Example response:

```json
{
  "meta": {
    "endpoint": "/api/v1/match/12345/state",
    "timestamp": "2026-04-18T16:35:14Z",
    "cache_ttl": 5,
    "version": "1.0"
  },
  "data": {
    "match_id": "12345",
    "competition_id": "39",
    "phase": "PRE_MATCH",
    "clock": 0,
    "home_score": 0,
    "away_score": 0,
    "home_team": "Arsenal",
    "away_team": "Chelsea",
    "lineups_confirmed": false,
    "kickoff_utc": "2026-04-19T15:00:00Z"
  },
  "error": null
}
```

## 2. Competition Table

- Path: `/api/v1/competition/{competition_id}/table`
- Method: `GET`
- Query params: none
- TTL: `300` seconds
- ClickHouse note: row-shaped array; maps cleanly to one standings row per team per competition snapshot

Returned row fields include:

- core standings: `position`, `team_name`, `played`, `won`, `drawn`, `lost`, `gf`, `ga`, `gd`, `points`
- live/table helpers: `previous_position`, `form`
- split views: nested `home` and `away` objects for the frontend toggle

Example request:

```http
GET /api/v1/competition/39/table HTTP/1.1
Host: localhost:8080
```

Example response row:

```json
{
  "position": 2,
  "previous_position": 3,
  "team_name": "Arsenal",
  "played": 32,
  "won": 22,
  "drawn": 7,
  "lost": 3,
  "gf": 68,
  "ga": 24,
  "gd": 44,
  "points": 73,
  "form": ["W", "D", "W", "W", "L"],
  "home": {
    "played": 16,
    "won": 13,
    "drawn": 2,
    "lost": 1,
    "gd": 25,
    "points": 41
  },
  "away": {
    "played": 16,
    "won": 9,
    "drawn": 5,
    "lost": 2,
    "gd": 19,
    "points": 32
  }
}
```

## 3. Competition Fixtures

- Path: `/api/v1/competition/{competition_id}/fixtures`
- Method: `GET`
- Query params:
  - `status` (`string`, optional): `scheduled` or `played`
  - `limit` (`integer`, optional, default `5`): must be greater than `0`
- TTL: `60` seconds
- ClickHouse note: row-shaped array; natural fit for one fixture row per match with filterable status/date columns

Example request:

```http
GET /api/v1/competition/39/fixtures?status=played&limit=2 HTTP/1.1
Host: localhost:8080
```

## 4. xG Race

- Path: `/api/v1/match/{match_id}/xg-race`
- Method: `GET`
- Query params: none
- TTL: `10` seconds
- ClickHouse note: columnar shape already; easy to serve from aggregated arrays or ordered event rollups

Example request:

```http
GET /api/v1/match/12345/xg-race HTTP/1.1
Host: localhost:8080
```

Example response:

```json
{
  "home_team": "Arsenal",
  "away_team": "Chelsea",
  "timeline_minute": [5, 23, 31, 44, 56, 67, 78],
  "home_xg_cumulative": [0.0, 0.18, 0.18, 0.52, 0.89, 0.89, 1.24],
  "away_xg_cumulative": [0.12, 0.12, 0.41, 0.41, 0.68, 1.05, 1.05]
}
```

The frontend scopes this response to the current simulated/live clock when rendering the example page or live preview.

## 5. Squads

- Path: `/api/v1/match/{match_id}/squads`
- Method: `GET`
- Query params: none
- TTL: `60` seconds
- ClickHouse note: nested object payload; typically assembled from lineup rows plus player metadata rather than read as one raw row

Returned structure includes:

- `home` and `away` team objects
- `starting_xi`
- `bench`
- `live_events` for goal/card/substitution badges in live formation view

The frontend uses this together with `state.lineups_confirmed` and `state.phase` to produce three squads states:

- full squad list before line-ups are confirmed
- confirmed XI view before kick-off
- live pitch view with event badges

## 6. Match Team Stats

- Path: `/api/v1/match/{match_id}/team-stats`
- Method: `GET`
- Query params:
  - `split` (`string`, optional, default `season`): one of `season`, `last_5`, `last_10`, `home`, `away`, `live`
- TTL: `120` seconds
- ClickHouse note: split-based comparison payload; best modeled as pre-aggregated team-pair metric slices keyed by match context

Example request:

```http
GET /api/v1/match/12345/team-stats?split=live HTTP/1.1
Host: localhost:8080
```

Example live response:

```json
{
  "meta": {
    "endpoint": "/api/v1/match/12345/team-stats",
    "timestamp": "2026-04-18T16:38:06Z",
    "cache_ttl": 120,
    "version": "1.0"
  },
  "data": {
    "home": {
      "team_name": "Arsenal",
      "possession_pct": 57,
      "shots": 11,
      "shots_on_target": 4,
      "corners": 5,
      "fouls": 8,
      "yellow_cards": 1,
      "red_cards": 0
    },
    "away": {
      "team_name": "Chelsea",
      "possession_pct": 43,
      "shots": 7,
      "shots_on_target": 2,
      "corners": 3,
      "fouls": 10,
      "yellow_cards": 2,
      "red_cards": 0
    }
  },
  "error": null
}
```

## 7. Team Stats (Legacy / Internal Contract)

- Path: `/api/v1/team/{team_id}/stats`
- Method: `GET`
- Query params:
  - `split` (`string`, optional, default `season`): one of `season`, `last_5`, `last_10`, `home`, `away`, `live`
- TTL: `120` seconds

This route is still supported by the backend, but the match widget now prefers `/api/v1/match/{match_id}/team-stats` because that fits the page-context model more naturally.

## 8. Match H2H

- Path: `/api/v1/match/{match_id}/h2h`
- Method: `GET`
- Query params:
  - `limit` (`integer`, optional, default `5`): must be greater than `0`
- TTL: `300` seconds
- ClickHouse note: row-shaped array; natural fit for historic match rows filtered by team pair and ordered by date

## 9. H2H Players

- Path: `/api/v1/match/{match_id}/h2h/players`
- Method: `GET`
- Query params:
  - `home_player_id` (`string`, optional, default `null`): must be supplied together with `away_player_id`
  - `away_player_id` (`string`, optional, default `null`): must be supplied together with `home_player_id`
- TTL: `300` seconds
- ClickHouse note: selector response is row-derived metadata; comparison response is a two-row player matchup projected into one object

## 10. Match Facts

- Path: `/api/v1/match/{match_id}/facts`
- Method: `GET`
- Query params:
  - `category` (`string`, optional, default `null`): one of `team`, `player`, `match`, `live`
  - `limit` (`integer`, optional, default `10`): must be greater than `0`
- TTL: `15` seconds
- ClickHouse note: row-shaped event/fact array; natural fit for append-only facts tables filtered by match and category

The frontend uses `minute` on live facts so commentary can reveal progressively during live simulation instead of dumping the entire feed at kick-off.

## Health Endpoint

- Path: `/api/health`
- Method: `GET`
- Query params: none
- Response:

```json
{
  "status": "ok"
}
```
