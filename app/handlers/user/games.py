from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

from app.core import group_user


#
# Games command
#
def build_games_handlers(service):
    def _build_games_text(visible_count: int = 12, show_all: bool = False) -> tuple[str, bool]:
        response_text = "بازی‌ها:\n"
        game_ids = service.list_game_ids()
        if not game_ids:
            return response_text, False

        if show_all:
            start_game_id = 1
            end_game_id = len(game_ids) + 1
        else:
            current_game_id = service.current_game()
            start_game_id = max(current_game_id - visible_count // 4, 1)
            start_game_id = min(max(len(game_ids) - visible_count + 1, 1), start_game_id)
            end_game_id = min(start_game_id + visible_count, len(game_ids) + 1)

        grouped_lines: dict[str, list[str]] = {}
        for game_id in range(start_game_id, end_game_id):
            if not service.game_exists(game_id):
                continue
            game = service.game(game_id)
            goals_a = game.goals_a if game.is_played else "TBD"
            goals_b = game.goals_b if game.is_played else "TBD"
            if game.played_at:
                try:
                    played_at_dt = datetime.fromisoformat(game.played_at)
                    date_label = played_at_dt.strftime("%B %d:")
                    time_label = played_at_dt.strftime("%H:%M")
                except Exception:
                    date_label = "Date Unknown:"
                    time_label = "--:--"
            else:
                date_label = "Date Unknown:"
                time_label = "--:--"

            if game.is_played:
                game_line = f"{game_id}: {game.team_a} {goals_a} - {goals_b} {game.team_b}"
            else:
                game_line = f"{game_id}: {game.team_a} ({time_label}) {game.team_b}"
            grouped_lines.setdefault(date_label, []).append(game_line)

        for date_label, lines in grouped_lines.items():
            response_text += f"\n{date_label}\n"
            for line in lines:
                response_text += f"{line}\n"

        has_more = not show_all and len(game_ids) > max(0, end_game_id - start_game_id)
        return response_text, has_more

    @group_user
    async def games_command(update, context):
        try:
            visible_count = int(context.args[0])
        except Exception:
            visible_count = 12

        response_text, has_more = _build_games_text(visible_count=visible_count, show_all=False)
        reply_markup = None
        if has_more:
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("نمایش همه بازی‌ها", callback_data="games:all")]]
            )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text, reply_markup=reply_markup)

    @group_user
    async def games_show_all_callback(update, context):
        query = update.callback_query
        await query.answer()
        response_text, _ = _build_games_text(show_all=True)
        await query.edit_message_text(text=response_text)

    return {
        "games": games_command,
        "games_show_all_callback": CallbackQueryHandler(games_show_all_callback, pattern=r"^games:all$"),
    }
