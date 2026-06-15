import logging

from app.core import group_user

logger = logging.getLogger(__name__)


#
# Stats and ranking commands
#
def build_stats_handlers(service):
    @group_user
    async def rank_command(update, context):
        group_id = update.effective_chat.id
        group_rankings = service.get_group_rankings(group_id)
        text = "رده‌بندی گروه:\n"
        for index, (_, username, points) in enumerate(group_rankings, start=1):
            text += f"{index} - {username} : {points}\n"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    @group_user
    async def my_stats_command(update, context):
        group_id = update.effective_chat.id
        user = update.effective_user
        try:
            recent_limit = int(context.args[0])
        except Exception:
            recent_limit = 10

        predictions = service.get_user_predictions(user.id, group_id)
        scores = [item[2] for item in predictions.values()]
        played_games_count = service.current_game()
        predicted_played_games_count = sum(
            1
            for game_id in predictions
            if game_id <= played_games_count and service.game_exists(game_id)
        )
        coverage = predicted_played_games_count * 100 // played_games_count if played_games_count else 0

        text = f"@{user.username}\nآمار شما در این گروه:"
        text += f"\n{len(predictions)} پیش‌بینی (برای {predicted_played_games_count} بازی برگزار شده)"
        text += f"\nپیش‌بینی {coverage}٪ بازی‌ها تا کنون ({predicted_played_games_count}/{played_games_count})"
        text += f"\n{scores.count(10)} پیش‌بینی دقیق"
        avg_den = min(played_games_count, len(scores)) if scores and played_games_count else 1
        text += f"\nمیانگین {round(sum(scores) / avg_den, 2) if scores else 0} امتیاز از هر پیش‌بینی"

        text += "\n\nآخرین پیش‌بینی‌ها"
        if predictions:
            game_id = max(predictions.keys())
            shown = 0
            while game_id >= 1 and shown < recent_limit:
                if game_id in predictions and service.game_exists(game_id):
                    game = service.game(game_id)
                    score_text = (
                        predictions[game_id][2]
                        if service.is_result_final(game)
                        else "np"
                    )
                    text += (
                        f"\n{game_id}: {game.team_a} {predictions[game_id][0]} - "
                        f"{predictions[game_id][1]} {game.team_b}: {score_text}"
                    )
                    shown += 1
                game_id -= 1

        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    @group_user
    async def results_command(update, context):
        group_id = update.effective_chat.id
        user = update.effective_user

        try:
            requested_game_id = int(context.args[0])
            game_id = requested_game_id if service.game_exists(requested_game_id) else service.current_game()
        except Exception:
            game_id = service.current_game()

        if not service.game_exists(game_id):
            await context.bot.send_message(chat_id=update.effective_chat.id, text="بازی پیدا نشد.")
            return

        game = service.game(game_id)
        logger.info(
            "results_command start user_id=%s chat_id=%s game_id=%s game_is_played=%s",
            user.id if user else None,
            group_id,
            game_id,
            service.is_result_final(game),
        )

        result_is_final = service.is_result_final(game)
        goals_a = game.goals_a if result_is_final else "TBD"
        goals_b = game.goals_b if result_is_final else "TBD"
        text = f"تمام پیش‌بینی‌ها برای بازی {game_id}:\n{game.team_a} {goals_a} - {goals_b} {game.team_b}\n"
        rows = service.get_predictions_for_game(game_id, group_id)
        sorted_rows = sorted([[row[4], row[1], row[2], row[3]] for row in rows], reverse=True)
        for row in sorted_rows:
            score_text = row[0] if result_is_final else "np"
            text += f"\n{row[1]}: {row[2]} - {row[3]}: {score_text}"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    return {
        "rank": rank_command,
        "my_stats": my_stats_command,
        "results": results_command,
    }
