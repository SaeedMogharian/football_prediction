from telegram import Update
from telegram.ext import ContextTypes

from app.core import auth


#
# Public entry handlers
#
def build_user_handlers(service, is_open):
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        telegram_user = update.effective_message.from_user
        response_text = "سلام {}".format(telegram_user.first_name)

        try:
            if not telegram_user.username:
                raise NameError

            if not service.user_exists(telegram_user.id):
                if is_open:
                    service.add_user(telegram_user)
                else:
                    response_text += "\n\n شرمنده عضویت نداریم!"

            if service.user_exists(telegram_user.id):
                response_text += "\nبه بات پیش‌بینی خوش اومدی!"
                response_text += "\nبرای پیش بینی لیست بازی‌ها رو از /games ببین و این جوری پیش‌بینی‌ت رو ثبت کن:"
                response_text += "\n/predict <game_id> <team_a_goals> <team_b_goals>"

            await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="بدون داشتن یوزرنیم نمی‌توانید از بات استفاده کنید")

    @auth
    async def games_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        response_text = "بازی‌ها:\n"
        game_ids = service.list_game_ids()
        if not game_ids:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)
            return

        try:
            visible_count = int(context.args[0])
        except Exception:
            visible_count = 12

        current_game_id = service.current_game()
        start_game_id = max(current_game_id - visible_count // 4, 1)
        start_game_id = min(max(len(game_ids) - visible_count + 1, 1), start_game_id)
        end_game_id = min(start_game_id + visible_count, len(game_ids) + 1)

        for game_id in range(start_game_id, end_game_id):
            if not service.game_exists(game_id):
                continue
            game = service.game(game_id)
            goals_a = game.goals_a if game.is_played else "TBD"
            goals_b = game.goals_b if game.is_played else "TBD"
            response_text += f"{game_id}: {game.team_a} {goals_a} - {goals_b} {game.team_b}\n"

        await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)

    @auth
    async def predict_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        telegram_user = update.effective_message.from_user
        response_text = "@{}".format(telegram_user.username)
        try:
            prediction_input = (
                telegram_user.id,
                int(context.args[0]),
                int(context.args[1]),
                int(context.args[2]),
                0,
            )
            is_open_for_prediction = service.is_prediction_open(prediction_input[1])
            is_new_prediction = service.is_new_prediction(prediction_input[0], prediction_input[1])

            if service.is_valid_prediction_input(prediction_input):
                game = service.game(prediction_input[1])
                if is_open_for_prediction and is_new_prediction:
                    response_text += "\n پیش بینی شما اضافه شد:"
                    response_text += f"\n{prediction_input[1]}: {game.team_a} {prediction_input[2]} - {prediction_input[3]} {game.team_b}"
                    service.add_prediction(prediction_input)
                elif not is_open_for_prediction:
                    response_text += "\n این بازی برای پیش‌بینی در دسترس نیست"
                elif not is_new_prediction:
                    response_text += "\nشما قبلا این بازی را پیش بینی کرده‌اید\n لطفا دقت کنید :)\n"
                    existing_prediction = service.get_prediction(prediction_input[0], prediction_input[1])
                    if existing_prediction and existing_prediction != prediction_input[2:]:
                        service.update_prediction(prediction_input)
                        response_text += "\n پیش بینی شما تغییر کرد:"
                        response_text += f"\n{prediction_input[1]}: {game.team_a} {prediction_input[2]} - {prediction_input[3]} {game.team_b}"
                await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)
            else:
                raise ValueError
        except Exception:
            response_text = "لطفا طبق الگوی خواسته شده و از بین بازی‌های موجود پیش‌بینی را وارد کنید"
            response_text += "\n/predict <game_id> <team_a_goals> <team_b_goals>"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)

    @auth
    async def rank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        response_text = "رده‌بندی:\n"
        ranked_players = sorted(service.get_all_users(), reverse=True, key=lambda user_row: user_row[2])
        if not ranked_players:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)
            return

        current_score = ranked_players[0][2]
        rank_position = 1
        tied_offset = 0
        for player in ranked_players:
            if player[2] < current_score:
                rank_position += ranked_players.index(player) - tied_offset
                tied_offset = ranked_players.index(player)
                current_score = player[2]
            response_text += "{} - {} : {}\n".format(rank_position, player[1], player[2])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)

    @auth
    async def my_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            recent_limit = int(context.args[0])
        except Exception:
            recent_limit = 10

        telegram_user = update.effective_message.from_user
        response_text = "@{}\nآمار شما:".format(telegram_user.username)

        user_predictions = service.get_user_predictions(telegram_user.id)
        prediction_scores = [prediction[2] for prediction in user_predictions.values()]

        played_games_count = service.current_game()
        prediction_coverage = min(len(user_predictions), played_games_count) * 100 // played_games_count if played_games_count else 0
        current_user = service.get_user(telegram_user.id)

        response_text += "\n {} پیش‌بینی ({} بازی برگزار شده) ".format(len(user_predictions), played_games_count)
        response_text += "\n امتیاز ثبت شده: {}".format(current_user[2] if current_user else 0)
        response_text += "\n پیش بینی {}٪ بازی‌ها تا کنون".format(prediction_coverage)
        response_text += "\n {} پیش‌بینی دقیق ".format(prediction_scores.count(10))
        average_denominator = min(played_games_count, len(prediction_scores)) if prediction_scores and played_games_count else 1
        response_text += "\n میانگین {} امتیاز از هر پیش‌بینی. ".format(
            round(sum(prediction_scores) / average_denominator, 2) if prediction_scores else 0
        )

        response_text += "\n\nآخرین پیش‌بینی‌ها "
        if user_predictions:
            game_id = max(user_predictions.keys())
            shown = 0
            while game_id >= 1 and shown < recent_limit:
                if game_id in user_predictions and service.game_exists(game_id):
                    game = service.game(game_id)
                    score_text = user_predictions[game_id][2] if game.is_played else "np"
                    response_text += (
                        f"\n{game_id}: {game.team_a} {user_predictions[game_id][0]} - "
                        f"{user_predictions[game_id][1]} {game.team_b}: {score_text}"
                    )
                    shown += 1
                game_id -= 1

        await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)

    @auth
    async def game_results_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        def format_results_for_game(text, game_id):
            game = service.game(game_id)
            text += f"\n\nبرای بازی {game_id}: {game.team_a} {game.goals_a} - {game.goals_b} {game.team_b}"
            rows = service.get_predictions_for_game(game_id)
            sorted_rows = sorted([[row[4], row[1], row[2], row[3]] for row in rows], reverse=True)
            for row in sorted_rows:
                text += "\n{}: {} - {}: {}".format(row[1], row[2], row[3], row[0])
            return text

        try:
            requested_game_id = int(context.args[0])
            game_id = requested_game_id if service.game_exists(requested_game_id) else service.current_game()
        except Exception:
            game_id = service.current_game()

        if service.game_exists(game_id) and service.game(game_id).is_played:
            response_text = ":تمام پیش‌‌بینی‌ها"
            try:
                service.fetch_result(game_id)
            except Exception:
                print("Google Didn't Respond!")
            response_text = format_results_for_game(response_text, game_id)
        else:
            response_text = "بازی شماره {} هنوز برگزار نشده است!".format(game_id)

        await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)

    return {
        "start": start_command,
        "predict": predict_command,
        "games": games_command,
        "rank": rank_command,
        "my_stats": my_stats_command,
        "results": game_results_command,
    }
