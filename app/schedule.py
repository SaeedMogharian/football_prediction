import json
from pathlib import Path


def sync_schedule(cursor, connection, teams_path: str = "data/teams.json", games_path: str = "data/games.json"):
    teams_file = Path(teams_path)
    games_file = Path(games_path)
    if not teams_file.exists() or not games_file.exists():
        return False

    with teams_file.open("r", encoding="utf-8") as file:
        teams_data = json.load(file)
    with games_file.open("r", encoding="utf-8") as file:
        games_data = json.load(file)

    teams = teams_data.get("teams", [])
    games = games_data.get("games", [])

    for team in teams:
        cursor.execute("INSERT OR IGNORE INTO Teams (name) VALUES (?)", (team,))

    for game in games:
        game_id = int(game["id"])
        team_a = game["team_a"]
        team_b = game["team_b"]
        goals_a = int(game.get("goals_a", 0))
        goals_b = int(game.get("goals_b", 0))
        is_played = int(game.get("isPlayed", 0))

        cursor.execute(
            """
            INSERT INTO Games (id, team_a, team_b, goals_a, goals_b, isPlayed)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                team_a = excluded.team_a,
                team_b = excluded.team_b,
                goals_a = excluded.goals_a,
                goals_b = excluded.goals_b,
                isPlayed = excluded.isPlayed
            """,
            (game_id, team_a, team_b, goals_a, goals_b, is_played),
        )

    connection.commit()
    return True
