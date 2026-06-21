import logging

from app.core import group_user

logger = logging.getLogger(__name__)


#
# Stats and ranking commands
#
def build_stats_handlers(service):
    def _score_medal(user_score_count: int, all_user_score_counts: list[int]) -> str:
        if user_score_count <= 0:
            return ""

        top_counts = sorted({count for count in all_user_score_counts if count > 0}, reverse=True)[:3]
        medals = {
            0: " 🥇",
            1: " 🥈",
            2: " 🥉",
        }
        for index, count in enumerate(top_counts):
            if user_score_count == count:
                return medals[index]
        return ""

    def _rank_medal(rank: int | None) -> str:
        medals = {
            1: " 🥇",
            2: " 🥈",
            3: " 🥉",
        }
        return medals.get(rank, "") if rank else ""

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
        group_rankings = service.get_group_rankings(group_id)
        user_rank = next(
            (index for index, (member_id, _username, _points) in enumerate(group_rankings, start=1) if member_id == user.id),
            None,
        )
        scores = [item[2] for item in predictions.values()]
        group_users = service.get_group_users_from_predictions(group_id)
        score_counts_by_user = {}
        for member_id, _ in group_users:
            member_scores = [item[2] for item in service.get_user_predictions(member_id, group_id).values()]
            score_counts_by_user[member_id] = {
                10: member_scores.count(10),
                7: member_scores.count(7),
                5: member_scores.count(5),
                4: member_scores.count(4),
            }

        played_games_count = service.current_game()
        predicted_played_games_count = sum(
            1
            for game_id in predictions
            if game_id <= played_games_count and service.game_exists(game_id)
        )
        coverage = predicted_played_games_count * 100 // played_games_count if played_games_count else 0
        score_10_count = scores.count(10)
        score_7_count = scores.count(7)
        win_count = scores.count(5) + scores.count(4)

        text = f"@{user.username}\nآمار شما در این گروه:"
        if user_rank:
            text += f"\n\nرتبه: {user_rank}{_rank_medal(user_rank)}"
        text += f"\n{len(predictions)} پیش‌بینی (برای {predicted_played_games_count} بازی برگزار شده)"
        text += f"\nپیش‌بینی {coverage}٪ بازی‌ها تا کنون ({predicted_played_games_count}/{played_games_count})"
       
        text += f"\n\nاز {predicted_played_games_count} پیش‌بینی انجام شده: "
        text += (
            f"\n{score_10_count} پیش‌بینی دقیق"
            f"{_score_medal(score_10_count, [counts[10] for counts in score_counts_by_user.values()])}"
        )
        text += (
            f"\n{score_7_count} پیش‌بینی تفاضل"
            f"{_score_medal(score_7_count, [counts[7] for counts in score_counts_by_user.values()])}"
        )
        text += (
            f"\n{win_count} دیگر پیش‌‌‌بینی‌های برد"
            f"{_score_medal(win_count, [counts[5] + counts[4] for counts in score_counts_by_user.values()])}"
        )
        avg_den = min(played_games_count, len(scores)) if scores and played_games_count else 1
        text += f"\nمیانگین {round(sum(scores) / avg_den, 2) if scores else 0} امتیاز از هر پیش‌بینی"

        text += "\n\nآخرین پیش‌بینی‌ها"
        if predictions:
            game_id = max(predictions.keys())
            shown = 0
            while game_id >= 1 and shown < recent_limit:
                if game_id in predictions and service.game_exists(game_id):
                    game = service.game(game_id)
                    score_text = predictions[game_id][2] if game.is_played else "np"
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
        try:
            service.fetch_result(game_id)
            game = service.game(game_id)
        except Exception as error:
            logger.exception("results_command fetch_result failed game_id=%s error=%s", game_id, error)

        goals_a = game.goals_a if game.is_played else "TBD"
        goals_b = game.goals_b if game.is_played else "TBD"
        text = f"تمام پیش‌بینی‌ها برای بازی {game_id}:\n{game.team_a} {goals_a} - {goals_b} {game.team_b}\n"
        rows = service.get_predictions_for_game(game_id, group_id)
        sorted_rows = sorted([[row[4], row[1], row[2], row[3]] for row in rows], reverse=True)
        for row in sorted_rows:
            score_text = row[0] if game.is_played else "np"
            text += f"\n{row[1]}: {row[2]} - {row[3]}: {score_text}"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    return {
        "rank": rank_command,
        "my_stats": my_stats_command,
        "results": results_command,
    }
