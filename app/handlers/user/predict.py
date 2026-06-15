import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TimedOut
from telegram.ext import CallbackQueryHandler, CommandHandler, ConversationHandler, MessageHandler, filters

from app.core import group_user

SELECT_GAME, ENTER_SCORE_A, ENTER_SCORE_B = range(3)
logger = logging.getLogger(__name__)


#
# Predict command + conversation
#
def is_valid_prediction_input(service, game_id: int, pred_a: int, pred_b: int) -> bool:
    return service.game_exists(game_id) and pred_a >= 0 and pred_b >= 0


def build_predict_handlers(service):
    def _predict_user_label(user) -> str:
        if user.username:
            return f"@{user.username}"
        return user.first_name or str(user.id)

    def _predict_header(user) -> str:
        return f"{_predict_user_label(user)}"

    def _open_games_for_prediction(visible_count: int = 8):
        game_ids = service.list_game_ids()
        if not game_ids:
            return []

        open_games = []
        for game_id in game_ids:
            if service.is_prediction_open(game_id):
                open_games.append(game_id)
            if len(open_games) >= visible_count:
                break
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

    def _save_prediction(user_id: int, group_id: int, game_id: int, pred_a: int, pred_b: int) -> str:
        if not is_valid_prediction_input(service, game_id, pred_a, pred_b):
            raise ValueError
        prediction_input = (user_id, game_id, group_id, pred_a, pred_b, 0)

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

    async def _send_prediction_result(update, context, result_text: str):
        user = update.effective_user
        chat_id = update.effective_chat.id
        await context.bot.send_message(chat_id=chat_id, text=f"{_predict_header(user)}\n{result_text}")

    @group_user
    async def predict_start(update, context):
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
        context.user_data.pop("predict_input_message_id", None)
        user = update.effective_user
        try:
            sent = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    f"{_predict_header(user)}\n"
                    " یک بازی را از لیست انتخاب کنید\n"
                    "برای لغو: /cancel"
                ),
                reply_markup=keyboard,
            )
        except TimedOut:
            logger.warning(
                "event=send_message_timeout command=/predict chat_id=%s user_id=%s",
                update.effective_chat.id,
                user.id,
            )
            return ConversationHandler.END
        context.user_data["predict_input_message_id"] = sent.message_id
        return SELECT_GAME

    @group_user
    async def predict_game_selected(update, context):
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
                "یا عدد دلخواه را با ریپلای به همین پیام بفرستید:"
            ),
            reply_markup=_build_single_score_keyboard("scorea"),
        )
        context.user_data["predict_input_message_id"] = query.message.message_id
        return ENTER_SCORE_A

    @group_user
    async def predict_score_a_selected(update, context):
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
                "یا عدد دلخواه را با ریپلای به همین پیام بفرستید:"
            ),
            reply_markup=_build_single_score_keyboard("scoreb"),
        )
        context.user_data["predict_input_message_id"] = query.message.message_id
        return ENTER_SCORE_B

    @group_user
    async def predict_enter_score_a(update, context):
        game_id = context.user_data.get("predict_game_id")
        if game_id is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="ابتدا یک بازی انتخاب کنید. دوباره /predict را بزنید.",
            )
            return ConversationHandler.END

        input_message_id = context.user_data.get("predict_input_message_id")
        reply_to = update.message.reply_to_message if update.message else None
        if input_message_id is None or reply_to is None or reply_to.message_id != input_message_id:
            return ENTER_SCORE_A

        try:
            pred_a = _parse_single_score(update.message.text)
            context.user_data["predict_score_a"] = pred_a
        except Exception:
            game = service.game(game_id)
            user = update.effective_user
            sent = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    f"{_predict_header(user)}\n"
                    f"گل‌های {game.team_a} را درست وارد کنید.\n"
                    "مثال: 0 یا 2\n"
                    "عدد را با ریپلای به پیام بفرستید."
                ),
                reply_markup=_build_single_score_keyboard("scorea"),
            )
            context.user_data["predict_input_message_id"] = sent.message_id
            return ENTER_SCORE_A

        game = service.game(game_id)
        user = update.effective_user
        sent = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"{_predict_header(user)}\n\n"
                f"بازی {game_id}: {game.team_a} - {game.team_b}\n"
                f"گل‌های {game.team_b} را انتخاب کنید)\n"
                "یا عدد دلخواه را با ریپلای به همین پیام بفرستید:"
            ),
            reply_markup=_build_single_score_keyboard("scoreb"),
        )
        context.user_data["predict_input_message_id"] = sent.message_id
        return ENTER_SCORE_B

    @group_user
    async def predict_score_b_selected(update, context):
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
        context.user_data.pop("predict_input_message_id", None)
        return ConversationHandler.END

    @group_user
    async def predict_enter_score_b(update, context):
        game_id = context.user_data.get("predict_game_id")
        pred_a = context.user_data.get("predict_score_a")
        if game_id is None or pred_a is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="ابتدا مراحل را کامل کنید. دوباره /predict را بزنید.",
            )
            return ConversationHandler.END

        input_message_id = context.user_data.get("predict_input_message_id")
        reply_to = update.message.reply_to_message if update.message else None
        if input_message_id is None or reply_to is None or reply_to.message_id != input_message_id:
            return ENTER_SCORE_B

        user = update.effective_user
        group_id = update.effective_chat.id
        try:
            pred_b = _parse_single_score(update.message.text)
            result_text = _save_prediction(user.id, group_id, game_id, pred_a, pred_b)
            await _send_prediction_result(update, context, result_text)
        except Exception:
            game = service.game(game_id)
            sent = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    f"{_predict_header(user)}\n"
                    f"گل‌های {game.team_b} را درست وارد کنید.\n"
                    "مثال: 0 یا 2\n"
                    "عدد را با ریپلای به پیام مرحله بفرستید."
                ),
                reply_markup=_build_single_score_keyboard("scoreb"),
            )
            context.user_data["predict_input_message_id"] = sent.message_id
            return ENTER_SCORE_B

        context.user_data.pop("predict_game_id", None)
        context.user_data.pop("predict_score_a", None)
        context.user_data.pop("predict_input_message_id", None)
        return ConversationHandler.END

    @group_user
    async def predict_cancel(update, context):
        context.user_data.pop("predict_game_id", None)
        context.user_data.pop("predict_score_a", None)
        context.user_data.pop("predict_input_message_id", None)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="ثبت پیش‌بینی لغو شد.")
        return ConversationHandler.END

    @group_user
    async def predict_already_active(update, context):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="شما یک گفت‌وگوی پیش‌بینی فعال دارید. لطفا ابتدا آن را کامل کنید یا /cancel بزنید، سپس دوباره /predict را اجرا کنید.",
        )
        return None

    predict_conversation = ConversationHandler(
        entry_points=[CommandHandler("predict", predict_start)],
        states={
            SELECT_GAME: [
                CommandHandler("predict", predict_already_active),
                CallbackQueryHandler(predict_game_selected, pattern=r"^predict:game:\d+$"),
            ],
            ENTER_SCORE_A: [
                CommandHandler("predict", predict_already_active),
                CallbackQueryHandler(predict_score_a_selected, pattern=r"^predict:scorea:\d+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, predict_enter_score_a),
            ],
            ENTER_SCORE_B: [
                CommandHandler("predict", predict_already_active),
                CallbackQueryHandler(predict_score_b_selected, pattern=r"^predict:scoreb:\d+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, predict_enter_score_b),
            ],
        },
        fallbacks=[CommandHandler("cancel", predict_cancel)],
    )

    return {"predict_conversation": predict_conversation}
