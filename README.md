# Football Prediction Bot
Telegram bot for match prediction in a friend group.

## Data Architecture
- `db.sqlite3` is the source of truth for:
  - `Teams`
  - `Games`
  - `Groups` (Telegram groups and verification state)
  - `Users`
  - `Predictions`

`goals_a`, `goals_b`, and `isPlayed` are dynamic game fields stored in DB and persist across bot restarts.

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
2. Edit `settings.json` with bot token and admin Telegram IDs.
3. Start:
   ```bash
   python3 main.py
   ```

## SQLite Schema
- `Teams(name)`
- `Games(id, team_a, team_b, goals_a, goals_b, isPlayed)`
- `Users(t_id, username, score)`
- `Predictions(user, game, pred_a, pred_b, score)`
- `Groups(chat_id, title, is_verified, requested_by)`
- `Predictions(user, game, group_id, pred_a, pred_b, score)`

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
  ```text
  /add_games
  Argentina, Brazil
  France, Germany, 0, 0, 0
  ```

### Group Verification Flow
- Group admin runs `/request_group_verification` inside the group.
- Super admin runs `/verify_group <group_id>` to enable bot access for that group.
- Super admin can inspect requests with `/pending_groups`.

### Handler Structure
- `app/handlers/user.py`: verified group users
- `app/handlers/group_admin.py`: group admin (and super admin) commands
- `app/handlers/super_admin.py`: super admin only commands
