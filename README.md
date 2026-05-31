# Football Prediction Bot
Telegram bot for match prediction in a friend group.

## Data Architecture
- `data/catalog.jsonc`: source of truth for teams + games (supports comments)
- `db.sqlite3`: runtime data only (`Users`, `Predictions`)

`Teams` and `Games` are no longer stored in SQLite.

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
3. Edit schedule data in `data/catalog.jsonc`.
4. Start:
   ```bash
   python3 main.py
   ```

## SQLite Schema
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
