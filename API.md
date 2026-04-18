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

Example request:

```http
GET /api/v1/competition/39/table HTTP/1.1
Host: localhost:8080
```

Example response:

```json
{
  "meta": {
    "endpoint": "/api/v1/competition/39/table",
    "timestamp": "2026-04-18T16:38:06Z",
    "cache_ttl": 300,
    "version": "1.0"
  },
  "data": [
    {
      "position": 1,
      "team_name": "Liverpool",
      "played": 32,
      "won": 24,
      "drawn": 5,
      "lost": 3,
      "gf": 75,
      "ga": 28,
      "gd": 47,
      "points": 77,
      "form": ["W", "W", "D", "W", "W"]
    },
    {
      "position": 2,
      "team_name": "Arsenal",
      "played": 32,
      "won": 22,
      "drawn": 7,
      "lost": 3,
      "gf": 68,
      "ga": 24,
      "gd": 44,
      "points": 73,
      "form": ["W", "D", "W", "W", "L"]
    },
    {
      "position": 3,
      "team_name": "Manchester City",
      "played": 32,
      "won": 21,
      "drawn": 6,
      "lost": 5,
      "gf": 71,
      "ga": 33,
      "gd": 38,
      "points": 69,
      "form": ["W", "W", "W", "L", "D"]
    },
    {
      "position": 4,
      "team_name": "Chelsea",
      "played": 32,
      "won": 18,
      "drawn": 8,
      "lost": 6,
      "gf": 60,
      "ga": 37,
      "gd": 23,
      "points": 62,
      "form": ["D", "W", "W", "W", "L"]
    },
    {
      "position": 5,
      "team_name": "Aston Villa",
      "played": 32,
      "won": 17,
      "drawn": 7,
      "lost": 8,
      "gf": 55,
      "ga": 41,
      "gd": 14,
      "points": 58,
      "form": ["W", "L", "D", "W", "W"]
    },
    {
      "position": 6,
      "team_name": "Tottenham Hotspur",
      "played": 32,
      "won": 16,
      "drawn": 6,
      "lost": 10,
      "gf": 58,
      "ga": 46,
      "gd": 12,
      "points": 54,
      "form": ["L", "W", "W", "D", "L"]
    }
  ],
  "error": null
}
```

## 3. Competition Fixtures

- Path: `/api/v1/competition/{competition_id}/fixtures`
- Method: `GET`
- Query params:
  - `status` (`string`, optional, default `null`): one of `scheduled`, `played`
  - `limit` (`integer`, optional, default `5`): must be greater than `0`
- TTL: `60` seconds
- ClickHouse note: row-shaped array; natural fit for one fixture row per match with filterable status/date columns

Example request:

```http
GET /api/v1/competition/39/fixtures?status=played&limit=2 HTTP/1.1
Host: localhost:8080
```

Example response:

```json
{
  "meta": {
    "endpoint": "/api/v1/competition/39/fixtures",
    "timestamp": "2026-04-18T16:35:14Z",
    "cache_ttl": 60,
    "version": "1.0"
  },
  "data": [
    {
      "match_id": "m_004",
      "date": "2026-04-12T15:30:00Z",
      "home_team": "Chelsea",
      "away_team": "Newcastle United",
      "home_score": 2,
      "away_score": 1,
      "status": "played"
    },
    {
      "match_id": "m_005",
      "date": "2026-04-12T13:00:00Z",
      "home_team": "Arsenal",
      "away_team": "Brighton & Hove Albion",
      "home_score": 3,
      "away_score": 0,
      "status": "played"
    }
  ],
  "error": null
}
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
  "meta": {
    "endpoint": "/api/v1/match/12345/xg-race",
    "timestamp": "2026-04-18T16:38:06Z",
    "cache_ttl": 10,
    "version": "1.0"
  },
  "data": {
    "home_team": "Arsenal",
    "away_team": "Chelsea",
    "timeline_minute": [5, 23, 31, 44, 56, 67, 78],
    "home_xg_cumulative": [0.0, 0.18, 0.18, 0.52, 0.89, 0.89, 1.24],
    "away_xg_cumulative": [0.12, 0.12, 0.41, 0.41, 0.68, 1.05, 1.05]
  },
  "error": null
}
```

## 5. Squads

- Path: `/api/v1/match/{match_id}/squads`
- Method: `GET`
- Query params: none
- TTL: `60` seconds
- ClickHouse note: nested object payload; typically assembled from lineup rows plus player metadata rather than read as one raw row

Example request:

```http
GET /api/v1/match/12345/squads HTTP/1.1
Host: localhost:8080
```

Example response:

```json
{
  "meta": {
    "endpoint": "/api/v1/match/12345/squads",
    "timestamp": "2026-04-18T16:38:06Z",
    "cache_ttl": 60,
    "version": "1.0"
  },
  "data": {
    "home": {
      "team_id": "1",
      "team_name": "Arsenal",
      "formation": "4-3-3",
      "starting_xi": [
        { "player_id": "p_01", "name": "David Raya", "position": "GK", "position_x": 50, "position_y": 8, "number": 22 },
        { "player_id": "p_02", "name": "Ben White", "position": "RB", "position_x": 82, "position_y": 24, "number": 4 },
        { "player_id": "p_03", "name": "William Saliba", "position": "CB", "position_x": 62, "position_y": 22, "number": 2 },
        { "player_id": "p_04", "name": "Gabriel Magalhaes", "position": "CB", "position_x": 38, "position_y": 22, "number": 6 },
        { "player_id": "p_05", "name": "Oleksandr Zinchenko", "position": "LB", "position_x": 18, "position_y": 24, "number": 17 },
        { "player_id": "p_06", "name": "Martin Odegaard", "position": "CM", "position_x": 64, "position_y": 46, "number": 8 },
        { "player_id": "p_07", "name": "Declan Rice", "position": "CM", "position_x": 50, "position_y": 54, "number": 41 },
        { "player_id": "p_08", "name": "Kai Havertz", "position": "CM", "position_x": 36, "position_y": 46, "number": 29 },
        { "player_id": "p_09", "name": "Bukayo Saka", "position": "RW", "position_x": 78, "position_y": 74, "number": 7 },
        { "player_id": "p_10", "name": "Gabriel Jesus", "position": "CF", "position_x": 50, "position_y": 82, "number": 9 },
        { "player_id": "p_11", "name": "Gabriel Martinelli", "position": "LW", "position_x": 22, "position_y": 74, "number": 11 }
      ],
      "bench": [
        { "player_id": "p_12", "name": "Aaron Ramsdale", "position": "GK", "number": 32 },
        { "player_id": "p_13", "name": "Jakub Kiwior", "position": "DEF", "number": 15 },
        { "player_id": "p_14", "name": "Jorginho", "position": "MID", "number": 20 },
        { "player_id": "p_15", "name": "Leandro Trossard", "position": "FWD", "number": 19 }
      ]
    },
    "away": {
      "team_id": "2",
      "team_name": "Chelsea",
      "formation": "4-2-3-1",
      "starting_xi": [
        { "player_id": "p_21", "name": "Robert Sanchez", "position": "GK", "position_x": 50, "position_y": 8, "number": 1 },
        { "player_id": "p_22", "name": "Malo Gusto", "position": "RB", "position_x": 82, "position_y": 24, "number": 27 },
        { "player_id": "p_23", "name": "Axel Disasi", "position": "CB", "position_x": 62, "position_y": 22, "number": 2 },
        { "player_id": "p_24", "name": "Levi Colwill", "position": "CB", "position_x": 38, "position_y": 22, "number": 26 },
        { "player_id": "p_25", "name": "Ben Chilwell", "position": "LB", "position_x": 18, "position_y": 24, "number": 21 },
        { "player_id": "p_26", "name": "Moises Caicedo", "position": "DM", "position_x": 58, "position_y": 44, "number": 25 },
        { "player_id": "p_27", "name": "Enzo Fernandez", "position": "DM", "position_x": 42, "position_y": 44, "number": 8 },
        { "player_id": "p_28", "name": "Cole Palmer", "position": "AM", "position_x": 50, "position_y": 60, "number": 20 },
        { "player_id": "p_29", "name": "Noni Madueke", "position": "RW", "position_x": 78, "position_y": 74, "number": 11 },
        { "player_id": "p_30", "name": "Nicolas Jackson", "position": "CF", "position_x": 50, "position_y": 82, "number": 15 },
        { "player_id": "p_31", "name": "Mykhailo Mudryk", "position": "LW", "position_x": 22, "position_y": 74, "number": 10 }
      ],
      "bench": [
        { "player_id": "p_32", "name": "Djordje Petrovic", "position": "GK", "number": 28 },
        { "player_id": "p_33", "name": "Trevoh Chalobah", "position": "DEF", "number": 14 },
        { "player_id": "p_34", "name": "Conor Gallagher", "position": "MID", "number": 23 },
        { "player_id": "p_35", "name": "Christopher Nkunku", "position": "FWD", "number": 18 }
      ]
    }
  },
  "error": null
}
```

## 6. Team Stats

- Path: `/api/v1/team/{team_id}/stats`
- Method: `GET`
- Query params:
  - `split` (`string`, optional, default `season`): one of `season`, `last_5`, `last_10`, `home`, `away`
- TTL: `120` seconds
- ClickHouse note: split-based object payload; usually assembled from pre-aggregated metric tables grouped by split

Example request:

```http
GET /api/v1/team/1/stats?split=season HTTP/1.1
Host: localhost:8080
```

Example response:

```json
{
  "meta": {
    "endpoint": "/api/v1/team/1/stats",
    "timestamp": "2026-04-18T16:38:06Z",
    "cache_ttl": 120,
    "version": "1.0"
  },
  "data": {
    "home": {
      "team_name": "Arsenal",
      "goals_for_avg": 2.1,
      "goals_against_avg": 0.8,
      "xg_for_avg": 1.94,
      "xg_against_avg": 0.91,
      "possession_pct": 58.3,
      "shots_per_game": 15.2,
      "shots_on_target_per_game": 5.8
    },
    "away": {
      "team_name": "Chelsea",
      "goals_for_avg": 1.8,
      "goals_against_avg": 1.1,
      "xg_for_avg": 1.67,
      "xg_against_avg": 1.08,
      "possession_pct": 55.1,
      "shots_per_game": 13.7,
      "shots_on_target_per_game": 5.1
    }
  },
  "error": null
}
```

## 7. Match H2H

- Path: `/api/v1/match/{match_id}/h2h`
- Method: `GET`
- Query params:
  - `limit` (`integer`, optional, default `5`): must be greater than `0`
- TTL: `300` seconds
- ClickHouse note: row-shaped array; natural fit for historic match rows filtered by team pair and ordered by date

Example request:

```http
GET /api/v1/match/12345/h2h?limit=3 HTTP/1.1
Host: localhost:8080
```

Example response:

```json
{
  "meta": {
    "endpoint": "/api/v1/match/12345/h2h",
    "timestamp": "2026-04-18T16:38:06Z",
    "cache_ttl": 300,
    "version": "1.0"
  },
  "data": [
    {
      "match_id": "h_001",
      "match_date": "2025-11-02",
      "home_team": "Arsenal",
      "away_team": "Chelsea",
      "home_score": 2,
      "away_score": 1,
      "home_xg": 1.87,
      "away_xg": 0.94
    },
    {
      "match_id": "h_002",
      "match_date": "2025-03-16",
      "home_team": "Chelsea",
      "away_team": "Arsenal",
      "home_score": 1,
      "away_score": 1,
      "home_xg": 0.98,
      "away_xg": 1.12
    },
    {
      "match_id": "h_003",
      "match_date": "2024-10-28",
      "home_team": "Arsenal",
      "away_team": "Chelsea",
      "home_score": 3,
      "away_score": 1,
      "home_xg": 2.04,
      "away_xg": 0.76
    }
  ],
  "error": null
}
```

## 8. H2H Players

- Path: `/api/v1/match/{match_id}/h2h/players`
- Method: `GET`
- Query params:
  - `home_player_id` (`string`, optional, default `null`): must be supplied together with `away_player_id`
  - `away_player_id` (`string`, optional, default `null`): must be supplied together with `home_player_id`
- TTL: `300` seconds
- ClickHouse note: selector response is row-derived metadata; comparison response is a two-row player matchup projected into one object

Example request for selector payload:

```http
GET /api/v1/match/12345/h2h/players HTTP/1.1
Host: localhost:8080
```

Example response:

```json
{
  "meta": {
    "endpoint": "/api/v1/match/12345/h2h/players",
    "timestamp": "2026-04-18T16:35:14Z",
    "cache_ttl": 300,
    "version": "1.0"
  },
  "data": {
    "home_players": [
      { "player_id": "p_09", "name": "Bukayo Saka" },
      { "player_id": "p_10", "name": "Gabriel Jesus" },
      { "player_id": "p_06", "name": "Martin Odegaard" }
    ],
    "away_players": [
      { "player_id": "p_28", "name": "Cole Palmer" },
      { "player_id": "p_30", "name": "Nicolas Jackson" },
      { "player_id": "p_27", "name": "Enzo Fernandez" }
    ]
  },
  "error": null
}
```

Example request for comparison payload:

```http
GET /api/v1/match/12345/h2h/players?home_player_id=p_09&away_player_id=p_28 HTTP/1.1
Host: localhost:8080
```

Example response:

```json
{
  "meta": {
    "endpoint": "/api/v1/match/12345/h2h/players",
    "timestamp": "2026-04-18T16:38:06Z",
    "cache_ttl": 300,
    "version": "1.0"
  },
  "data": {
    "home_player": {
      "player_id": "p_09",
      "name": "Bukayo Saka",
      "goals": 14,
      "assists": 9,
      "xg": 12.3,
      "shots_per_game": 2.8,
      "pass_accuracy_pct": 84.1
    },
    "away_player": {
      "player_id": "p_28",
      "name": "Cole Palmer",
      "goals": 17,
      "assists": 11,
      "xg": 15.1,
      "shots_per_game": 3.1,
      "pass_accuracy_pct": 81.7
    }
  },
  "error": null
}
```

## 9. Match Facts

- Path: `/api/v1/match/{match_id}/facts`
- Method: `GET`
- Query params:
  - `category` (`string`, optional, default `null`): one of `team`, `player`, `match`, `live`
  - `limit` (`integer`, optional, default `10`): must be greater than `0`
- TTL: `15` seconds
- ClickHouse note: row-shaped event/fact array; natural fit for append-only facts tables filtered by match and category

Example request:

```http
GET /api/v1/match/12345/facts?category=live&limit=2 HTTP/1.1
Host: localhost:8080
```

Example response:

```json
{
  "meta": {
    "endpoint": "/api/v1/match/12345/facts",
    "timestamp": "2026-04-18T16:38:06Z",
    "cache_ttl": 15,
    "version": "1.0"
  },
  "data": [
    {
      "fact_id": "f_012",
      "category": "live",
      "text": "GOAL - Bukayo Saka taps in at the far post. Arsenal 1-0 Chelsea (34').",
      "minute": 34,
      "event_type": "goal"
    },
    {
      "fact_id": "f_013",
      "category": "live",
      "text": "Chelsea respond with a spell of pressure and two corners in quick succession (41').",
      "minute": 41,
      "event_type": "momentum"
    }
  ],
  "error": null
}
```

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
