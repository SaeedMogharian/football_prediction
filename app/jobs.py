from datetime import datetime
import logging

from app.services import Service


async def run_scheduled_fetch_results(context):
    service_obj: Service = context.application.bot_data["service"]
    now = datetime.now(service_obj.timezone)

    for game in service_obj.games_with_datetime():
        if service_obj.is_result_final(game):
            continue
        played_at = service_obj.get_game_played_at_datetime(game)
        if played_at is None:
            continue
        elapsed_minutes = (now - played_at).total_seconds() / 60
        if elapsed_minutes < 0 or elapsed_minutes > 120:
            continue

        try:
            fetched = service_obj.fetch_result(game.id)
            logging.info(
                "event=scheduled_fetch_result game_id=%s elapsed_minutes=%.1f fetched=%s",
                game.id,
                elapsed_minutes,
                bool(fetched),
            )
            if fetched:
                service_obj.calculate_user_scores()
        except Exception as error:
            logging.exception(
                "event=scheduled_fetch_result_failed game_id=%s error=%s",
                game.id,
                error,
            )
