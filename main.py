import logging

from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler

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
    admin_ids = set(map(int, settings["admins"]))
    is_open_signup = settings["is_open"]

    connection = create_connection("db.sqlite3")
    cursor = connection.cursor()

    init_db(cursor, connection, "schema.sql")
    service = Service(cursor, connection)

    handlers = build_handlers(service, admin_ids, is_open_signup)

    application = ApplicationBuilder().token(bot_token).build()
    application.bot_data["service"] = service
    application.bot_data["admin_ids"] = admin_ids

    application.add_handler(CommandHandler("start", handlers["start"]))
    application.add_handler(CommandHandler("predict", handlers["predict"]))
    application.add_handler(CommandHandler("games", handlers["games"]))
    application.add_handler(CommandHandler("rank", handlers["rank"]))
    application.add_handler(CommandHandler("my_stats", handlers["my_stats"]))
    application.add_handler(CommandHandler("results", handlers["results"]))
    application.add_handler(CommandHandler("remind", handlers["remind"]))
    application.add_handler(CommandHandler("group_stats", handlers["group_stats"]))
    application.add_handler(CommandHandler("request_group_verification", handlers["request_group_verification"]))
    application.add_handler(CommandHandler("verify_group", handlers["verify_group"]))
    application.add_handler(CommandHandler("pending_groups", handlers["pending_groups"]))
    application.add_handler(CommandHandler("recalc_scores", handlers["recalc_scores"]))
    application.add_handler(CommandHandler("set_result", handlers["set_result"]))
    application.add_handler(CommandHandler("close_predictions", handlers["close_predictions"]))
    application.add_handler(CommandHandler("open_predictions", handlers["open_predictions"]))
    application.add_handler(CommandHandler("delete_user", handlers["delete_user"]))
    application.add_handler(CommandHandler("add_teams", handlers["add_teams"]))
    application.add_handler(CommandHandler("add_games", handlers["add_games"]))
    application.add_handler(MessageHandler(filters.COMMAND, handlers["unknown"]))
    application.run_polling()


if __name__ == "__main__":
    main()
