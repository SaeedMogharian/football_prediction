from telegram import Update
from telegram.ext import ContextTypes


#
# Start command
#
def build_start_handler(service, is_open_signup):
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

    return {"start": start_command}
