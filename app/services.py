from app.catalog import Catalog, Game


class Service:
    def __init__(self, cursor, connection, catalog: Catalog):
        self.cursor = cursor
        self.connection = connection
        self.catalog = catalog

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
    # Game helpers
    #
    def game_exists(self, game_id: int) -> bool:
        return game_id in self.catalog.games

    def game(self, game_id: int) -> Game:
        return self.catalog.games[game_id]

    def list_game_ids(self):
        return sorted(self.catalog.games.keys())

    def current_game(self):
        played = [g.id for g in self.catalog.games.values() if g.is_played]
        return max(played) if played else 1

    def set_game(self, game_id: int, goals_a: int, goals_b: int, is_played: int = 1):
        game = self.catalog.games[game_id]
        changed = (
            game.goals_a != goals_a
            or game.goals_b != goals_b
            or game.is_played != is_played
        )
        if not changed:
            return

        game.goals_a = goals_a
        game.goals_b = goals_b
        game.is_played = is_played

        if is_played:
            self.score_calc(game_id)

    def fetch_result(self, game_id: int):
        from bs4 import BeautifulSoup
        import requests

        game = self.catalog.games[game_id]
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
        return not self.catalog.games[game_id].is_played

    def pred_is_possib(self, pred):
        return pred[1] in self.catalog.games and pred[2] >= 0 and pred[3] >= 0

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
        row = self.cursor.execute(
            "SELECT pred_a, pred_b, score FROM Predictions WHERE user = ? AND game = ?",
            (user_id, game_id),
        ).fetchone()
        return row

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
        game = self.catalog.games[game_id]
        if game.is_played == 0:
            return 0

        goals_a = game.goals_a
        goals_b = game.goals_b

        if int(pred_a) == int(goals_a) and int(pred_b) == int(goals_b):
            return 10
        if int(pred_a) - int(pred_b) == int(goals_a) - int(goals_b):
            return 7

        point = 0
        if (int(pred_a) > int(pred_b) and int(goals_a) > int(goals_b)) or (
            int(pred_a) < int(pred_b) and int(goals_a) < int(goals_b)
        ):
            point += 4
        if int(pred_a) == int(goals_a) or int(pred_b) == int(goals_b):
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
        rows = self.cursor.execute("SELECT user, game, score FROM Predictions").fetchall()
        for user_id, game_id, score in rows:
            if self.catalog.games.get(game_id) and self.catalog.games[game_id].is_played:
                scores[user_id] += score
        self.update_scores(scores)
        return scores
