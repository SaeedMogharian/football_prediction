# Footbal Prediction Bot
A simple one-day project that creates a telegram bot for a friend group; letting them to predict footbal matches and compete.

## Requierments
- python
    - install the requierments using: pip install re.txt
- a telegram bot token
    - save it in a file name token (no suffix!)
- Games.csv
    - Team1, Team12, Res1, Res2 (you should manualy add them) (you should keep 'TBD' for not played games)
- Users.csv
    - id, FirstName, username, points}
- Predictions.csv
    - UserID, GameID, Pred1, Pred2

## Commands
### User commands
- start: 
  - add user
  - send greeting & manuals 
- games:
  - send list of games and their results
- pred:
  - get prediction in folowing scheme:
  - /pred (gameID) (goal_pred_for_team1) (goal_pred_for_team2)
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
  - /set (gameID) (result_for_team1) )result_for_team2)
  - send confirmation
- calc
  - calculate all points for all users
- warn
  - get gameID: /warn (gameID)
  - send a message in the current chat, mention all users that don't send prediction for the game

### Need to be implemented:
- admin recognition
- authentication from admin for new users
- save each prediction point to reduce calculation
- edit option for predictions

 
Helpful Documentaition:
[https://github.com/python-telegram-bot/python-telegram-bot]
[https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions---Your-first-Bot]
[https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions---Advanced-Filters]
[https://github.com/python-telegram-bot/python-telegram-bot]
[https://github.com/python-telegram-bot/python-telegram-bot/wiki/Exceptions%2C-Warnings-and-Logging]

