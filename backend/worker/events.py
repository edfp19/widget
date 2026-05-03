from __future__ import annotations

from copy import deepcopy


DEMO_EVENTS = [
    {
        "event_id": "evt_lineups_confirmed",
        "delay_seconds": 0.2,
        "state": {
            "match_id": "12345",
            "competition_id": "39",
            "phase": "PRE_MATCH",
            "clock": 0,
            "home_score": 0,
            "away_score": 0,
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "lineups_confirmed": True,
            "kickoff_utc": "2026-04-19T15:00:00Z",
        },
    },
    {
        "event_id": "evt_live_opening",
        "delay_seconds": 0.2,
        "state": {
            "match_id": "12345",
            "competition_id": "39",
            "phase": "LIVE",
            "clock": 12,
            "home_score": 0,
            "away_score": 0,
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "lineups_confirmed": True,
            "kickoff_utc": "2026-04-19T15:00:00Z",
        },
        "live_team_stats": {
            "home": {
                "team_name": "Arsenal",
                "possession_pct": 54,
                "shots": 3,
                "shots_on_target": 1,
                "corners": 1,
                "fouls": 2,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            "away": {
                "team_name": "Chelsea",
                "possession_pct": 46,
                "shots": 2,
                "shots_on_target": 0,
                "corners": 1,
                "fouls": 3,
                "yellow_cards": 0,
                "red_cards": 0,
            },
        },
    },
    {
        "event_id": "evt_goal_saka_34",
        "delay_seconds": 0.2,
        "state": {
            "match_id": "12345",
            "competition_id": "39",
            "phase": "LIVE",
            "clock": 34,
            "home_score": 1,
            "away_score": 0,
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "lineups_confirmed": True,
            "kickoff_utc": "2026-04-19T15:00:00Z",
        },
        "xg_point": {
            "minute": 34,
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "home_xg_cumulative": 0.34,
            "away_xg_cumulative": 0.20,
        },
        "fact": {
            "fact_id": "f_live_goal_034",
            "category": "live",
            "text": "GOAL - Bukayo Saka taps in at the far post. Arsenal 1-0 Chelsea (34').",
            "minute": 34,
            "event_type": "goal",
        },
        "live_team_stats": {
            "home": {
                "team_name": "Arsenal",
                "possession_pct": 57,
                "shots": 6,
                "shots_on_target": 3,
                "corners": 3,
                "fouls": 5,
                "yellow_cards": 0,
                "red_cards": 0,
            },
            "away": {
                "team_name": "Chelsea",
                "possession_pct": 43,
                "shots": 4,
                "shots_on_target": 1,
                "corners": 2,
                "fouls": 6,
                "yellow_cards": 1,
                "red_cards": 0,
            },
        },
    },
]


def load_demo_events() -> list[dict]:
    return deepcopy(DEMO_EVENTS)
