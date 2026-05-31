import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Game:
    id: int
    team_a: str
    team_b: str
    goals_a: int = 0
    goals_b: int = 0
    is_played: int = 0


@dataclass
class Catalog:
    teams: set[str]
    games: dict[int, Game]


def _load_json_with_comments(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    # Allow JSONC-style comments in catalog files.
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
    raw = re.sub(r"^\s*//.*$", "", raw, flags=re.MULTILINE)
    return json.loads(raw)


def load_catalog(path: str = "data/catalog.jsonc") -> Catalog:
    catalog_file = Path(path)
    data = _load_json_with_comments(catalog_file)

    teams = set(data.get("teams", []))
    games: dict[int, Game] = {}

    for row in data.get("games", []):
        game = Game(
            id=int(row["id"]),
            team_a=row["team_a"],
            team_b=row["team_b"],
            goals_a=int(row.get("goals_a", 0)),
            goals_b=int(row.get("goals_b", 0)),
            is_played=int(row.get("isPlayed", 0)),
        )
        if game.team_a not in teams or game.team_b not in teams:
            raise ValueError(f"Game {game.id} references unknown team")
        games[game.id] = game

    return Catalog(teams=teams, games=games)
