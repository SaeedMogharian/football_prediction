import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import requests

from app.core import init_db
from app.jobs import run_scheduled_fetch_results
from app.services import Game, Service


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema.sql"
UTC = ZoneInfo("UTC")


class FrozenDateTime(datetime):
    current = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.current.replace(tzinfo=None)
        return cls.current.astimezone(tz)


class FakeResponse:
    def __init__(self, payload, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


def api_payload(fixtures, current=1, total=1, errors=None):
    return {
        "errors": {} if errors is None else errors,
        "paging": {"current": current, "total": total},
        "response": fixtures,
    }


def api_fixture(
    fixture_id,
    status,
    home="United States",
    away="IR Iran",
    fixture_date="2026-06-15T11:30:00+00:00",
    fulltime=(2, 1),
    goals=(4, 3),
    extratime=(3, 2),
    penalty=(5, 4),
):
    return {
        "fixture": {
            "id": fixture_id,
            "date": fixture_date,
            "status": {"short": status},
        },
        "teams": {
            "home": {"name": home},
            "away": {"name": away},
        },
        "goals": {"home": goals[0], "away": goals[1]},
        "score": {
            "halftime": {"home": 1, "away": 0},
            "fulltime": {"home": fulltime[0], "away": fulltime[1]},
            "extratime": {"home": extratime[0], "away": extratime[1]},
            "penalty": {"home": penalty[0], "away": penalty[1]},
        },
    }


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.cursor = self.connection.cursor()
        init_db(self.cursor, self.connection, str(SCHEMA_PATH))
        self.cursor.executemany(
            "INSERT INTO Teams (name) VALUES (?)",
            [("USA",), ("Iran",), ("South Korea",), ("Turkey",)],
        )
        self.connection.commit()
        self.service = Service(
            self.cursor,
            self.connection,
            timezone_name="UTC",
            api_football_key="test-key",
        )

    def tearDown(self):
        self.connection.close()

    def add_game(
        self,
        team_a="USA",
        team_b="Iran",
        played_at="2026-06-15T11:30:00+00:00",
        is_played=1,
        api_fixture_id=None,
        result_status=None,
    ):
        self.cursor.execute(
            """
            INSERT INTO Games (
                team_a, team_b, goals_a, goals_b, played_at, isPlayed,
                api_fixture_id, result_status
            )
            VALUES (?, ?, 0, 0, ?, ?, ?, ?)
            """,
            (
                team_a,
                team_b,
                played_at,
                is_played,
                api_fixture_id,
                result_status,
            ),
        )
        self.connection.commit()
        self.service._games_cache = None
        return self.cursor.lastrowid


class ApiFootballResultTests(ServiceTestCase):
    def test_normalizes_common_world_cup_aliases(self):
        pairs = [
            ("USA", "United States"),
            ("Iran", "IR Iran"),
            ("South Korea", "Korea Republic"),
            ("Turkey", "Türkiye"),
            ("Ivory Coast", "Côte d’Ivoire"),
        ]
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                self.assertEqual(
                    self.service._normalize_team_name(left),
                    self.service._normalize_team_name(right),
                )

    def test_selects_nearest_fixture_and_enforces_orientation(self):
        game_id = self.add_game()
        game = self.service.game(game_id)
        kickoff = self.service.get_game_played_at_datetime(game)
        candidates = [
            api_fixture(
                10,
                "NS",
                fixture_date="2026-06-15T08:00:00+00:00",
            ),
            api_fixture(
                20,
                "NS",
                fixture_date="2026-06-15T11:31:00+00:00",
            ),
        ]
        selected = self.service._select_matching_fixture(candidates, game, kickoff)
        self.assertEqual(selected["fixture"]["id"], 20)

        reversed_fixture = api_fixture(30, "NS", home="IR Iran", away="United States")
        self.assertIsNone(
            self.service._select_matching_fixture(
                [reversed_fixture],
                game,
                kickoff,
            )
        )

    @patch("app.services.requests.get")
    @patch("app.services.datetime", FrozenDateTime)
    def test_finished_result_uses_fulltime_and_updates_scores(self, request_get):
        game_id = self.add_game()
        self.cursor.execute(
            "INSERT INTO Users (t_id, username) VALUES (1, 'player')"
        )
        self.cursor.execute(
            """
            INSERT INTO Groups (chat_id, title, is_verified, requested_by)
            VALUES (100, 'group', 1, 1)
            """
        )
        self.cursor.execute(
            """
            INSERT INTO Predictions (user, game, group_id, pred_a, pred_b, score)
            VALUES (1, ?, 100, 2, 1, 0)
            """,
            (game_id,),
        )
        self.connection.commit()
        request_get.return_value = FakeResponse(
            api_payload([api_fixture(9001, "FT", fulltime=(2, 1))])
        )

        self.assertTrue(self.service.fetch_result(game_id))
        game = self.service.game(game_id)
        self.assertEqual((game.goals_a, game.goals_b), (2, 1))
        self.assertEqual(game.api_fixture_id, 9001)
        self.assertEqual(game.result_status, "FT")
        prediction_score = self.cursor.execute(
            "SELECT score FROM Predictions WHERE game = ?",
            (game_id,),
        ).fetchone()[0]
        self.assertEqual(prediction_score, 10)

        self.service.calculate_user_scores()
        total = self.cursor.execute(
            "SELECT score FROM UserGroupScores WHERE user_id = 1 AND group_id = 100"
        ).fetchone()[0]
        self.assertEqual(total, 10)
        _, kwargs = request_get.call_args
        self.assertEqual(kwargs["params"]["date"], "2026-06-15")
        self.assertEqual(kwargs["params"]["timezone"], "UTC")
        self.assertEqual(kwargs["headers"]["x-rapidapi-key"], "test-key")

    @patch("app.services.requests.get")
    @patch("app.services.datetime", FrozenDateTime)
    def test_terminal_statuses_use_fulltime_not_extra_time_or_penalties(
        self,
        request_get,
    ):
        statuses = ("FT", "AET", "PEN")
        game_ids = [
            self.add_game(api_fixture_id=fixture_id)
            for fixture_id in (101, 102, 103)
        ]
        request_get.side_effect = [
            FakeResponse(
                api_payload(
                    [
                        api_fixture(
                            fixture_id,
                            status,
                            fulltime=(1, 1),
                            goals=(4, 3),
                            extratime=(2, 1),
                            penalty=(5, 4),
                        )
                    ]
                )
            )
            for fixture_id, status in zip((101, 102, 103), statuses)
        ]

        for game_id, status in zip(game_ids, statuses):
            with self.subTest(status=status):
                self.assertTrue(self.service.fetch_result(game_id))
                game = self.service.game(game_id)
                self.assertEqual((game.goals_a, game.goals_b), (1, 1))
                self.assertEqual(game.result_status, status)

    @patch("app.services.requests.get")
    @patch("app.services.datetime", FrozenDateTime)
    def test_live_fixture_persists_identity_without_scoring(self, request_get):
        game_id = self.add_game()
        request_get.return_value = FakeResponse(
            api_payload([api_fixture(55, "1H", fulltime=(None, None))])
        )

        self.assertFalse(self.service.fetch_result(game_id))
        game = self.service.game(game_id)
        self.assertEqual(game.api_fixture_id, 55)
        self.assertEqual(game.result_status, "1H")
        self.assertFalse(self.service.is_result_final(game))

    def test_closing_predictions_does_not_finalize_or_score_game(self):
        game_id = self.add_game(is_played=0)
        self.cursor.execute(
            "INSERT INTO Users (t_id, username) VALUES (1, 'player')"
        )
        self.cursor.execute(
            """
            INSERT INTO Groups (chat_id, title, is_verified, requested_by)
            VALUES (100, 'group', 1, 1)
            """
        )
        self.cursor.execute(
            """
            INSERT INTO Predictions (user, game, group_id, pred_a, pred_b, score)
            VALUES (1, ?, 100, 0, 0, 0)
            """,
            (game_id,),
        )
        self.connection.commit()

        self.service.set_game(game_id, 0, 0, 1)

        game = self.service.game(game_id)
        self.assertTrue(game.is_played)
        self.assertIsNone(game.result_status)
        self.assertEqual(self.service.calculate_points(game_id, 0, 0), 0)
        score = self.cursor.execute(
            "SELECT score FROM Predictions WHERE game = ?",
            (game_id,),
        ).fetchone()[0]
        self.assertEqual(score, 0)

    @patch("app.services.requests.get")
    @patch("app.services.datetime", FrozenDateTime)
    def test_known_fixture_id_uses_direct_lookup(self, request_get):
        game_id = self.add_game(api_fixture_id=77, result_status="1H")
        request_get.return_value = FakeResponse(
            api_payload([api_fixture(77, "2H", fulltime=(None, None))])
        )

        self.assertFalse(self.service.fetch_result(game_id))
        _, kwargs = request_get.call_args
        self.assertEqual(
            kwargs["params"],
            {"id": 77, "timezone": "UTC"},
        )

    @patch("app.services.requests.get")
    def test_date_discovery_follows_pagination_and_caches(self, request_get):
        request_get.side_effect = [
            FakeResponse(api_payload([api_fixture(1, "NS")], current=1, total=2)),
            FakeResponse(api_payload([api_fixture(2, "NS")], current=2, total=2)),
        ]

        first = self.service._fixtures_for_date("2026-06-15")
        second = self.service._fixtures_for_date("2026-06-15")

        self.assertEqual([item["fixture"]["id"] for item in first], [1, 2])
        self.assertIs(first, second)
        self.assertEqual(request_get.call_count, 2)
        self.assertEqual(request_get.call_args_list[1].kwargs["params"]["page"], 2)

    @patch("app.services.requests.get")
    @patch("app.services.datetime", FrozenDateTime)
    def test_fetch_window_includes_zero_and_120_minutes_only(self, request_get):
        request_get.return_value = FakeResponse(api_payload([]))
        cases = [
            ("2026-06-15T12:00:00+00:00", True),
            ("2026-06-15T10:00:00+00:00", True),
            ("2026-06-15T12:01:00+00:00", False),
            ("2026-06-15T09:59:59+00:00", False),
        ]

        for played_at, should_request in cases:
            with self.subTest(played_at=played_at):
                game_id = self.add_game(played_at=played_at)
                request_get.reset_mock()
                self.service._fixture_discovery_cache.clear()
                self.assertFalse(self.service.fetch_result(game_id))
                self.assertEqual(request_get.called, should_request)

    @patch("app.services.requests.get")
    @patch("app.services.datetime", FrozenDateTime)
    def test_finalized_game_never_calls_api(self, request_get):
        game_id = self.add_game(result_status="MANUAL")
        self.assertFalse(self.service.fetch_result(game_id))
        request_get.assert_not_called()

    @patch("app.services.requests.get")
    def test_provider_and_http_errors_return_none(self, request_get):
        request_get.return_value = FakeResponse(
            api_payload([], errors={"rateLimit": "exceeded"})
        )
        self.assertIsNone(self.service._request_api_football({"id": 1}))

        request_get.return_value = FakeResponse(
            {},
            error=requests.HTTPError("server error"),
        )
        self.assertIsNone(self.service._request_api_football({"id": 1}))


class MigrationTests(unittest.TestCase):
    def test_init_db_adds_columns_and_backfills_legacy_results(self):
        connection = sqlite3.connect(":memory:")
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE Games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_a TEXT NOT NULL,
                team_b TEXT NOT NULL,
                goals_a INTEGER NOT NULL DEFAULT 0,
                goals_b INTEGER NOT NULL DEFAULT 0,
                played_at TEXT,
                isPlayed INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO Games (team_a, team_b, goals_a, goals_b, isPlayed)
            VALUES ('A', 'B', 1, 0, 1)
            """
        )
        connection.commit()

        init_db(cursor, connection, str(SCHEMA_PATH))
        cursor.execute(
            """
            INSERT INTO Games (
                team_a, team_b, goals_a, goals_b, isPlayed, result_status
            )
            VALUES ('C', 'D', 0, 0, 1, NULL)
            """
        )
        connection.commit()
        init_db(cursor, connection, str(SCHEMA_PATH))

        columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(Games)").fetchall()
        }
        self.assertIn("api_fixture_id", columns)
        self.assertIn("result_status", columns)
        status = cursor.execute(
            "SELECT result_status FROM Games WHERE id = 1"
        ).fetchone()[0]
        self.assertEqual(status, "LEGACY_FINAL")
        post_migration_status = cursor.execute(
            "SELECT result_status FROM Games WHERE id = 2"
        ).fetchone()[0]
        self.assertIsNone(post_migration_status)
        connection.close()


class SchedulerTests(unittest.TestCase):
    def test_scheduler_aggregates_only_after_successful_fetch(self):
        now = datetime.now(UTC)
        games = [
            Game(1, "A", "B", 0, 0, (now - timedelta(minutes=30)).isoformat(), 1, None, None),
            Game(2, "C", "D", 0, 0, (now - timedelta(minutes=130)).isoformat(), 1, None, None),
            Game(3, "E", "F", 1, 0, (now - timedelta(minutes=30)).isoformat(), 1, 3, "FT"),
        ]

        class FakeService:
            timezone = UTC

            def __init__(self):
                self.fetched = []
                self.aggregated = 0

            def games_with_datetime(self):
                return games

            def is_result_final(self, game):
                return game.result_status in {"FT", "AET", "PEN", "MANUAL", "LEGACY_FINAL"}

            def get_game_played_at_datetime(self, game):
                return datetime.fromisoformat(game.played_at)

            def fetch_result(self, game_id):
                self.fetched.append(game_id)
                return True

            def calculate_user_scores(self):
                self.aggregated += 1

        service = FakeService()
        context = SimpleNamespace(
            application=SimpleNamespace(bot_data={"service": service})
        )

        asyncio.run(run_scheduled_fetch_results(context))

        self.assertEqual(service.fetched, [1])
        self.assertEqual(service.aggregated, 1)

    def test_results_handler_is_cache_only(self):
        source = (ROOT / "app" / "handlers" / "user" / "stats.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("fetch_result(", source)
