import json
import sqlite3
from pathlib import Path
from functools import wraps


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
        connection.execute("PRAGMA foreign_keys = ON")
        print("Connection to SQLite DB successful")
    except sqlite3.Error as error:
        print(f"The error '{error}' occurred")
    return connection


def init_db(cursor, connection, schema_path: str = "schema.sql"):
    with open(schema_path, "r") as file:
        cursor.executescript(file.read())
    cursor.execute("PRAGMA table_info(Users)")
    user_columns = [row[1] for row in cursor.fetchall()]
    if "score" in user_columns:
        cursor.execute("PRAGMA foreign_keys = OFF")
        cursor.execute("ALTER TABLE Users RENAME TO Users_old")
        cursor.execute(
            """
            CREATE TABLE Users (
                t_id INTEGER NOT NULL UNIQUE,
                username TEXT UNIQUE,
                PRIMARY KEY(t_id)
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO Users (t_id, username)
            SELECT t_id, username FROM Users_old
            """
        )

    cursor.execute("PRAGMA foreign_keys = OFF")
    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """
    )
    table_names = [row[0] for row in cursor.fetchall()]
    for table_name in table_names:
        if table_name in {"Users", "Users_old"}:
            continue
        cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        fk_rows = cursor.fetchall()
        if not any(row[2] == "Users_old" for row in fk_rows):
            continue
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        )
        create_sql_row = cursor.fetchone()
        if not create_sql_row or not create_sql_row[0]:
            continue
        create_sql = create_sql_row[0].replace("REFERENCES \"Users_old\"", "REFERENCES \"Users\"")
        create_sql = create_sql.replace("REFERENCES Users_old", "REFERENCES Users")
        temp_table_name = f"{table_name}__tmp_fix_users_fk"
        temp_create_sql = create_sql.replace(
            f"CREATE TABLE {table_name}",
            f"CREATE TABLE {temp_table_name}",
            1,
        ).replace(
            f'CREATE TABLE "{table_name}"',
            f'CREATE TABLE "{temp_table_name}"',
            1,
        )
        cursor.execute(temp_create_sql)
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        column_sql = ", ".join(f'"{column}"' for column in columns)
        cursor.execute(f'INSERT INTO "{temp_table_name}" ({column_sql}) SELECT {column_sql} FROM "{table_name}"')
        cursor.execute(f'DROP TABLE "{table_name}"')
        cursor.execute(f'ALTER TABLE "{temp_table_name}" RENAME TO "{table_name}"')
    cursor.execute("DROP TABLE IF EXISTS Users_old")
    cursor.execute("PRAGMA foreign_keys = ON")

    cursor.execute("PRAGMA table_info(Games)")
    game_columns = {row[1] for row in cursor.fetchall()}
    if "played_at" not in game_columns:
        cursor.execute('ALTER TABLE Games ADD COLUMN played_at TEXT')
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS UserGroupScores (
            user_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, group_id),
            FOREIGN KEY(user_id) REFERENCES Users(t_id) ON DELETE CASCADE,
            FOREIGN KEY(group_id) REFERENCES Groups(chat_id) ON DELETE CASCADE
        )
        """
    )
    connection.commit()

#
# General Helper
#
def _is_group_chat(chat) -> bool:
    return chat is not None and chat.type in ("group", "supergroup")

#
# Decorators
#
def super_admin(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        admin_ids = context.application.bot_data["admin_ids"]
        user_id = update.effective_user.id
        if user_id not in admin_ids:
            print("Unauthorized: super admin required.")
            return
        return await func(update, context, *args, **kwargs)

    return wrapped


def group_user(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        service = context.application.bot_data["service"]
        admin_ids = context.application.bot_data["admin_ids"]
        user_id = update.effective_user.id
        chat = update.effective_chat
        is_super_admin = user_id in admin_ids

        if not is_super_admin and not _is_group_chat(chat):
            await context.bot.send_message(
                chat_id=chat.id,
                text="این دستور فقط در گروه قابل اجرا است.",
            )
            return
        if not is_super_admin and not service.is_group_registered(chat.id):
            await context.bot.send_message(
                chat_id=chat.id,
                text="این گروه هنوز ثبت نشده است. از ادمین گروه بخواهید دستور /request_group_verification را اجرا کند.",
            )
            return
        if not is_super_admin and not service.is_group_verified(chat.id):
            await context.bot.send_message(
                chat_id=chat.id,
                text="این گروه هنوز تایید نشده است. از ادمین گروه بخواهید دستور /request_group_verification را اجرا کند.",
            )
            return
        if not service.user_exists(user_id):
            await context.bot.send_message(
                chat_id=chat.id,
                text="برای استفاده از این دستور ابتدا /start را اجرا کنید، سپس دوباره تلاش کنید.",
            )
            return
        return await func(update, context, *args, **kwargs)

    return wrapped


def group_admin(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        service = context.application.bot_data["service"]
        admin_ids = context.application.bot_data["admin_ids"]
        user_id = update.effective_user.id
        chat = update.effective_chat

        if not _is_group_chat(chat):
            await context.bot.send_message(chat_id=chat.id, text="این دستور فقط در گروه قابل اجرا است.")
            return
        if not service.is_group_registered(chat.id):
            await context.bot.send_message(
                chat_id=chat.id,
                text="این گروه هنوز ثبت نشده است. از ادمین گروه بخواهید دستور /request_group_verification را اجرا کند.",
            )
            return
        if not service.is_group_verified(chat.id):
            await context.bot.send_message(
                chat_id=chat.id,
                text="این گروه هنوز تایید نشده است. از ادمین گروه بخواهید دستور /request_group_verification را اجرا کند.",
            )
            return
        if user_id in admin_ids:
            return await func(update, context, *args, **kwargs)

        chat_admins = await context.bot.get_chat_administrators(chat.id)
        if any(admin.user.id == user_id for admin in chat_admins):
            return await func(update, context, *args, **kwargs)

        await context.bot.send_message(chat_id=chat.id, text="فقط ادمین گروه یا ادمین سراسری می‌تواند این دستور را اجرا کند.")
        return

    return wrapped
