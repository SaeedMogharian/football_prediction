# Football Prediction Bot
A simple project that creates a telegram bot for a friend group; letting them to predict football matches and compete.

## Requirements
- python
    - install the requirements using: pip install re.txt
- a setting.json file created from setting.json.example

### db.sqlite
The db in which we store
- Teams
- Games
- Users
- Predictions

## Run the bot
1. Install dependencies:
   ```bash
   pip install -r re.txt
   ```
2. Create your config file from the example:
   ```bash
   cp settings.json.example settings.json
   ```
3. Edit `settings.json` and set your real bot token and admin Telegram IDs.
4. Start the bot:
   ```bash
   python main.py
   ```
5. Open Telegram and send `/start` to your bot.

## Commands
### User commands
- start:
  - add user
  - send greeting & manuals
- games:
  - send list of games and their results
- pred:
  - get prediction in following scheme:
  - /pred (gameID) (pred_a) (pred_b)
  - send confirmation
- rank:
  - send ranking of all users that send prediction to the bot
- mine:
  - send user's recorded predictions with the point it taken
- res:
  - get gameID: /res (gameID)
  - send all recorded predictions of all users for an specific game


### Admin commands
- set (set_game)
  - get game results and edit it in the game data:
  - /set (gameID) (goals_a) (goals_b)
  - send confirmation
- calc
  - calculate all points for all users
- warn
  - get gameID: /warn (gameID)
  - send a message in the current chat, mention all users that don't send prediction for the game

### Need to be implemented:
- authentication from admin for new users
- different groups implementation

Helpful Documentation:
[https://github.com/python-telegram-bot/python-telegram-bot]
[https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions---Your-first-Bot]
[https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions---Advanced-Filters]
[https://github.com/python-telegram-bot/python-telegram-bot]
[https://github.com/python-telegram-bot/python-telegram-bot/wiki/Exceptions%2C-Warnings-and-Logging]
