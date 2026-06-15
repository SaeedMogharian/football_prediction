from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import re
import time
import unicodedata
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

API_FOOTBALL_FIXTURES_URL = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
API_FOOTBALL_HOST = "api-football-v1.p.rapidapi.com"
FINAL_RESULT_STATUSES = frozenset({"FT", "AET", "PEN", "MANUAL", "LEGACY_FINAL"})
API_FINAL_STATUSES = frozenset({"FT", "AET", "PEN"})
_UNSET = object()


@dataclass
class Game:
    id: int
    team_a: str
    team_b: str
    goals_a: int
    goals_b: int
    played_at: str | None
    is_played: int
    api_fixture_id: int | None
    result_status: str | None


class Service:
    def __init__(
        self,
        cursor,
        connection,
        prediction_close_minutes: int = 0,
        timezone_name: str = "UTC",
        api_football_key: str = "",
    ):
        self.cursor = cursor
        self.connection = connection
        self.prediction_close_minutes = prediction_close_minutes
        self.timezone_name = timezone_name
        self.api_football_key = api_football_key
        try:
            self.timezone = ZoneInfo(timezone_name)
        except Exception:
            self.timezone_name = "Asia/Tehran"
            self.timezone = ZoneInfo(self.timezone_name)
        self._teams_cache: set[str] | None = None
        self._games_cache: dict[int, Game] | None = None
        self._users_cache: dict[int, str] | None = None
        self._groups_cache: dict[int, tuple[str, int]] | None = None
        self._predictions_cache: dict[tuple[int, int, int], tuple[int, int, int]] | None = None
        self._player_group_scores_cache: dict[tuple[int, int], int] | None = None
        self._fixture_discovery_cache: dict[
            tuple[str, str], tuple[float, list[dict]]
        ] = {}
        self._fixture_discovery_cache_ttl_seconds = 240

    def _load_teams_cache(self):
        if self._teams_cache is None:
            rows = self.cursor.execute("SELECT name FROM Teams").fetchall()
            self._teams_cache = {row[0] for row in rows}

    def _load_games_cache(self):
        if self._games_cache is None:
            rows = self.cursor.execute(
                """
                SELECT id, team_a, team_b, goals_a, goals_b, played_at,
                       isPlayed, api_fixture_id, result_status
                FROM Games
                """
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
                    api_fixture_id=row[7],
                    result_status=row[8],
                )
                for row in rows
            }

    def _load_users_cache(self):
        if self._users_cache is None:
            rows = self.cursor.execute("SELECT t_id, username FROM Users").fetchall()
            self._users_cache = {row[0]: row[1] for row in rows}

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

    def _load_player_group_scores_cache(self):
        if self._player_group_scores_cache is None:
            rows = self.cursor.execute(
                "SELECT user_id, group_id, score FROM UserGroupScores"
            ).fetchall()
            self._player_group_scores_cache = {(row[0], row[1]): row[2] for row in rows}

    #
    # User helpers
    #
    def user_exists(self, user_id: int) -> bool:
        self._load_users_cache()
        return user_id in self._users_cache

    def add_user(self, user):
        self.cursor.execute(
            "INSERT INTO Users (t_id, username) VALUES (?, ?)",
            (user.id, user.username),
        )
        self.connection.commit()
        self._load_users_cache()
        self._users_cache[user.id] = user.username

    def get_user(self, user_id: int):
        self._load_users_cache()
        if user_id not in self._users_cache:
            return None
        username = self._users_cache[user_id]
        return (user_id, username, 0)

    def get_all_users(self):
        self._load_users_cache()
        return [(uid, username, 0) for uid, username in self._users_cache.items()]

    def delete_user(self, user_id: int):
        self.cursor.execute("DELETE FROM Predictions WHERE user = ?", (user_id,))
        self.cursor.execute("DELETE FROM Users WHERE t_id = ?", (user_id,))
        self.connection.commit()
        self._load_users_cache()
        self._users_cache.pop(user_id, None)
        self._load_predictions_cache()
        self._predictions_cache = {k: v for k, v in self._predictions_cache.items() if k[0] != user_id}
        self._load_player_group_scores_cache()
        self._player_group_scores_cache = {
            k: v for k, v in self._player_group_scores_cache.items() if k[0] != user_id
        }

    def update_scores(self, scores: dict[int, int]):
        return

    #
    # Group helpers
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

    # Team helpers
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
        played = [
            game.id
            for game in self._games_cache.values()
            if self.is_result_final(game)
        ]
        return max(played) if played else 1

    @staticmethod
    def is_result_final(game: Game) -> bool:
        return game.result_status in FINAL_RESULT_STATUSES

    def add_games(self, games: list[tuple[str, str, int, int, int, str | None]]):
        for team_a, team_b, goals_a, goals_b, is_played, played_at in games:
            if not self.team_exists(team_a) or not self.team_exists(team_b):
                raise ValueError(f"Unknown team in game: {team_a} vs {team_b}")
            self.cursor.execute(
                """
                INSERT INTO Games (
                    team_a, team_b, goals_a, goals_b, isPlayed, played_at,
                    result_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team_a,
                    team_b,
                    goals_a,
                    goals_b,
                    is_played,
                    played_at,
                    "LEGACY_FINAL" if is_played else None,
                ),
            )
        self.connection.commit()
        self._games_cache = None

    def set_game(
        self,
        game_id: int,
        goals_a: int,
        goals_b: int,
        is_played: int = 1,
        played_at: str | None = None,
        *,
        api_fixture_id=_UNSET,
        result_status=_UNSET,
    ):
        if not self.game_exists(game_id):
            return False

        assignments = ["goals_a = ?", "goals_b = ?", "isPlayed = ?"]
        values = [goals_a, goals_b, is_played]
        if played_at is not None:
            assignments.append("played_at = ?")
            values.append(played_at)
        if api_fixture_id is not _UNSET:
            assignments.append("api_fixture_id = ?")
            values.append(api_fixture_id)
        if result_status is not _UNSET:
            assignments.append("result_status = ?")
            values.append(result_status)
        values.append(game_id)
        self.cursor.execute(
            f"UPDATE Games SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
        self.connection.commit()
        self._load_games_cache()
        game = self._games_cache[game_id]
        game.goals_a = goals_a
        game.goals_b = goals_b
        game.is_played = is_played
        if played_at is not None:
            game.played_at = played_at
        if api_fixture_id is not _UNSET:
            game.api_fixture_id = api_fixture_id
        if result_status is not _UNSET:
            game.result_status = result_status
        if self.is_result_final(game):
            self.recalculate_game_scores(game_id)
        return True

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
        decomposed = unicodedata.normalize("NFKD", name or "").casefold()
        without_marks = "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )
        normalized = re.sub(r"[^a-z0-9]+", "", without_marks)
        aliases = {
            "usa": "unitedstates",
            "us": "unitedstates",
            "unitedstatesofamerica": "unitedstates",
            "iran": "iran",
            "iriran": "iran",
            "iranislamicrepublicof": "iran",
            "southkorea": "southkorea",
            "korearepublic": "southkorea",
            "republicofkorea": "southkorea",
            "turkey": "turkey",
            "turkiye": "turkey",
            "ivorycoast": "ivorycoast",
            "cotedivoire": "ivorycoast",
        }
        return aliases.get(normalized, normalized)

    def _request_api_football(self, params: dict) -> dict | None:
        headers = {
            "x-rapidapi-key": self.api_football_key,
            "x-rapidapi-host": API_FOOTBALL_HOST,
        }
        try:
            response = requests.get(
                API_FOOTBALL_FIXTURES_URL,
                headers=headers,
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            logger.warning(
                "event=api_football_request_failed params=%s error=%s",
                {key: value for key, value in params.items() if key != "key"},
                error,
            )
            return None

        if not isinstance(payload, dict):
            logger.warning("event=api_football_invalid_payload reason=not_object")
            return None
        if payload.get("errors"):
            logger.warning(
                "event=api_football_provider_error errors=%s",
                payload.get("errors"),
            )
            return None
        if not isinstance(payload.get("response"), list):
            logger.warning("event=api_football_invalid_payload reason=response_not_list")
            return None
        return payload

    def _fixtures_for_date(self, local_date: str) -> list[dict] | None:
        cache_key = (local_date, self.timezone_name)
        cached = self._fixture_discovery_cache.get(cache_key)
        now_monotonic = time.monotonic()
        if cached and now_monotonic - cached[0] < self._fixture_discovery_cache_ttl_seconds:
            return cached[1]

        fixtures: list[dict] = []
        page = 1
        total_pages = 1
        while page <= total_pages:
            payload = self._request_api_football(
                {
                    "date": local_date,
                    "timezone": self.timezone_name,
                    "page": page,
                }
            )
            if payload is None:
                return None
            fixtures.extend(payload["response"])
            paging = payload.get("paging")
            if isinstance(paging, dict):
                try:
                    total_pages = max(1, int(paging.get("total", 1)))
                except (TypeError, ValueError):
                    total_pages = 1
            page += 1

        self._fixture_discovery_cache[cache_key] = (now_monotonic, fixtures)
        return fixtures

    @staticmethod
    def _parse_api_datetime(value) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    def _select_matching_fixture(
        self,
        fixtures: list[dict],
        game: Game,
        played_at_dt: datetime,
    ) -> dict | None:
        expected_home = self._normalize_team_name(game.team_a)
        expected_away = self._normalize_team_name(game.team_b)
        matches: list[tuple[float, dict]] = []
        for candidate in fixtures:
            if not isinstance(candidate, dict):
                continue
            teams = candidate.get("teams")
            fixture = candidate.get("fixture")
            if not isinstance(teams, dict) or not isinstance(fixture, dict):
                continue
            home = teams.get("home")
            away = teams.get("away")
            if not isinstance(home, dict) or not isinstance(away, dict):
                continue
            home_name = self._normalize_team_name(str(home.get("name") or ""))
            away_name = self._normalize_team_name(str(away.get("name") or ""))
            if home_name != expected_home or away_name != expected_away:
                continue

            fixture_dt = self._parse_api_datetime(fixture.get("date"))
            if fixture_dt is None:
                distance = float("inf")
            else:
                if fixture_dt.tzinfo is None:
                    fixture_dt = fixture_dt.replace(tzinfo=self.timezone)
                distance = abs(
                    (
                        fixture_dt.astimezone(self.timezone) - played_at_dt
                    ).total_seconds()
                )
            matches.append((distance, candidate))

        if not matches:
            return None
        return min(matches, key=lambda item: item[0])[1]

    @staticmethod
    def _score_value(value) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def fetch_result(self, game_id: int) -> bool:
        if not self.game_exists(game_id):
            logger.info("event=api_football_fetch_skipped_unknown_game game_id=%s", game_id)
            return False

        game = self.game(game_id)
        if self.is_result_final(game):
            logger.info(
                "event=api_football_fetch_skipped_final game_id=%s status=%s",
                game_id,
                game.result_status,
            )
            return False
        if not self.api_football_key:
            logger.error("event=api_football_fetch_skipped_missing_key game_id=%s", game_id)
            return False

        played_at_dt = self.get_game_played_at_datetime(game)
        if played_at_dt is None:
            logger.info("event=api_football_fetch_skipped_no_played_at game_id=%s", game_id)
            return False
        elapsed_minutes = (
            datetime.now(self.timezone) - played_at_dt
        ).total_seconds() / 60
        if elapsed_minutes < 0 or elapsed_minutes > 120:
            logger.info(
                "event=api_football_fetch_skipped_outside_window game_id=%s elapsed_minutes=%.1f",
                game_id,
                elapsed_minutes,
            )
            return False

        if game.api_fixture_id is not None:
            payload = self._request_api_football(
                {
                    "id": game.api_fixture_id,
                    "timezone": self.timezone_name,
                }
            )
            fixtures = payload["response"] if payload is not None else None
        else:
            fixtures = self._fixtures_for_date(played_at_dt.date().isoformat())
        if fixtures is None:
            return False

        matched = self._select_matching_fixture(fixtures, game, played_at_dt)
        if matched is None:
            logger.info(
                "event=api_football_fixture_not_matched game_id=%s team_a=%s team_b=%s",
                game_id,
                game.team_a,
                game.team_b,
            )
            return False

        fixture_data = matched.get("fixture")
        if not isinstance(fixture_data, dict):
            logger.warning("event=api_football_invalid_fixture game_id=%s", game_id)
            return False
        status_data = fixture_data.get("status")
        if not isinstance(status_data, dict):
            logger.warning("event=api_football_missing_status game_id=%s", game_id)
            return False
        try:
            fixture_id = int(fixture_data["id"])
        except (KeyError, TypeError, ValueError):
            logger.warning("event=api_football_missing_fixture_id game_id=%s", game_id)
            return False
        status = str(status_data.get("short") or "").upper()
        if not status:
            logger.warning("event=api_football_empty_status game_id=%s", game_id)
            return False

        if status not in API_FINAL_STATUSES:
            self.set_game(
                game_id,
                game.goals_a,
                game.goals_b,
                game.is_played,
                api_fixture_id=fixture_id,
                result_status=status,
            )
            logger.info(
                "event=api_football_fixture_pending game_id=%s fixture_id=%s status=%s",
                game_id,
                fixture_id,
                status,
            )
            return False

        score = matched.get("score")
        fulltime = score.get("fulltime") if isinstance(score, dict) else None
        if not isinstance(fulltime, dict):
            logger.warning(
                "event=api_football_missing_fulltime_score game_id=%s fixture_id=%s status=%s",
                game_id,
                fixture_id,
                status,
            )
            return False
        home_score = self._score_value(fulltime.get("home"))
        away_score = self._score_value(fulltime.get("away"))
        if home_score is None or away_score is None:
            logger.warning(
                "event=api_football_invalid_fulltime_score game_id=%s fixture_id=%s status=%s",
                game_id,
                fixture_id,
                status,
            )
            return False

        self.set_game(
            game_id,
            home_score,
            away_score,
            1,
            api_fixture_id=fixture_id,
            result_status=status,
        )
        logger.info(
            "event=api_football_result_applied game_id=%s fixture_id=%s status=%s score=%s-%s",
            game_id,
            fixture_id,
            status,
            home_score,
            away_score,
        )
        return True

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
                rows.append((user_id, self._users_cache[user_id], pred[0], pred[1], pred[2]))
        return rows

    def get_group_users_from_predictions(self, group_id: int) -> list[tuple[int, str | None]]:
        self._load_predictions_cache()
        self._load_users_cache()
        user_ids = {
            user_id
            for (user_id, _game_id, pred_group_id) in self._predictions_cache.keys()
            if pred_group_id == group_id
        }
        return [(user_id, self._users_cache.get(user_id, "")) for user_id in user_ids]

    #
    # Scoring helpers
    #
    def get_group_rankings(self, group_id: int):
        self._load_player_group_scores_cache()
        self._load_users_cache()
        totals: dict[int, int] = {
            user_id: score
            for (user_id, score_group_id), score in self._player_group_scores_cache.items()
            if score_group_id == group_id
        }
        return sorted(
            [(user_id, self._users_cache[user_id], total) for user_id, total in totals.items() if user_id in self._users_cache],
            key=lambda x: x[2],
            reverse=True,
        )

    def get_total_user_group_score(self, user_id: int) -> int:
        self._load_player_group_scores_cache()
        return sum(
            score
            for (score_user_id, _group_id), score in self._player_group_scores_cache.items()
            if score_user_id == user_id
        )

    def get_group_prediction_count(self, group_id: int) -> int:
        self._load_predictions_cache()
        return sum(1 for (_, _, pred_group_id) in self._predictions_cache.keys() if pred_group_id == group_id)

    def calculate_points(self, game_id: int, pred_a: int, pred_b: int):
        game = self.game(game_id)
        if not self.is_result_final(game):
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
        self._load_predictions_cache()
        self._load_games_cache()
        group_scores: dict[tuple[int, int], int] = {}
        for (user_id, game_id, group_id), (_, _, score) in self._predictions_cache.items():
            game = self._games_cache.get(game_id)
            if game and self.is_result_final(game):
                key = (user_id, group_id)
                group_scores[key] = group_scores.get(key, 0) + score

        self.cursor.execute("DELETE FROM UserGroupScores")
        for (user_id, group_id), score in group_scores.items():
            self.cursor.execute(
                "INSERT INTO UserGroupScores (user_id, group_id, score) VALUES (?, ?, ?)",
                (user_id, group_id, score),
            )
        self.connection.commit()
        self._player_group_scores_cache = dict(group_scores)
        return group_scores
