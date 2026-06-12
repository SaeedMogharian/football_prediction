from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import logging
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


@dataclass
class Game:
    id: int
    team_a: str
    team_b: str
    goals_a: int
    goals_b: int
    played_at: str | None
    is_played: int


class Service:
    def __init__(
        self,
        cursor,
        connection,
        prediction_close_minutes: int = 0,
        timezone_name: str = "UTC",
        fotmob_fixtures_url: str = "",
    ):
        self.cursor = cursor
        self.connection = connection
        self.prediction_close_minutes = prediction_close_minutes
        self.timezone_name = timezone_name
        self.fotmob_fixtures_url = fotmob_fixtures_url
        try:
            self.timezone = ZoneInfo(timezone_name)
        except Exception:
            self.timezone = ZoneInfo("Asia/Tehran")
        self._teams_cache: set[str] | None = None
        self._games_cache: dict[int, Game] | None = None
        self._users_cache: dict[int, tuple[str, int]] | None = None
        self._groups_cache: dict[int, tuple[str, int]] | None = None
        self._predictions_cache: dict[tuple[int, int, int], tuple[int, int, int]] | None = None

    def _load_teams_cache(self):
        if self._teams_cache is None:
            rows = self.cursor.execute("SELECT name FROM Teams").fetchall()
            self._teams_cache = {row[0] for row in rows}

    def _load_games_cache(self):
        if self._games_cache is None:
            rows = self.cursor.execute(
                "SELECT id, team_a, team_b, goals_a, goals_b, played_at, isPlayed FROM Games"
            ).fetchall()
            self._games_cache = {
                row[0]: Game(
                    id=row[0],
                    team_a=row[1],
                    team_b=row[2],
                    goals_a=row[3],
                    goals_b=row[4],
                    played_at=row[5],
                    is_played=row[6],
                )
                for row in rows
            }

    def _load_users_cache(self):
        if self._users_cache is None:
            rows = self.cursor.execute("SELECT t_id, username, score FROM Users").fetchall()
            self._users_cache = {row[0]: (row[1], row[2]) for row in rows}

    def _load_groups_cache(self):
        if self._groups_cache is None:
            rows = self.cursor.execute("SELECT chat_id, title, is_verified FROM Groups").fetchall()
            self._groups_cache = {row[0]: (row[1] or "", row[2]) for row in rows}

    def _load_predictions_cache(self):
        if self._predictions_cache is None:
            rows = self.cursor.execute(
                "SELECT user, game, group_id, pred_a, pred_b, score FROM Predictions"
            ).fetchall()
            self._predictions_cache = {
                (row[0], row[1], row[2]): (row[3], row[4], row[5])
                for row in rows
            }

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

    def delete_user(self, user_id: int):
        self.cursor.execute("DELETE FROM Predictions WHERE user = ?", (user_id,))
        self.cursor.execute("DELETE FROM Users WHERE t_id = ?", (user_id,))
        self.connection.commit()
        self._load_users_cache()
        self._users_cache.pop(user_id, None)
        self._load_predictions_cache()
        self._predictions_cache = {k: v for k, v in self._predictions_cache.items() if k[0] != user_id}

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
    def register_group_request(self, chat_id: int, title: str, requested_by: int):
        self.cursor.execute(
            """
            INSERT INTO Groups (chat_id, title, is_verified, requested_by)
            VALUES (?, ?, 0, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title = excluded.title,
                requested_by = excluded.requested_by
            """,
            (chat_id, title, requested_by),
        )
        self.connection.commit()
        self._groups_cache = None

    def verify_group(self, chat_id: int) -> bool:
        self.cursor.execute("UPDATE Groups SET is_verified = 1 WHERE chat_id = ?", (chat_id,))
        self.connection.commit()
        self._groups_cache = None
        return self.cursor.rowcount > 0

    def list_pending_groups(self):
        rows = self.cursor.execute(
            """
            SELECT g.chat_id, g.title, g.requested_by, u.username
            FROM Groups g
            LEFT JOIN Users u ON u.t_id = g.requested_by
            WHERE g.is_verified = 0
            ORDER BY g.chat_id
            """
        ).fetchall()
        return rows

    def is_group_verified(self, chat_id: int) -> bool:
        self._load_groups_cache()
        group_data = self._groups_cache.get(chat_id)
        return bool(group_data and group_data[1] == 1)

    def is_group_registered(self, chat_id: int) -> bool:
        self._load_groups_cache()
        return chat_id in self._groups_cache

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
        played = [game.id for game in self._games_cache.values() if game.is_played]
        return max(played) if played else 1

    def add_games(self, games: list[tuple[str, str, int, int, int, str | None]]):
        for team_a, team_b, goals_a, goals_b, is_played, played_at in games:
            if not self.team_exists(team_a) or not self.team_exists(team_b):
                raise ValueError(f"Unknown team in game: {team_a} vs {team_b}")
            self.cursor.execute(
                """
                INSERT INTO Games (team_a, team_b, goals_a, goals_b, isPlayed, played_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (team_a, team_b, goals_a, goals_b, is_played, played_at),
            )
        self.connection.commit()
        self._games_cache = None

    def set_game(self, game_id: int, goals_a: int, goals_b: int, is_played: int = 1, played_at: str | None = None):
        if not self.game_exists(game_id):
            return
        if played_at is None:
            self.cursor.execute(
                "UPDATE Games SET goals_a = ?, goals_b = ?, isPlayed = ? WHERE id = ?",
                (goals_a, goals_b, is_played, game_id),
            )
        else:
            self.cursor.execute(
                "UPDATE Games SET goals_a = ?, goals_b = ?, isPlayed = ?, played_at = ? WHERE id = ?",
                (goals_a, goals_b, is_played, played_at, game_id),
            )
        self.connection.commit()
        self._load_games_cache()
        game = self._games_cache[game_id]
        game.goals_a = goals_a
        game.goals_b = goals_b
        game.is_played = is_played
        if played_at is not None:
            game.played_at = played_at
        if is_played:
            self.recalculate_game_scores(game_id)

    def set_game_time(self, game_id: int, played_at: str):
        if not self.game_exists(game_id):
            return False
        self.cursor.execute(
            "UPDATE Games SET played_at = ? WHERE id = ?",
            (played_at, game_id),
        )
        self.connection.commit()
        self._load_games_cache()
        self._games_cache[game_id].played_at = played_at
        return True

    @staticmethod
    def _normalize_team_name(name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (name or "").lower())

    @staticmethod
    def _build_fotmob_page_url(base_url: str, page: int) -> str:
        parsed = urlparse(base_url)
        query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query_items["page"] = str(page)
        new_query = urlencode(query_items)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    def _collect_fixtures_from_json(self, node, fixtures: list[dict]):
        if isinstance(node, dict):
            home = node.get("homeTeam") or node.get("home")
            away = node.get("awayTeam") or node.get("away")
            if isinstance(home, dict) and isinstance(away, dict):
                home_name = home.get("name") or home.get("shortName")
                away_name = away.get("name") or away.get("shortName")
                status = node.get("status", {})
                started = bool(status.get("started") or node.get("started"))
                finished = bool(status.get("finished") or node.get("finished"))
                score = node.get("score") or {}
                score_str = node.get("scoreStr") or ""
                home_score = score.get("home")
                away_score = score.get("away")

                if (home_score is None or away_score is None) and isinstance(score_str, str):
                    parts = [part.strip() for part in score_str.split("-")]
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        home_score = int(parts[0])
                        away_score = int(parts[1])

                fixtures.append(
                    {
                        "home_name": home_name,
                        "away_name": away_name,
                        "home_score": home_score,
                        "away_score": away_score,
                        "started": started,
                        "finished": finished,
                    }
                )

            for value in node.values():
                self._collect_fixtures_from_json(value, fixtures)
            return

        if isinstance(node, list):
            for item in node:
                self._collect_fixtures_from_json(item, fixtures)

    def _extract_fotmob_fixtures(self, html: str) -> list[dict]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        fixtures: list[dict] = []
        for script in soup.find_all("script"):
            script_text = (script.string or script.get_text() or "").strip()
            if not script_text:
                continue
            if script_text.startswith("{") and script_text.endswith("}"):
                try:
                    payload = json.loads(script_text)
                except Exception:
                    continue
                self._collect_fixtures_from_json(payload, fixtures)
        return fixtures

    def fetch_result(self, game_id: int):
        import requests

        game = self.game(game_id)
        team_a = self._normalize_team_name(game.team_a)
        team_b = self._normalize_team_name(game.team_b)

        for page in range(10):
            page_url = self._build_fotmob_page_url(self.fotmob_fixtures_url, page)
            logger.info("FotMob query game=%s page=%s url=%s", game_id, page, page_url)
            try:
                source = requests.get(page_url, headers={"accept-language": "en-US,en;q=0.9"}, timeout=15).text
            except Exception as error:
                logger.warning("FotMob request failed game=%s page=%s error=%s", game_id, page, error)
                continue
            fixtures = self._extract_fotmob_fixtures(source)

            for fixture in fixtures:
                home_name = self._normalize_team_name(str(fixture.get("home_name") or ""))
                away_name = self._normalize_team_name(str(fixture.get("away_name") or ""))
                if home_name != team_a or away_name != team_b:
                    continue

                home_score = fixture.get("home_score")
                away_score = fixture.get("away_score")
                is_finished = bool(fixture.get("finished"))
                logger.info(
                    "FotMob game found game=%s page=%s %s vs %s finished=%s score=%s-%s",
                    game_id,
                    page,
                    game.team_a,
                    game.team_b,
                    is_finished,
                    home_score,
                    away_score,
                )
                if home_score is None or away_score is None or not is_finished:
                    return False

                self.set_game(game_id, int(home_score), int(away_score), 1)
                logger.info("FotMob result applied game=%s score=%s-%s", game_id, int(home_score), int(away_score))
                return True

        logger.info("FotMob game not found game=%s %s vs %s pages=0..9", game_id, game.team_a, game.team_b)
        return False

    #
    # Prediction helpers
    #
    def is_new_prediction(self, user_id: int, game_id: int, group_id: int):
        self._load_predictions_cache()
        return (user_id, game_id, group_id) not in self._predictions_cache

    def is_prediction_open(self, game_id: int):
        game = self.game(game_id)
        if game.is_played:
            return False
        played_at_dt = self.get_game_played_at_datetime(game)
        if played_at_dt is None:
            return True
        now = datetime.now(self.timezone)
        close_at = played_at_dt - timedelta(minutes=self.prediction_close_minutes)
        return now < close_at

    def get_game_played_at_datetime(self, game: Game) -> datetime | None:
        if not game.played_at:
            return None
        raw_value = str(game.played_at).strip()
        if not raw_value:
            return None

        normalized = raw_value.replace("Z", "+00:00")
        try:
            played_at_dt = datetime.fromisoformat(normalized)
        except Exception:
            fallback_formats = (
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M",
                "%Y-%m-%dT%H:%M:%S",
            )
            played_at_dt = None
            for dt_format in fallback_formats:
                try:
                    played_at_dt = datetime.strptime(raw_value, dt_format)
                    break
                except Exception:
                    continue
            if played_at_dt is None:
                return None
        if played_at_dt.tzinfo is None:
            return played_at_dt.replace(tzinfo=self.timezone)
        return played_at_dt.astimezone(self.timezone)

    def list_verified_group_ids(self) -> list[int]:
        self._load_groups_cache()
        return [chat_id for chat_id, (_, is_verified) in self._groups_cache.items() if is_verified == 1]

    def get_pending_prediction_usernames(self, game_id: int, group_id: int) -> list[str]:
        usernames = []
        for member_id, username, _ in self.get_all_users():
            if not username:
                continue
            if self.is_new_prediction(member_id, game_id, group_id):
                usernames.append(username)
        return usernames

    def games_with_datetime(self) -> list[Game]:
        self._load_games_cache()
        return [game for game in self._games_cache.values() if game.played_at]

    def is_valid_prediction_input(self, prediction_input):
        return self.game_exists(prediction_input[1]) and prediction_input[3] >= 0 and prediction_input[4] >= 0

    def add_prediction(self, prediction):
        self.cursor.execute(
            "INSERT INTO Predictions (user, game, group_id, pred_a, pred_b, score) VALUES (?, ?, ?, ?, ?, ?)",
            (prediction[0], prediction[1], prediction[2], prediction[3], prediction[4], prediction[5]),
        )
        self.connection.commit()
        self._load_predictions_cache()
        self._predictions_cache[(prediction[0], prediction[1], prediction[2])] = (
            prediction[3], prediction[4], prediction[5]
        )

    def update_prediction(self, prediction):
        self.cursor.execute(
            """
            UPDATE Predictions
            SET pred_a = ?, pred_b = ?, score = ?
            WHERE user = ? AND game = ? AND group_id = ?
            """,
            (prediction[3], prediction[4], prediction[5], prediction[0], prediction[1], prediction[2]),
        )
        self.connection.commit()
        self._load_predictions_cache()
        self._predictions_cache[(prediction[0], prediction[1], prediction[2])] = (
            prediction[3], prediction[4], prediction[5]
        )

    def get_prediction(self, user_id: int, game_id: int, group_id: int):
        self._load_predictions_cache()
        return self._predictions_cache.get((user_id, game_id, group_id))

    def get_user_predictions(self, user_id: int, group_id: int):
        self._load_predictions_cache()
        return {k[1]: v for k, v in self._predictions_cache.items() if k[0] == user_id and k[2] == group_id}

    def get_predictions_for_game(self, game_id: int, group_id: int):
        self._load_predictions_cache()
        self._load_users_cache()
        rows = []
        for (user_id, pred_game_id, pred_group_id), pred in self._predictions_cache.items():
            if pred_game_id == game_id and pred_group_id == group_id and user_id in self._users_cache:
                rows.append((user_id, self._users_cache[user_id][0], pred[0], pred[1], pred[2]))
        return rows

    #
    # Scoring helpers
    #
    def get_group_rankings(self, group_id: int):
        self._load_predictions_cache()
        self._load_users_cache()
        self._load_games_cache()
        totals: dict[int, int] = {}
        for (user_id, game_id, pred_group_id), (_, _, score) in self._predictions_cache.items():
            if pred_group_id != group_id:
                continue
            game = self._games_cache.get(game_id)
            if not game or not game.is_played:
                continue
            totals[user_id] = totals.get(user_id, 0) + score
        return sorted(
            [(user_id, self._users_cache[user_id][0], total) for user_id, total in totals.items() if user_id in self._users_cache],
            key=lambda x: x[2],
            reverse=True,
        )

    def get_group_prediction_count(self, group_id: int) -> int:
        self._load_predictions_cache()
        return sum(1 for (_, _, pred_group_id) in self._predictions_cache.keys() if pred_group_id == group_id)

    def calculate_points(self, game_id: int, pred_a: int, pred_b: int):
        game = self.game(game_id)
        if game.is_played == 0:
            return 0
        if int(pred_a) == int(game.goals_a) and int(pred_b) == int(game.goals_b):
            return 10
        if int(pred_a) - int(pred_b) == int(game.goals_a) - int(game.goals_b):
            return 7
        points = 0
        if (int(pred_a) > int(pred_b) and int(game.goals_a) > int(game.goals_b)) or (
            int(pred_a) < int(pred_b) and int(game.goals_a) < int(game.goals_b)
        ):
            points += 4
        if int(pred_a) == int(game.goals_a) or int(pred_b) == int(game.goals_b):
            points += 1
        return points

    def recalculate_game_scores(self, game_id: int):
        self._load_predictions_cache()
        updates = []
        for key, value in list(self._predictions_cache.items()):
            user_id, pred_game_id, group_id = key
            pred_a, pred_b, old_score = value
            if pred_game_id != game_id:
                continue
            points = self.calculate_points(game_id, pred_a, pred_b)
            if old_score != points:
                updates.append((points, user_id, pred_game_id, group_id))
                self._predictions_cache[key] = (pred_a, pred_b, points)

        for points, user_id, pred_game_id, group_id in updates:
            self.cursor.execute(
                "UPDATE Predictions SET score = ? WHERE user = ? AND game = ? AND group_id = ?",
                (points, user_id, pred_game_id, group_id),
            )
        self.connection.commit()

    def calculate_user_scores(self):
        scores = {user_id: 0 for user_id, _, _ in self.get_all_users()}
        self._load_predictions_cache()
        self._load_games_cache()
        for (user_id, game_id, _group_id), (_, _, score) in self._predictions_cache.items():
            game = self._games_cache.get(game_id)
            if game and game.is_played:
                scores[user_id] += score
        self.update_scores(scores)
        return scores
