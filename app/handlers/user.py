from telegram import Update
from telegram.ext import ContextTypes

from app.core import group_user


def build_user_handlers(service, is_open_signup):
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        user = update.effective_user
        admin_ids = context.application.bot_data["admin_ids"]
        is_super_admin = user.id in admin_ids

        if not is_super_admin and chat.type not in ("group", "supergroup"):
            await context.bot.send_message(
                chat_id=chat.id,
                text="این ربات در گروه کار می‌کند. لطفا ربات را به گروه اضافه کنید و دستور /start را داخل گروه اجرا کنید.",
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

        if not user.username:
            await context.bot.send_message(chat_id=chat.id, text="بدون داشتن یوزرنیم نمی‌توانید از بات استفاده کنید")
            return

        if not service.user_exists(user.id):
            if is_open_signup or is_super_admin:
                service.add_user(user)
            else:
                await context.bot.send_message(chat_id=chat.id, text="شرمنده عضویت نداریم!")
                return

        text = f"سلام {user.first_name}\nبه بات پیش‌بینی خوش اومدی!"
        text += "\nبرای پیش بینی لیست بازی‌ها رو از /games ببین و این جوری پیش‌بینی‌ت رو ثبت کن:"
        text += "\n/predict <game_id> <team_a_goals> <team_b_goals>"
        await context.bot.send_message(chat_id=chat.id, text=text)

    @group_user
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

    @group_user
    async def predict_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        group_id = update.effective_chat.id
        response_text = f"@{user.username}"
        try:
            prediction_input = (
                user.id,
                int(context.args[0]),
                group_id,
                int(context.args[1]),
                int(context.args[2]),
                0,
            )
            if not service.is_valid_prediction_input(prediction_input):
                raise ValueError

            game_id = prediction_input[1]
            game = service.game(game_id)
            is_open_for_prediction = service.is_prediction_open(game_id)
            is_new_prediction = service.is_new_prediction(user.id, game_id, group_id)

            if is_open_for_prediction and is_new_prediction:
                service.add_prediction(prediction_input)
                response_text += f"\nپیش‌بینی شما اضافه شد:\n{game_id}: {game.team_a} {prediction_input[3]} - {prediction_input[4]} {game.team_b}"
            elif not is_open_for_prediction:
                response_text += "\nاین بازی برای پیش‌بینی در دسترس نیست"
            else:
                existing_prediction = service.get_prediction(user.id, game_id, group_id)
                if existing_prediction and existing_prediction != prediction_input[3:]:
                    service.update_prediction(prediction_input)
                    response_text += f"\nپیش‌بینی شما تغییر کرد:\n{game_id}: {game.team_a} {prediction_input[3]} - {prediction_input[4]} {game.team_b}"
                else:
                    response_text += "\nشما قبلا این بازی را پیش‌بینی کرده‌اید"

            await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)
        except Exception:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="لطفا پیش‌بینی را درست وارد کنید:\n/predict <game_id> <team_a_goals> <team_b_goals>",
            )

    @group_user
    async def rank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        group_id = update.effective_chat.id
        ranked_players = service.get_group_rankings(group_id)
        ranking_by_user_id = {user_id: points for user_id, _username, points in ranked_players}
        group_rankings = []

        for user_id, username, _ in service.get_all_users():
            try:
                member = await context.bot.get_chat_member(group_id, user_id)
            except Exception:
                continue
            if member.status not in ("member", "administrator", "creator", "restricted"):
                continue
            group_rankings.append((user_id, username, ranking_by_user_id.get(user_id, 0)))

        group_rankings.sort(key=lambda item: (-item[2], item[1] or ""))
        text = "رده‌بندی گروه:\n"
        for index, (_, username, points) in enumerate(group_rankings, start=1):
            text += f"{index} - {username} : {points}\n"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    @group_user
    async def my_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        group_id = update.effective_chat.id
        user = update.effective_user
        try:
            recent_limit = int(context.args[0])
        except Exception:
            recent_limit = 10

        predictions = service.get_user_predictions(user.id, group_id)
        scores = [item[2] for item in predictions.values()]
        played_games_count = service.current_game()
        coverage = min(len(predictions), played_games_count) * 100 // played_games_count if played_games_count else 0

        text = f"@{user.username}\nآمار شما در این گروه:"
        text += f"\n{len(predictions)} پیش‌بینی ({played_games_count} بازی برگزار شده)"
        text += f"\nپیش‌بینی {coverage}٪ بازی‌ها تا کنون"
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
                    score_text = predictions[game_id][2] if game.is_played else "np"
                    text += (
                        f"\n{game_id}: {game.team_a} {predictions[game_id][0]} - "
                        f"{predictions[game_id][1]} {game.team_b}: {score_text}"
                    )
                    shown += 1
                game_id -= 1

        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    @group_user
    async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        group_id = update.effective_chat.id

        try:
            requested_game_id = int(context.args[0])
            game_id = requested_game_id if service.game_exists(requested_game_id) else service.current_game()
        except Exception:
            game_id = service.current_game()

        if not service.game_exists(game_id):
            await context.bot.send_message(chat_id=update.effective_chat.id, text="بازی پیدا نشد.")
            return

        game = service.game(game_id)
        if not game.is_played:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"بازی شماره {game_id} هنوز برگزار نشده است!")
            return

        try:
            service.fetch_result(game_id)
            game = service.game(game_id)
        except Exception:
            pass

        text = f"تمام پیش‌بینی‌ها برای بازی {game_id}: {game.team_a} {game.goals_a} - {game.goals_b} {game.team_b}"
        rows = service.get_predictions_for_game(game_id, group_id)
        sorted_rows = sorted([[row[4], row[1], row[2], row[3]] for row in rows], reverse=True)
        for row in sorted_rows:
            text += f"\n{row[1]}: {row[2]} - {row[3]}: {row[0]}"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    return {
        "start": start_command,
        "predict": predict_command,
        "games": games_command,
        "rank": rank_command,
        "my_stats": my_stats_command,
        "results": results_command,
    }
