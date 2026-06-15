# Football Prediction Bot
Telegram bot for match prediction in a friend group.

## Data Architecture
- `db.sqlite3` is the source of truth for:
  - `Teams`
  - `Games`
  - `Groups` (Telegram groups and verification state)
  - `Users`
  - `Predictions`
  - `UserGroupScores`

`goals_a`, `goals_b`, `isPlayed`, `played_at`, `api_fixture_id`, and
`result_status` are dynamic game fields stored in DB and persist across bot
restarts. `isPlayed` locks predictions; `result_status` determines whether a
result is final and eligible for scoring.

## Requirements
- Python 3
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

## Run the bot
1. Create config:
   ```bash
   cp settings.json.example settings.json
   ```
2. Edit `settings.json` with the bot token, RapidAPI key, and admin Telegram IDs.
3. Start:
   ```bash
   python3 main.py
   ```

## SQLite Schema
- `Teams(name)`
- `Games(id, team_a, team_b, goals_a, goals_b, played_at, isPlayed, api_fixture_id, result_status)`
- `Users(t_id, username)`
- `Groups(chat_id, title, is_verified, requested_by)`
- `Predictions(user, game, group_id, pred_a, pred_b, score)`
- `UserGroupScores(user_id, group_id, score)`

## Commands
### User
- `/start`
- `/games`
- `/predict <game_id> <team_a_goals> <team_b_goals>`
- `/rank`
- `/my_stats`
- `/results [game_id]`

### Group Admin
- `/request_group_verification`
- `/remind [game_id]`
- `/group_stats`

### Super Admin
- `/set_result <game_id> <goals_a> <goals_b>`
- `/set_time <game_id> <YYYY-MM-DDTHH:MM:SS>`
- `/close_predictions <game_id>`
- `/open_predictions <game_id>`
- `/recalc_scores`
- `/delete_user <username> [f|1]`
- `/verify_group <group_id>`
- `/pending_groups`
- `/add_teams` (bulk insert)
- `/add_games` (bulk insert)

### Admin Bulk Insert
- `/add_teams` with newline-separated names:
  ```text
  /add_teams
  Argentina
  Brazil
  Germany
  ```

- `/add_games` with newline-separated rows (comma-separated):
  - minimal: `team_a, team_b`
  - full: `team_a, team_b, goals_a, goals_b, isPlayed`
  - scheduled: `team_a, team_b, goals_a, goals_b, isPlayed, YYYY-MM-DDTHH:MM:SS`
  ```text
  /add_games
  Argentina, Brazil
  France, Germany, 0, 0, 0
  England, Spain, 0, 0, 0, 2026-06-21T21:30:00
  ```

- `/set_time` supports single or multiline input:
  ```text
  /set_time 1 2026-06-21T21:30:00
  ```
  ```text
  /set_time
  1, 2026-06-21T21:30:00
  2, 2026-06-21T23:30:00
  ```

## Scheduling Settings
- `timezone`: IANA timezone used for interpreting game `played_at` values and reminder/close checks.
  - Example: `Asia/Tehran`, `UTC`, `Europe/Berlin`
- `api_football_key`: RapidAPI key for API-Football v3.
  - Keep the real key only in ignored `settings.json`; never commit it.
  - The bot calls `https://api-football-v1.p.rapidapi.com/v3/fixtures`.
- `prediction_close_minutes`: closes predictions this many minutes before kickoff.
  - Example: `0` closes exactly at kickoff.
  - Example: `10` closes 10 minutes before kickoff.
  - Example: `-5` closes 5 minutes after kickoff.
- `reminder_offsets_minutes`: list of reminder offsets (in minutes before kickoff), sent to verified groups.
  - Example: `[10, 1]` sends reminders 10 and 1 minutes before game time.
- The bot polls API-Football every five minutes from kickoff through minute 120.
- Fixture discovery uses the configured timezone and kickoff date, then persists
  `api_fixture_id` so later polls can query the exact fixture.
- Polling stops permanently when `result_status` becomes `FT`, `AET`, `PEN`,
  `MANUAL`, or `LEGACY_FINAL`.
- API `score.fulltime` values are used for scoring. Extra-time and penalty
  shootout values are not included.

### Existing Database Migration

On startup, missing API-Football columns are added automatically. Rows that
already had `isPlayed = 1` before this migration are marked `LEGACY_FINAL` to
preserve historical scores.

If an active game was only closed for predictions and was incorrectly marked as
legacy final, clear its result metadata while keeping predictions closed:

```sql
UPDATE Games
SET result_status = NULL, api_fixture_id = NULL
WHERE id = <game_id>;
```

### Group Verification Flow
- Group admin runs `/request_group_verification` inside the group.
- Super admin runs `/verify_group <group_id>` to enable bot access for that group.
- Super admin can inspect requests with `/pending_groups`.

### Handler Structure
- `app/handlers/user/`: verified group user features
  - `app/handlers/user/start.py`: `/start`
  - `app/handlers/user/games.py`: `/games` + games callbacks
  - `app/handlers/user/predict.py`: prediction conversation + helpers
  - `app/handlers/user/stats.py`: `/rank`, `/my_stats`, `/results`
  - `app/handlers/user/__init__.py`: user handler composition
- `app/handlers/group_admin.py`: group admin (and super admin) commands
- `app/handlers/super_admin.py`: super admin only commands

### Logging
- Runtime logs are written to `system.log` in project root.
- Logs are also printed to console.
- Rotation is enabled (`5MB` per file, keep `5` backups).
