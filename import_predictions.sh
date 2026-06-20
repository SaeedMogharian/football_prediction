#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_FILE="${DB_FILE:-${SCRIPT_DIR}/db.sqlite3}"
GROUP_ID=${GROUP_ID:--1001620681085}

command -v sqlite3 >/dev/null || { echo "sqlite3 is required" >&2; exit 1; }

TMP_SQL="$(mktemp)"
trap 'rm -f "$TMP_SQL"' EXIT

cat > "$TMP_SQL" <<'SQL'
BEGIN IMMEDIATE;
PRAGMA foreign_keys = ON;

INSERT OR REPLACE INTO Predictions (user, game, group_id, pred_a, pred_b, score) VALUES
  (256388689, 29, -1001620681085, 2, 1, 0),
  (87880137, 29, -1001620681085, 2, 1, 0),
  (106872961, 29, -1001620681085, 3, 1, 0),
  (107945188, 29, -1001620681085, 1, 1, 0),
  (87880137, 30, -1001620681085, 0, 2, 0),
  (87880137, 31, -1001620681085, 3, 0, 0),
  (87880137, 32, -1001620681085, 1, 0, 0),
  (256388689, 30, -1001620681085, 1, 2, 0),
  (256388689, 31, -1001620681085, 3, 0, 0),
  (256388689, 32, -1001620681085, 2, 0, 0),
  (107945188, 30, -1001620681085, 0, 2, 0),
  (107945188, 31, -1001620681085, 3, 0, 0),
  (107945188, 32, -1001620681085, 2, 1, 0)
;

COMMIT;
SQL

sqlite3 "$DB_FILE" < "$TMP_SQL"
echo "Predictions imported/updated."
