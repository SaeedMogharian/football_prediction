import logging

from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler

from app.catalog import load_catalog
from app.core import load_settings, create_connection, init_db
from app.services import Service
from app.handlers import build_handlers


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def main():
    settings = load_settings()
    bot_token = settings["token"]
    admins = set(map(int, settings["admins"]))
    is_open = settings["is_open"]

    catalog = load_catalog("data/catalog.jsonc")

    connection = create_connection("db.sqlite3")
    cursor = connection.cursor()

    init_db(cursor, connection, "schema.sql")
    service = Service(cursor, connection, catalog)

    handlers = build_handlers(service, admins, is_open)

    application = ApplicationBuilder().token(bot_token).build()
    application.bot_data["service"] = service

    application.add_handler(CommandHandler("start", handlers["start"]))
    application.add_handler(CommandHandler("pred", handlers["pred"]))
    application.add_handler(CommandHandler("games", handlers["games"]))
    application.add_handler(CommandHandler("rank", handlers["rank"]))
    application.add_handler(CommandHandler("mine", handlers["mine"]))
    application.add_handler(CommandHandler("res", handlers["res"]))
    application.add_handler(CommandHandler("warn", handlers["warn"]))
    application.add_handler(CommandHandler("calc", handlers["calc"]))
    application.add_handler(CommandHandler("set", handlers["set"]))
    application.add_handler(CommandHandler("play", handlers["play"]))
    application.add_handler(CommandHandler("unplay", handlers["unplay"]))
    application.add_handler(CommandHandler("delu", handlers["delu"]))
    application.add_handler(MessageHandler(filters.COMMAND, handlers["unknown"]))
    application.run_polling()


if __name__ == "__main__":
    main()
