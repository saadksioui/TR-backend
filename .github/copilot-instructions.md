# Copilot Instructions — Treasure Hunt Project

## Project overview
This is a team-based treasure hunt web app for 42 students.
- Players log in with their **42 Intra account** (OAuth2).
- Before the game starts, players stay in a **waiting room**.
- An **admin** controls the game: changes the game state, sets the team size, generates teams, and manages puzzles (CRUD).
- When the game is `ON`, puzzles are launched. Each player earns **XP** by solving puzzles, and that XP is **also added to their team's total**.
- Teams are ranked on a leaderboard by total XP.

## Roles
- **Player**: logs in, waits in the lobby, joins a team, solves puzzles, earns XP.
- **Admin**: identified by 42 login (`ADMIN_LOGINS` env variable or `is_admin` flag). Has access to the admin panel.

## Game states (admin-controlled only)
`WAITING` -> `ON` -> `ENDED`
- `WAITING`: lobby only. No puzzles visible, no submissions.
- `ON`: teams exist, puzzles are visible, submissions are accepted.
- `ENDED`: submissions locked, final leaderboard shown.

## Game flow
1. Player logs in with 42 Intra; a user is created from the Intra profile (login, display name, avatar).
2. Player lands in the waiting room and is redirected automatically when the state becomes `ON`.
3. Admin sets the team size and generates teams (random by default).
4. Admin switches the state to `ON`; puzzles are launched.
5. Player submits an answer. If correct: player XP += puzzle XP, and team XP += puzzle XP.
6. Admin switches the state to `ENDED`; results are displayed.

## XP rules
- Each puzzle has an XP value set by the admin.
- Team XP = sum of the XP of all its members.
- A puzzle awards XP only **once per player**. Never award XP twice for the same player and puzzle.
- Update player XP and team XP in the **same transaction**.

## Admin features
- Change game state.
- Change team size (number of members per team) and generate/regenerate teams.
- Puzzles CRUD (title, description, answer, XP, order, active flag).
- View players, teams, submissions, and the live leaderboard.

## Data model (suggested)
- `User`: id, intra_id, login, display_name, avatar_url, is_admin, team_id, xp
- `Team`: id, name, xp
- `Puzzle`: id, title, description, answer_hash, xp, order, is_active
- `Submission`: id, user_id, puzzle_id, is_correct, submitted_at
- `GameConfig`: id, state (`WAITING` | `ON` | `ENDED`), team_size, started_at, ended_at

<!-- ## 42 Intra OAuth2
- Authorize: `https://api.intra.42.fr/oauth/authorize`
- Token: `https://api.intra.42.fr/oauth/token`
- Profile: `GET https://api.intra.42.fr/v2/me`
- Environment variables: `FT_CLIENT_ID`, `FT_CLIENT_SECRET`, `FT_REDIRECT_URI` -->

<!-- ## Pages
- Player: `/login`, `/waiting`, `/game`, `/leaderboard`, `/team`
- Admin (protected): `/admin`, `/admin/puzzles`, `/admin/teams` -->

## Coding rules
- Always check admin rights **on the server** for every admin endpoint.
- Always check the game state **on the server**: refuse puzzle access and submissions unless the state is `ON`.
- Validate answers **server-side only**. Never send answers to the client. Store answers hashed.
- Never hard-code secrets or Intra credentials; use environment variables.
- Use real-time updates (WebSocket or SSE) for state changes and the leaderboard; polling is an acceptable fallback.
- Validate and sanitize all user input.
- Keep code simple, readable, and consistent with the existing project structure and naming.
- Add error handling and return clear HTTP status codes (401 not logged in, 403 not admin, 409 duplicate submission).
- If a requirement is unclear, ask instead of guessing.

## Tech stack
- Frontend: react
- Backend: fastapi
- Database: supabase
<!-- - Real-time: TBD -->