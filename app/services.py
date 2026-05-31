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
        self._teams_cache: set[str] | None = None
        self._games_cache: dict[int, Game] | None = None
        self._users_cache: dict[int, tuple[str, int]] | None = None
        self._pred_cache: dict[tuple[int, int], tuple[int, int, int]] | None = None

    def _load_teams_cache(self):
        if self._teams_cache is None:
            rows = self.cursor.execute("SELECT name FROM Teams").fetchall()
            self._teams_cache = {row[0] for row in rows}

    def _load_games_cache(self):
        if self._games_cache is None:
            rows = self.cursor.execute(
                "SELECT id, team_a, team_b, goals_a, goals_b, isPlayed FROM Games"
            ).fetchall()
            self._games_cache = {
                row[0]: Game(
                    id=row[0],
                    team_a=row[1],
                    team_b=row[2],
                    goals_a=row[3],
                    goals_b=row[4],
                    is_played=row[5],
                )
                for row in rows
            }

    def _load_users_cache(self):
        if self._users_cache is None:
            rows = self.cursor.execute("SELECT t_id, username, score FROM Users").fetchall()
            self._users_cache = {row[0]: (row[1], row[2]) for row in rows}

    def _load_pred_cache(self):
        if self._pred_cache is None:
            rows = self.cursor.execute("SELECT user, game, pred_a, pred_b, score FROM Predictions").fetchall()
            self._pred_cache = {(row[0], row[1]): (row[2], row[3], row[4]) for row in rows}

    #
    # User helpers
    #
    def user_exists(self, user_id: int) -> bool:
        self._load_users_cache()
        return user_id in self._users_cache

    def add_user(self, user):
        self.cursor.execute(
            "INSERT INTO Users (t_id, username, score) VALUES (?, ?, 0)",
            (user.id, user.username),
        )
        self.connection.commit()
        self._load_users_cache()
        self._users_cache[user.id] = (user.username, 0)

    def get_user(self, user_id: int):
        self._load_users_cache()
        if user_id not in self._users_cache:
            return None
        username, score = self._users_cache[user_id]
        return (user_id, username, score)

    def get_all_users(self):
        self._load_users_cache()
        return [(uid, data[0], data[1]) for uid, data in self._users_cache.items()]

    def del_user(self, user_id: int):
        self.cursor.execute("DELETE FROM Predictions WHERE user = ?", (user_id,))
        self.cursor.execute("DELETE FROM Users WHERE t_id = ?", (user_id,))
        self.connection.commit()

        self._load_users_cache()
        self._users_cache.pop(user_id, None)
        self._load_pred_cache()
        self._pred_cache = {k: v for k, v in self._pred_cache.items() if k[0] != user_id}

    def update_scores(self, scores: dict[int, int]):
        for user_id, score in scores.items():
            self.cursor.execute("UPDATE Users SET score = ? WHERE t_id = ?", (score, user_id))
        self.connection.commit()

        self._load_users_cache()
        for user_id, score in scores.items():
            if user_id in self._users_cache:
                self._users_cache[user_id] = (self._users_cache[user_id][0], score)

    #
    # Team helpers
    #
    def add_teams(self, teams: list[str]):
        for team in teams:
            self.cursor.execute("INSERT OR IGNORE INTO Teams (name) VALUES (?)", (team,))
        self.connection.commit()
        self._teams_cache = None

    def team_exists(self, team_name: str) -> bool:
        self._load_teams_cache()
        return team_name in self._teams_cache

    #
    # Game helpers
    #
    def game_exists(self, game_id: int) -> bool:
        self._load_games_cache()
        return game_id in self._games_cache

    def game(self, game_id: int) -> Game:
        self._load_games_cache()
        return self._games_cache[game_id]

    def list_game_ids(self):
        self._load_games_cache()
        return sorted(self._games_cache.keys())

    def current_game(self):
        self._load_games_cache()
        played = [g.id for g in self._games_cache.values() if g.is_played]
        return max(played) if played else 1

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
        self._games_cache = None

    def set_game(self, game_id: int, goals_a: int, goals_b: int, is_played: int = 1):
        if not self.game_exists(game_id):
            return
        self.cursor.execute(
            "UPDATE Games SET goals_a = ?, goals_b = ?, isPlayed = ? WHERE id = ?",
            (goals_a, goals_b, is_played, game_id),
        )
        self.connection.commit()

        self._load_games_cache()
        g = self._games_cache[game_id]
        g.goals_a = goals_a
        g.goals_b = goals_b
        g.is_played = is_played

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
        self._load_pred_cache()
        return (user_id, game_id) not in self._pred_cache

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
        self._load_pred_cache()
        self._pred_cache[(pred[0], pred[1])] = (pred[2], pred[3], pred[4])

    def edit_pred(self, pred):
        self.cursor.execute(
            "UPDATE Predictions SET pred_a = ?, pred_b = ?, score = ? WHERE user = ? AND game = ?",
            (pred[2], pred[3], pred[4], pred[0], pred[1]),
        )
        self.connection.commit()
        self._load_pred_cache()
        self._pred_cache[(pred[0], pred[1])] = (pred[2], pred[3], pred[4])

    def get_prediction(self, user_id: int, game_id: int):
        self._load_pred_cache()
        return self._pred_cache.get((user_id, game_id))

    def get_user_predictions(self, user_id: int):
        self._load_pred_cache()
        return {k[1]: v for k, v in self._pred_cache.items() if k[0] == user_id}

    def get_predictions_for_game(self, game_id: int):
        self._load_pred_cache()
        self._load_users_cache()
        rows = []
        for (user_id, g_id), pred in self._pred_cache.items():
            if g_id == game_id and user_id in self._users_cache:
                rows.append((user_id, self._users_cache[user_id][0], pred[0], pred[1], pred[2]))
        return rows

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
        self._load_pred_cache()
        updates = []
        for (user_id, g_id), (pred_a, pred_b, old_score) in list(self._pred_cache.items()):
            if g_id != game_id:
                continue
            point = self.point_calc(game_id, pred_a, pred_b)
            if old_score != point:
                updates.append((point, user_id, game_id))
                self._pred_cache[(user_id, g_id)] = (pred_a, pred_b, point)

        for point, user_id, g_id in updates:
            self.cursor.execute(
                "UPDATE Predictions SET score = ? WHERE user = ? AND game = ?",
                (point, user_id, g_id),
            )
        self.connection.commit()

    def calculate_user_scores(self):
        scores = {user_id: 0 for user_id, _, _ in self.get_all_users()}
        self._load_pred_cache()
        self._load_games_cache()

        for (user_id, game_id), (_, _, score) in self._pred_cache.items():
            game = self._games_cache.get(game_id)
            if game and game.is_played:
                scores[user_id] += score

        self.update_scores(scores)
        return scores
