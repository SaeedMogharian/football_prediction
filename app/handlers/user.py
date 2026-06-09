from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from datetime import datetime

from app.core import group_user

SELECT_GAME, ENTER_SCORE_A, ENTER_SCORE_B = range(3)


def build_user_handlers(service, is_open_signup):
    def _predict_user_label(user) -> str:
        if user.username:
            return f"@{user.username}"
        return user.first_name or str(user.id)

    def _predict_header(user) -> str:
        return f"{_predict_user_label(user)}"

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
        text += "\nلیست بازی‌ها رو از /games ببین."
        text += "\nبرای ثبت پیش‌بینی دستور /predict رو بزن."
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

            game_line = f"{game_id}: {game.team_a} {goals_a} -  {time_label} - {goals_b} {game.team_b}"
            grouped_lines.setdefault(date_label, []).append(game_line)

        for date_label, lines in grouped_lines.items():
            response_text += f"\n{date_label}\n"
            for line in lines:
                response_text += f"{line}\n"

        await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)

    def _open_games_for_prediction(visible_count: int = 8):
        game_ids = service.list_game_ids()
        if not game_ids:
            return []

        current_game_id = service.current_game()
        start_game_id = max(current_game_id - visible_count // 4, 1)
        start_game_id = min(max(len(game_ids) - visible_count + 1, 1), start_game_id)
        end_game_id = min(start_game_id + visible_count, len(game_ids) + 1)

        open_games = []
        for game_id in range(start_game_id, end_game_id):
            if service.game_exists(game_id) and service.is_prediction_open(game_id):
                open_games.append(game_id)
        return open_games

    def _build_game_keyboard():
        open_games = _open_games_for_prediction()
        if not open_games:
            return None

        rows = []
        row = []
        for game_id in open_games:
            game = service.game(game_id)
            label = f"{game_id}: {game.team_a} - {game.team_b}"
            row.append(InlineKeyboardButton(label, callback_data=f"predict:game:{game_id}"))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        return InlineKeyboardMarkup(rows)

    def _build_single_score_keyboard(prefix: str):
        rows = []
        row = []
        for score in range(6):
            row.append(InlineKeyboardButton(str(score), callback_data=f"predict:{prefix}:{score}"))
            if len(row) == 3:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        return InlineKeyboardMarkup(rows)

    def _parse_single_score(text: str):
        value = int(text.strip())
        if value < 0:
            raise ValueError
        return value

    def _parse_score(text: str):
        cleaned = text.strip()
        for separator in ("-", " ", ":"):
            if separator in cleaned:
                parts = cleaned.split(separator, 1)
                if len(parts) == 2:
                    return int(parts[0].strip()), int(parts[1].strip())
        raise ValueError

    def _save_prediction(user_id: int, group_id: int, game_id: int, pred_a: int, pred_b: int) -> str:
        prediction_input = (user_id, game_id, group_id, pred_a, pred_b, 0)
        if not service.is_valid_prediction_input(prediction_input):
            raise ValueError

        game = service.game(game_id)
        is_open_for_prediction = service.is_prediction_open(game_id)
        is_new_prediction = service.is_new_prediction(user_id, game_id, group_id)

        if is_open_for_prediction and is_new_prediction:
            service.add_prediction(prediction_input)
            return f"پیش‌بینی شما اضافه شد:\n{game_id}: {game.team_a} {pred_a} - {pred_b} {game.team_b}"
        if not is_open_for_prediction:
            return "این بازی برای پیش‌بینی در دسترس نیست"

        existing_prediction = service.get_prediction(user_id, game_id, group_id)
        if existing_prediction and existing_prediction != (pred_a, pred_b):
            service.update_prediction(prediction_input)
            return f"پیش‌بینی شما تغییر کرد:\n{game_id}: {game.team_a} {pred_a} - {pred_b} {game.team_b}"
        return "شما قبلا این بازی را پیش‌بینی کرده‌اید"

    async def _send_prediction_result(update: Update, context: ContextTypes.DEFAULT_TYPE, result_text: str):
        user = update.effective_user
        chat_id = update.effective_chat.id
        await context.bot.send_message(chat_id=chat_id, text=f"{_predict_header(user)}\n{result_text}")

    @group_user
    async def predict_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if chat.type not in ("group", "supergroup"):
            await context.bot.send_message(
                chat_id=chat.id,
                text="دستور /predict فقط داخل گروه قابل اجراست چون پیش‌بینی به گروه وابسته است.",
            )
            return ConversationHandler.END

        if len(context.args) >= 3:
            user = update.effective_user
            group_id = update.effective_chat.id
            try:
                result_text = _save_prediction(
                    user.id,
                    group_id,
                    int(context.args[0]),
                    int(context.args[1]),
                    int(context.args[2]),
                )
                await _send_prediction_result(update, context, result_text)
            except Exception:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="لطفا پیش‌بینی را درست وارد کنید:\n/predict <game_id> <team_a_goals> <team_b_goals>",
                )
            return ConversationHandler.END

        keyboard = _build_game_keyboard()
        if keyboard is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="فعلا بازی باز برای پیش‌بینی وجود ندارد.",
            )
            return ConversationHandler.END

        context.user_data.pop("predict_game_id", None)
        context.user_data.pop("predict_score_a", None)
        user = update.effective_user
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"{_predict_header(user)}\n"
                " یک بازی را از لیست انتخاب کنید\n\n"
                "برای لغو: /cancel"
            ),
            reply_markup=keyboard,
        )
        return SELECT_GAME

    @group_user
    async def predict_game_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        game_id = int(query.data.rsplit(":", 1)[-1])
        game = service.game(game_id)
        user = update.effective_user

        context.user_data["predict_game_id"] = game_id
        context.user_data.pop("predict_score_a", None)
        await query.edit_message_text(
            text=(
                f"{_predict_header(user)}\n\n"
                f"بازی {game_id}: {game.team_a} - {game.team_b}\n"
                f" گل‌های {game.team_a} را انتخاب کنید)\n"
                "یا عدد دلخواه بفرستید:"
            ),
            reply_markup=_build_single_score_keyboard("scorea"),
        )
        return ENTER_SCORE_A

    @group_user
    async def predict_score_a_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        _, _, pred_a = query.data.split(":")
        game_id = context.user_data.get("predict_game_id")
        if game_id is None:
            await query.edit_message_text(text="ابتدا یک بازی انتخاب کنید. دوباره /predict را بزنید.")
            return ConversationHandler.END

        context.user_data["predict_score_a"] = int(pred_a)
        game = service.game(game_id)
        user = update.effective_user
        await query.edit_message_text(
            text=(
                f"{_predict_header(user)}\n\n"
                f"بازی {game_id}: {game.team_a} - {game.team_b}\n"
                f"گل‌های {game.team_b} را انتخاب کنید)\n"
                "یا عدد دلخواه بفرستید:"
            ),
            reply_markup=_build_single_score_keyboard("scoreb"),
        )
        return ENTER_SCORE_B

    @group_user
    async def predict_enter_score_a(update: Update, context: ContextTypes.DEFAULT_TYPE):
        game_id = context.user_data.get("predict_game_id")
        if game_id is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="ابتدا یک بازی انتخاب کنید. دوباره /predict را بزنید.",
            )
            return ConversationHandler.END

        try:
            pred_a = _parse_single_score(update.message.text)
            context.user_data["predict_score_a"] = pred_a
        except Exception:
            game = service.game(game_id)
            user = update.effective_user
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    f"{_predict_header(user)}\n"
                    f"گل‌های {game.team_a} را درست وارد کنید.\n"
                    "مثال: 0 یا 2"
                ),
                reply_markup=_build_single_score_keyboard("scorea"),
            )
            return ENTER_SCORE_A

        game = service.game(game_id)
        user = update.effective_user
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"{_predict_header(user)}\n\n"
                f"بازی {game_id}: {game.team_a} - {game.team_b}\n"
                f"گل‌های {game.team_b} را انتخاب کنید)\n"
                "یا عدد دلخواه بفرستید:"
            ),
            reply_markup=_build_single_score_keyboard("scoreb"),
        )
        return ENTER_SCORE_B

    @group_user
    async def predict_score_b_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        _, _, pred_b = query.data.split(":")
        game_id = context.user_data.get("predict_game_id")
        pred_a = context.user_data.get("predict_score_a")
        if game_id is None or pred_a is None:
            await query.edit_message_text(text="ابتدا مراحل را کامل کنید. دوباره /predict را بزنید.")
            return ConversationHandler.END

        user = update.effective_user
        group_id = update.effective_chat.id
        try:
            result_text = _save_prediction(user.id, group_id, game_id, int(pred_a), int(pred_b))
            await query.edit_message_text(text=f"{_predict_header(user)}\n{result_text}")
        except Exception:
            await query.edit_message_text(text="ثبت پیش‌بینی ناموفق بود. دوباره /predict را بزنید.")
        context.user_data.pop("predict_game_id", None)
        context.user_data.pop("predict_score_a", None)
        return ConversationHandler.END

    @group_user
    async def predict_enter_score_b(update: Update, context: ContextTypes.DEFAULT_TYPE):
        game_id = context.user_data.get("predict_game_id")
        pred_a = context.user_data.get("predict_score_a")
        if game_id is None or pred_a is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="ابتدا مراحل را کامل کنید. دوباره /predict را بزنید.",
            )
            return ConversationHandler.END

        user = update.effective_user
        group_id = update.effective_chat.id
        try:
            pred_b = _parse_single_score(update.message.text)
            result_text = _save_prediction(user.id, group_id, game_id, pred_a, pred_b)
            await _send_prediction_result(update, context, result_text)
        except Exception:
            game = service.game(game_id)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    f"{_predict_header(user)}\n"
                    f"گل‌های {game.team_b} را درست وارد کنید.\n"
                    "مثال: 0 یا 2"
                ),
                reply_markup=_build_single_score_keyboard("scoreb"),
            )
            return ENTER_SCORE_B

        context.user_data.pop("predict_game_id", None)
        context.user_data.pop("predict_score_a", None)
        return ConversationHandler.END

    @group_user
    async def predict_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.pop("predict_game_id", None)
        context.user_data.pop("predict_score_a", None)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="ثبت پیش‌بینی لغو شد.")
        return ConversationHandler.END

    predict_conversation = ConversationHandler(
        entry_points=[CommandHandler("predict", predict_start)],
        states={
            SELECT_GAME: [
                CallbackQueryHandler(predict_game_selected, pattern=r"^predict:game:\d+$"),
            ],
            ENTER_SCORE_A: [
                CallbackQueryHandler(predict_score_a_selected, pattern=r"^predict:scorea:\d+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, predict_enter_score_a),
            ],
            ENTER_SCORE_B: [
                CallbackQueryHandler(predict_score_b_selected, pattern=r"^predict:scoreb:\d+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, predict_enter_score_b),
            ],
        },
        fallbacks=[CommandHandler("cancel", predict_cancel)],
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
        if game.is_played:
            try:
                service.fetch_result(game_id)
                game = service.game(game_id)
            except Exception:
                pass

        goals_a = game.goals_a if game.is_played else "TBD"
        goals_b = game.goals_b if game.is_played else "TBD"
        text = f"تمام پیش‌بینی‌ها برای بازی {game_id}: {game.team_a} {goals_a} - {goals_b} {game.team_b}"
        rows = service.get_predictions_for_game(game_id, group_id)
        sorted_rows = sorted([[row[4], row[1], row[2], row[3]] for row in rows], reverse=True)
        for row in sorted_rows:
            score_text = row[0] if game.is_played else "np"
            text += f"\n{row[1]}: {row[2]} - {row[3]}: {score_text}"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    return {
        "start": start_command,
        "predict_conversation": predict_conversation,
        "games": games_command,
        "rank": rank_command,
        "my_stats": my_stats_command,
        "results": results_command,
    }
