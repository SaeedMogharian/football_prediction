from telegram import Update
from telegram.ext import ContextTypes

from app.core import group_admin


def build_group_admin_handlers(service):
    async def request_group_verification_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        user = update.effective_user
        if chat.type not in ("group", "supergroup"):
            await context.bot.send_message(chat_id=chat.id, text="این دستور فقط در گروه قابل اجرا است.")
            return

        user_id = user.id
        admin_ids = context.application.bot_data["admin_ids"]
        if user_id not in admin_ids:
            chat_admins = await context.bot.get_chat_administrators(chat.id)
            if not any(admin.user.id == user_id for admin in chat_admins):
                await context.bot.send_message(chat_id=chat.id, text="فقط ادمین گروه می‌تواند درخواست تایید ثبت کند.")
                return

        service.register_group_request(chat.id, chat.title or "", user.id)
        await context.bot.send_message(chat_id=chat.id, text="درخواست تایید گروه ثبت شد. لطفا ادمین سراسری تایید کند.")

    @group_admin
    async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        try:
            game_id = int(context.args[0])
        except Exception:
            current_game_id = service.current_game()
            game_id = current_game_id + 1 if service.game_exists(current_game_id) and service.game(current_game_id).is_played else current_game_id

        text = f"بازی شماره {game_id} به زودی شروع خواهد شد.\nهرچه سریعتر پیش‌بینی خود را وارد کنید:"
        for member_id, username, _ in service.get_all_users():
            if service.is_new_prediction(member_id, game_id, chat.id):
                text += f"\n@{username}"
        await context.bot.send_message(chat_id=chat.id, text=text)

    @group_admin
    async def group_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        group_id = chat.id
        rankings = service.get_group_rankings(group_id)
        total_predictions = service.get_group_prediction_count(group_id)
        total_users = len({user_id for user_id, _, _ in rankings})
        verified_text = "بله" if service.is_group_verified(group_id) else "خیر"

        text = f"آمار گروه: {chat.title or group_id}"
        text += f"\nشناسه گروه: {group_id}"
        text += f"\nتایید شده: {verified_text}"
        text += f"\nتعداد کاربران دارای امتیاز: {total_users}"
        text += f"\nتعداد کل پیش‌بینی‌های ثبت‌شده: {total_predictions}"
        await context.bot.send_message(chat_id=chat.id, text=text)

    return {
        "request_group_verification": request_group_verification_command,
        "remind": remind_command,
        "group_stats": group_stats_command,
    }
