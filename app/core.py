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
    connection.commit()


def _is_group_chat(chat) -> bool:
    return chat is not None and chat.type in ("group", "supergroup")


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
