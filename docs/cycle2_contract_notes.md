# Cycle 2 Contract Notes

These invariants are intentionally preserved from Cycle 1:

| Endpoint | Query params | TTL | Primary frontend dependency |
|---|---|---:|---|
| `/api/v1/match/{match_id}/state` | none | 5 | Match header, phase transitions, live polling |
| `/api/v1/competition/{competition_id}/table` | none | 300 | Default competition tab |
| `/api/v1/competition/{competition_id}/fixtures` | `status`, `limit` | 60 | Fixtures tab |
| `/api/v1/match/{match_id}/xg-race` | none | 10 | Live xG tab |
| `/api/v1/match/{match_id}/squads` | none | 60 | Pre-match and live squads views |
| `/api/v1/match/{match_id}/team-stats` | `split` | 120 | Team stats tab, especially `live` split |
| `/api/v1/team/{team_id}/stats` | `split` | 120 | Legacy/internal route |
| `/api/v1/match/{match_id}/h2h` | `limit` | 300 | H2H results tab |
| `/api/v1/match/{match_id}/h2h/players` | `home_player_id`, `away_player_id` | 300 | H2H player comparison |
| `/api/v1/match/{match_id}/facts` | `category`, `limit` | 15 | Facts tab, live filter |

Stable response rules:

- `Cache-Control: public, max-age={ttl}` remains unchanged.
- `meta.endpoint`, `meta.cache_ttl`, `meta.version`, and the envelope shape remain unchanged.
- Validation errors still return `data = {}` with the existing stable error codes.
- Missing-resource errors preserve the existing wording used by the smoke tests.
