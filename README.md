# Treasure Hunt Backend

FastAPI API for the Treasure Hunt application. All authenticated requests use
`Authorization: Bearer <token>`. Student tokens come from the 42 OAuth callback;
the seeded `root` admin uses `/auth/login`.

## Run

Configure the variables shown in `.env.example`, then run from this directory:

```sh
uv sync
uv run uvicorn main:app --reload
```

The API documentation is available at `/docs`. Startup creates missing tables
and adds the score/token/completion columns to an existing `teams` table.

## Authentication

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/auth/42/callback` | Public | Exchange a 42 OAuth code and sync the player profile |
| `POST` | `/auth/login` | Public | Admin login; returns a JWT |

## Student API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/game/state` | Game status, settings, and winner |
| `GET` | `/player` | Current player |
| `GET` | `/player/{login_or_id}` | Player lookup |
| `GET` | `/players`, `/players/count` | Registered player roster and count |
| `GET` | `/puzzles` | Activeuzzle/{puzzle_id}` | Puzzle CRUD; answers are only returned to admins  puzzles without answers, including team solve/lock state |
| `GET` | `/puzzle/{puzzle_id}` | One active puzzle without its answer |
| `POST` | `/puzzle/{puzzle_id}/submit` | Submit `{"answer": "..."}` during a running game |
| `GET` | `/team` | Current team and members ranked by individual XP |
| `GET` | `/teams/{team_id}` | Team and member detail |
| `GET` | `/leaderboard` | Teams ordered by total XP |
| `GET` | `/endgame` | Winner and final team statistics once finished |

Wrong answers are recorded and do not lock a puzzle. A correct answer is
awarded once per team; whitespace and letter case are ignored when comparing
answers. Individual XP is attributed to the submitting player. Special puzzle
tokens are added to the team. Big puzzles remain locked until the team meets
`tokens_required`.

The prehistoric era is always open. Middle Ages requires the configured
`stage_xp_threshold`; Future requires twice that threshold. These thresholds
are enforced both in puzzle responses and answer submissions.

## Admin API

Admin routes require an admin JWT.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/dashboard` | Live counts and game summary |
| `GET` | `/game/state` | Game status and settings (shared authenticated route) |
| `PUT` | `/game/settings` | Configure team size and era XP threshold before starting |
| `POST` | `/game/start` | Shuffle logged-in players into balanced teams and start once |
| `POST` | `/game/end` | End the game manually; preserve an existing winner or select the XP leader |
| `POST` | `/game/reset` | Reset game state, assignments, and submissions for a dry run |
| `GET`, `POST`, `PUT`, `DELETE` | `/puzzle` and `/puzzle/{puzzle_id}` | Puzzle CRUD; answers are only returned to admins |
| `POST` | `/puzzle/{puzzle_id}/image` | Upload a JPEG, PNG, or WebP image (10 MiB maximum) and set the puzzle image URL |
| `GET` | `/teams` | Team and roster overview |
| `PUT` | `/users/{player_id}/team` | Reassign a player; send `{"team_id": null}` to unassign |
| `GET` | `/users` | Synced player roster |
| `GET` | `/submissions` | Recent attempt feed; optional `team_id`, `puzzle_id`, `correct`, and `limit` filters |
| `GET` | `/audit` | Recent admin actions and answer attempts |

`POST /game/start` accepts an optional `GameSettings` JSON body. If omitted, it
uses the settings saved by `PUT /game/settings`. Puzzle categories are
`prehistoric`, `middle_ages`, and `future`; `is_special` is an independent
flag. Big puzzles must be special and declare a positive token threshold.
