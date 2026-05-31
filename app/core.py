import json
import sqlite3
from pathlib import Path
from functools import wraps

#
# States
#
Users = {}
Games = {}
Predictions = {}

#
# Config
#
def load_settings(path: str = "settings.json"):
    with Path(path).open("r") as file:
        return json.load(file)

#
# DB
#
def create_connection(db_path: str = "db.sqlite3"):
    connection = None
    try:
        connection = sqlite3.connect(db_path)
        print("Connection to SQLite DB successful")
    except sqlite3.Error as error:
        print(f"The error '{error}' occurred")
    return connection


def init_db(cursor, connection, schema_path: str = "schema.sql"):
    with open(schema_path, "r") as file:
        cursor.executescript(file.read())
    connection.commit()

#
# Auth
#
def auth(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_message.from_user.id
        if user_id not in Users:
            print("Unauthorized access denied.")
            return
        return await func(update, context)

    return wrapped


def restricted(admins):
    def decorator(func):
        @wraps(func)
        async def wrapped(update, context, *args, **kwargs):
            user_id = update.effective_message.from_user.id
            if user_id not in admins:
                print("Unauthorized only admin access.")
                return
            return await func(update, context)

        return wrapped

    return decorator
