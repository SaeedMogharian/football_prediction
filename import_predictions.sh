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
  (106872961, 61, -1001620681085, 1, 3, 0),
  (106872961, 62, -1001620681085, 2, 0, 0)
;

COMMIT;
SQL

sqlite3 "$DB_FILE" < "$TMP_SQL"
echo "Predictions imported/updated."
