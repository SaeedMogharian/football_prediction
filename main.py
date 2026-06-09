import logging
from datetime import datetime

from telegram import BotCommand
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
    prediction_close_minutes = int(settings.get("prediction_close_minutes", 0))
    reminder_offsets_minutes = settings.get("reminder_offsets_minutes", [10, 1])
    timezone_name = settings.get("timezone", "UTC")
    if not isinstance(reminder_offsets_minutes, list):
        reminder_offsets_minutes = [10, 1]
    reminder_offsets_minutes = [int(item) for item in reminder_offsets_minutes]

    connection = create_connection("db.sqlite3")
    cursor = connection.cursor()

    init_db(cursor, connection, "schema.sql")
    service = Service(
        cursor,
        connection,
        prediction_close_minutes=prediction_close_minutes,
        timezone_name=timezone_name,
    )

    handlers = build_handlers(service, admin_ids, is_open_signup)

    async def post_init(application):
        await application.bot.set_my_commands(
            [
                BotCommand("start", "شروع و ثبت‌نام"),
                BotCommand("predict", "ثبت پیش‌بینی"),
                BotCommand("games", "لیست بازی‌ها"),
                BotCommand("rank", "رده‌بندی گروه"),
                BotCommand("my_stats", "آمار شخصی"),
                BotCommand("results", "نتایج پیش‌بینی‌ها"),
                BotCommand("cancel", "لغو ثبت پیش‌بینی"),
                BotCommand("set_time", "تنظیم زمان بازی (ادمین)"),
            ]
        )

    application = ApplicationBuilder().token(bot_token).post_init(post_init).build()
    application.bot_data["service"] = service
    application.bot_data["admin_ids"] = admin_ids
    application.bot_data["reminder_offsets_minutes"] = reminder_offsets_minutes
    application.bot_data["scheduled_recalc_markers"] = set()

    async def send_scheduled_reminders(context):
        service_obj: Service = context.application.bot_data["service"]
        offsets = context.application.bot_data.get("reminder_offsets_minutes", [10, 1])
        now = datetime.now(service_obj.timezone)

        for game in service_obj.games_with_datetime():
            if game.is_played:
                continue
            played_at = service_obj.get_game_played_at_datetime(game)
            if played_at is None:
                continue

            delta_seconds = (played_at - now).total_seconds()
            if delta_seconds < -60:
                continue

            for offset in offsets:
                target_seconds = int(offset) * 60
                if abs(delta_seconds - target_seconds) <= 150:
                    text = f"یادآوری: بازی شماره {game.id} تا {int(offset)} دقیقه دیگر شروع می‌شود.\nپیش‌بینی‌هاتون رو ثبت کنید:"
                    for group_id in service_obj.list_verified_group_ids():
                        pending_usernames = service_obj.get_pending_prediction_usernames(game.id, group_id)
                        if not pending_usernames:
                            continue
                        message = text + "".join(f"\n@{username}" for username in pending_usernames)
                        await context.bot.send_message(chat_id=group_id, text=message)
                    break

    async def run_scheduled_recalc_scores(context):
        service_obj: Service = context.application.bot_data["service"]
        now = datetime.now(service_obj.timezone)
        markers: set[str] = context.application.bot_data.setdefault("scheduled_recalc_markers", set())
        trigger_minutes = (45, 90)
        trigger_window_seconds = 5 * 60

        for game in service_obj.games_with_datetime():
            played_at = service_obj.get_game_played_at_datetime(game)
            if played_at is None:
                continue
            elapsed_seconds = (now - played_at).total_seconds()
            if elapsed_seconds < 0:
                continue

            for minute in trigger_minutes:
                marker = f"{game.id}:{played_at.isoformat()}:{minute}"
                if marker in markers:
                    continue
                target_seconds = minute * 60
                if abs(elapsed_seconds - target_seconds) <= trigger_window_seconds:
                    service_obj.calculate_user_scores()
                    markers.add(marker)
                    logging.info("Scheduled recalc_scores executed for game %s at +%s minutes", game.id, minute)

    job_queue = getattr(application, "_job_queue", None)
    if job_queue is not None:
        job_queue.run_repeating(send_scheduled_reminders, interval=150, first=15, name="scheduled_game_reminders")
        job_queue.run_repeating(run_scheduled_recalc_scores, interval=300, first=20, name="scheduled_recalc_scores")
    else:
        logging.warning(
            "JobQueue is unavailable. Install with: pip install \"python-telegram-bot[job-queue]\""
        )

    application.add_handler(CommandHandler("start", handlers["start"]))
    application.add_handler(handlers["predict_conversation"])
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
    application.add_handler(CommandHandler("set_time", handlers["set_time"]))
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
