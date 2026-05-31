from telegram import Update
from telegram.ext import ContextTypes


#
# Fallback handlers
#
def build_unknown_handler():
    async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="درخواست مورد نظر صحیح نمی‌باشد")

    return {"unknown": unknown}
