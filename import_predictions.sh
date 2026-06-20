#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_FILE="${DB_FILE:-${SCRIPT_DIR}/db.sqlite3}"
GROUP_ID=${GROUP_ID:--1001620681085}

command -v sqlite3 >/dev/null || { echo "sqlite3 is required" >&2; exit 1; }

TMP_DATA="$(mktemp)"
trap 'rm -f "$TMP_DATA"' EXIT

cat > "$TMP_DATA" <<'DATA'
MrAmirmdm|29|2|1
amirmahdi_ebi|29|2|1
EhsanJamalu|29|3|1
alznez|29|1|1
MrAmirmdm|30|0|2
MrAmirmdm|31|3|0
MrAmirmdm|32|1|0
amirmahdi_ebi|30|1|2
amirmahdi_ebi|31|3|0
amirmahdi_ebi|32|2|0
alznez|30|0|2
alznez|31|3|0
alznez|32|2|1
DATA

sqlite3 "$DB_FILE" "BEGIN IMMEDIATE;"

while IFS='|' read -r username game_id pred_a pred_b; do
  [ -z "${username:-}" ] && continue

  user_id="$(sqlite3 "$DB_FILE" "SELECT t_id FROM Users WHERE username='${username}' LIMIT 1;")"
  if [ -z "$user_id" ]; then
    echo "Error: unknown user '$username'" >&2
    sqlite3 "$DB_FILE" "ROLLBACK;"
    exit 1
  fi

  if [ -z "$(sqlite3 "$DB_FILE" "SELECT id FROM Games WHERE id='${game_id}' LIMIT 1;")" ]; then
    echo "Error: unknown game '$game_id'" >&2
    sqlite3 "$DB_FILE" "ROLLBACK;"
    exit 1
  fi

  exists="$(sqlite3 "$DB_FILE" "SELECT COUNT(1) FROM Predictions WHERE user=$user_id AND game=$game_id AND group_id=$GROUP_ID;")"
  if [ "$exists" = "0" ]; then
    sqlite3 "$DB_FILE" "INSERT INTO Predictions (user, game, group_id, pred_a, pred_b, score)
      VALUES ($user_id, $game_id, $GROUP_ID, $pred_a, $pred_b, 0);"
  else
    sqlite3 "$DB_FILE" "UPDATE Predictions
      SET pred_a=$pred_a, pred_b=$pred_b, score=0
      WHERE user=$user_id AND game=$game_id AND group_id=$GROUP_ID;"
  fi
done < "$TMP_DATA"

sqlite3 "$DB_FILE" "COMMIT;"
echo "Predictions imported/updated."
