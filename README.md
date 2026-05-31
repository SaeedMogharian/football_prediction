# Football Prediction Bot
Telegram bot for match prediction in a friend group.

## Data Architecture
- `db.sqlite3` is the source of truth for:
  - `Teams`
  - `Games`
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

## Commands
### User
- `/start`
- `/games`
- `/pred <gameID> <team_a goals> <team_b goals>`
- `/rank`
- `/mine`
- `/res [gameID]`

### Admin
- `/set <gameID> <goals_a> <goals_b>`
- `/play <gameID>`
- `/unplay <gameID>`
- `/warn [gameID]`
- `/calc`
- `/delu <username> [f|1]`

### Admin Bulk Insert
- `/addteams` with newline-separated names:
  ```text
  /addteams
  Argentina
  Brazil
  Germany
  ```

- `/addgames` with newline-separated rows (comma-separated):
  - minimal: `team_a, team_b`
  - full: `team_a, team_b, goals_a, goals_b, isPlayed`
  ```text
  /addgames
  Argentina, Brazil
  France, Germany, 0, 0, 0
  ```
