# Football Prediction Bot
A simple project that creates a telegram bot for a friend group; letting them to predict football matches and compete.

## Requirements
- python
    - install the requirements using: pip install re.txt
- a setting.json file
```json
{  
    "is_open":  true/false, 
    "token":    "YourBotToken",   
    "admins":   ["Admin1NumeralTelgeramID", "Admin2NumeralTelgeramID", ...]      
}  
```
### db.sqlite3

```sql
# Teams
CREATE TABLE "Teams" ( 
  "Name" TEXT NOT NULL UNIQUE,
   PRIMARY KEY("Name") 
   )

# Games
CREATE TABLE "Games" ( 
  "id" INTEGER NOT NULL UNIQUE,
   "team1" TEXT, 
   "team2" TEXT, 
   "res1" INTEGER, 
   "res2" INTEGER, 
   "isPlayed" INTEGER COLLATE BINARY, 
   PRIMARY KEY("id" AUTOINCREMENT), 
   FOREIGN KEY("team2") REFERENCES "Teams"("Name"),
   FOREIGN KEY("team1") REFERENCES "Teams"("Name") 
   )

# Users
CREATE TABLE "Users" ( 
  "t_id" INTEGER NOT NULL UNIQUE, 
  "username" TEXT UNIQUE, 
  "score" INTEGER DEFAULT 0 )

# Predictions
CREATE TABLE "Predictions" ( 
  "user" INTEGER NOT NULL, 
  "game" INTEGER NOT NULL, 
  "pred1" INTEGER, 
  "pred2" INTEGER, 
  "score" INTEGER, 
  PRIMARY KEY("user","game"), 
  FOREIGN KEY("user") REFERENCES "Users"("t_id"), 
  FOREIGN KEY("game") REFERENCES "Games"("id") )
```


## Commands
### User commands
- start:
  - add user
  - send greeting & manuals
- games:
  - send list of games and their results
- pred:
  - get prediction in following scheme:
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
- authentication from admin for new users
- different tournament implemetation
- different groups implementation

Helpful Documentation:
[https://github.com/python-telegram-bot/python-telegram-bot]
[https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions---Your-first-Bot]
[https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions---Advanced-Filters]
[https://github.com/python-telegram-bot/python-telegram-bot]
[https://github.com/python-telegram-bot/python-telegram-bot/wiki/Exceptions%2C-Warnings-and-Logging]
