from dataclasses import dataclass


@dataclass
class Game:
    id: int
    team_a: str
    team_b: str
    goals_a: int
    goals_b: int
    is_played: int


class Service:
    def __init__(self, cursor, connection):
        self.cursor = cursor
        self.connection = connection

    #
    # User helpers
    #
    def user_exists(self, user_id: int) -> bool:
        row = self.cursor.execute("SELECT 1 FROM Users WHERE t_id = ?", (user_id,)).fetchone()
        return row is not None

    def add_user(self, user):
        self.cursor.execute(
            "INSERT INTO Users (t_id, username, score) VALUES (?, ?, 0)",
            (user.id, user.username),
        )
        self.connection.commit()

    def get_user(self, user_id: int):
        return self.cursor.execute(
            "SELECT t_id, username, score FROM Users WHERE t_id = ?", (user_id,)
        ).fetchone()

    def get_all_users(self):
        return self.cursor.execute("SELECT t_id, username, score FROM Users").fetchall()

    def del_user(self, user_id: int):
        self.cursor.execute("DELETE FROM Predictions WHERE user = ?", (user_id,))
        self.cursor.execute("DELETE FROM Users WHERE t_id = ?", (user_id,))
        self.connection.commit()

    def update_scores(self, scores: dict[int, int]):
        for user_id, score in scores.items():
            self.cursor.execute("UPDATE Users SET score = ? WHERE t_id = ?", (score, user_id))
        self.connection.commit()

    #
    # Team helpers
    #
    def add_teams(self, teams: list[str]):
        for team in teams:
            self.cursor.execute("INSERT OR IGNORE INTO Teams (name) VALUES (?)", (team,))
        self.connection.commit()

    def team_exists(self, team_name: str) -> bool:
        row = self.cursor.execute("SELECT 1 FROM Teams WHERE name = ?", (team_name,)).fetchone()
        return row is not None

    #
    # Game helpers
    #
    def game_exists(self, game_id: int) -> bool:
        row = self.cursor.execute("SELECT 1 FROM Games WHERE id = ?", (game_id,)).fetchone()
        return row is not None

    def game(self, game_id: int) -> Game:
        row = self.cursor.execute(
            "SELECT id, team_a, team_b, goals_a, goals_b, isPlayed FROM Games WHERE id = ?",
            (game_id,),
        ).fetchone()
        return Game(
            id=row[0],
            team_a=row[1],
            team_b=row[2],
            goals_a=row[3],
            goals_b=row[4],
            is_played=row[5],
        )

    def list_game_ids(self):
        rows = self.cursor.execute("SELECT id FROM Games ORDER BY id").fetchall()
        return [row[0] for row in rows]

    def current_game(self):
        row = self.cursor.execute("SELECT MAX(id) FROM Games WHERE isPlayed = 1").fetchone()
        return int(row[0]) if row and row[0] is not None else 1

    def add_games(self, games: list[tuple[str, str, int, int, int]]):
        for team_a, team_b, goals_a, goals_b, is_played in games:
            if not self.team_exists(team_a) or not self.team_exists(team_b):
                raise ValueError(f"Unknown team in game: {team_a} vs {team_b}")
            self.cursor.execute(
                """
                INSERT INTO Games (team_a, team_b, goals_a, goals_b, isPlayed)
                VALUES (?, ?, ?, ?, ?)
                """,
                (team_a, team_b, goals_a, goals_b, is_played),
            )
        self.connection.commit()

    def set_game(self, game_id: int, goals_a: int, goals_b: int, is_played: int = 1):
        if not self.game_exists(game_id):
            return
        self.cursor.execute(
            "UPDATE Games SET goals_a = ?, goals_b = ?, isPlayed = ? WHERE id = ?",
            (goals_a, goals_b, is_played, game_id),
        )
        self.connection.commit()

        if is_played:
            self.score_calc(game_id)

    def fetch_result(self, game_id: int):
        from bs4 import BeautifulSoup
        import requests

        game = self.game(game_id)
        query = f"https://www.google.com/search?q={game.team_a}+vs+{game.team_b}"
        source = requests.get(query, headers={"accept-language": "en-US,en;q=0.9"}).text
        soup = BeautifulSoup(source, "lxml")
        soup = soup.find_all("div", class_="BNeawe deIvCb AP7Wnd")

        print("Google Says: ", game_id, soup[1].text, soup[2].text)

        if soup[0].text.split(" ")[0] == game.team_a:
            self.set_game(game_id, int(soup[1].text), int(soup[2].text))
        else:
            self.set_game(game_id, int(soup[2].text), int(soup[1].text))

    #
    # Prediction helpers
    #
    def pred_is_new(self, user_id: int, game_id: int):
        row = self.cursor.execute(
            "SELECT 1 FROM Predictions WHERE user = ? AND game = ?", (user_id, game_id)
        ).fetchone()
        return row is None

    def pred_is_av(self, game_id: int):
        return not self.game(game_id).is_played

    def pred_is_possib(self, pred):
        return self.game_exists(pred[1]) and pred[2] >= 0 and pred[3] >= 0

    def add_pred(self, pred):
        self.cursor.execute(
            "INSERT INTO Predictions (user, game, pred_a, pred_b, score) VALUES (?, ?, ?, ?, ?)",
            (pred[0], pred[1], pred[2], pred[3], pred[4]),
        )
        self.connection.commit()

    def edit_pred(self, pred):
        self.cursor.execute(
            "UPDATE Predictions SET pred_a = ?, pred_b = ?, score = ? WHERE user = ? AND game = ?",
            (pred[2], pred[3], pred[4], pred[0], pred[1]),
        )
        self.connection.commit()

    def get_prediction(self, user_id: int, game_id: int):
        return self.cursor.execute(
            "SELECT pred_a, pred_b, score FROM Predictions WHERE user = ? AND game = ?",
            (user_id, game_id),
        ).fetchone()

    def get_user_predictions(self, user_id: int):
        rows = self.cursor.execute(
            "SELECT game, pred_a, pred_b, score FROM Predictions WHERE user = ? ORDER BY game",
            (user_id,),
        ).fetchall()
        return {row[0]: (row[1], row[2], row[3]) for row in rows}

    def get_predictions_for_game(self, game_id: int):
        return self.cursor.execute(
            """
            SELECT p.user, u.username, p.pred_a, p.pred_b, p.score
            FROM Predictions p
            JOIN Users u ON u.t_id = p.user
            WHERE p.game = ?
            """,
            (game_id,),
        ).fetchall()

    #
    # Scoring helpers
    #
    def point_calc(self, game_id: int, pred_a: int, pred_b: int):
        game = self.game(game_id)
        if game.is_played == 0:
            return 0

        if int(pred_a) == int(game.goals_a) and int(pred_b) == int(game.goals_b):
            return 10
        if int(pred_a) - int(pred_b) == int(game.goals_a) - int(game.goals_b):
            return 7

        point = 0
        if (int(pred_a) > int(pred_b) and int(game.goals_a) > int(game.goals_b)) or (
            int(pred_a) < int(pred_b) and int(game.goals_a) < int(game.goals_b)
        ):
            point += 4
        if int(pred_a) == int(game.goals_a) or int(pred_b) == int(game.goals_b):
            point += 1
        return point

    def score_calc(self, game_id: int):
        rows = self.cursor.execute(
            "SELECT user, pred_a, pred_b, score FROM Predictions WHERE game = ?", (game_id,)
        ).fetchall()
        for user_id, pred_a, pred_b, old_score in rows:
            point = self.point_calc(game_id, pred_a, pred_b)
            if old_score != point:
                self.cursor.execute(
                    "UPDATE Predictions SET score = ? WHERE user = ? AND game = ?",
                    (point, user_id, game_id),
                )
        self.connection.commit()

    def calculate_user_scores(self):
        scores = {user_id: 0 for user_id, _, _ in self.get_all_users()}
        rows = self.cursor.execute(
            "SELECT p.user, p.game, p.score FROM Predictions p JOIN Games g ON g.id = p.game WHERE g.isPlayed = 1"
        ).fetchall()
        for user_id, _game_id, score in rows:
            scores[user_id] += score
        self.update_scores(scores)
        return scores
