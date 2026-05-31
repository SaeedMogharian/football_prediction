from telegram import Update
from telegram.ext import ContextTypes

from app.core import Users, Games, Predictions, restricted
from app import services


#
# Admin moderation handlers
#
def build_admin_handlers(cursor, connection, admins, unknown):
    @restricted(admins)
    async def delu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            u = context.args[0]
            uid = None
            for x in Users:
                if Users[x][0] == u:
                    uid = x
                    break
            if uid:
                if uid in admins:
                    raise KeyError
                if Users[uid][1] != 0:
                    try:
                        f = context.args[1]
                    except:
                        f = None
                    if f == "1" or f == "f":
                        services.del_user(cursor, connection, uid)
                        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"یوزر {u} پاک شد!")
                    else:
                        await context.bot.send_message(chat_id=update.effective_chat.id, text="یوزر امتیاز دارد!")
                else:
                    services.del_user(cursor, connection, uid)
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"یوزر {u} پاک شد!")
            else:
                raise KeyError
        except:
            await unknown(update, context)

    #
    # Admin game control handlers
    #
    @restricted(admins)
    async def set_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            n = int(context.args[0])
            if 0 < n < len(Games) + 1:
                p1 = int(context.args[1])
                p2 = int(context.args[2])
                services.set_game(cursor, connection, n, p1, p2)
                text = "نتیجه ثبت شده به صورت دستی تغییر کرد"
                text += "\n{}: {} {} - {} {}".format(n, Games[n][0], Games[n][2], Games[n][3], Games[n][1])
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=" مشخصات بازی اشتباه وارد شده است")
        except:
            await unknown(update, context)

    @restricted(admins)
    async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            n = int(context.args[0])
            if not (0 < n < len(Games) + 1) or Games[n][4]:
                text = "بازی {} فعال است یا مشخصات بازی اشتباه وارد شده است".format(n)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            else:
                services.set_game(cursor, connection, n, 0, 0, 1)
                text = "بازی: "
                text += "\n{}: {} -  {}".format(n, Games[n][0], Games[n][1])
                text += "\n شروع شد و فرصت پیش‌بینی به پایان رسید."
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        except:
            await unknown(update, context)

    @restricted(admins)
    async def unplay(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            n = int(context.args[0])
            if not (0 < n < len(Games) + 1) or not Games[n][4]:
                text = "بازی {} غیر فعال است یا مشخصات بازی اشتباه وارد شده است".format(n)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            else:
                services.set_game(cursor, connection, n, 0, 0, 0)
                text = "بازی: "
                text += "\n{}: {} - {}".format(n, Games[n][0], Games[n][1])
                text += "\n برای پیش‌بینی فعال شد."
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        except:
            await unknown(update, context)

    #
    # Admin scoring/notification handlers
    #
    @restricted(admins)
    async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
        scores = {x: 0 for x in Users}
        for x in Predictions:
            if Games[x[1]][4]:
                scores[x[0]] += Predictions[x][2]
        services.update_scores(cursor, connection, scores)
        await context.bot.send_message(chat_id=update.effective_chat.id, text='محاسبه امتیاز انجام شد')

    @restricted(admins)
    async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            n = int(context.args[0])
        except:
            c = services.current_game(cursor)
            n = c + 1 if Games[c][4] else c
        text = 'بازی شماره {} به زودی شروع خواهد شد.'.format(n)
        text += '\nهرچه سریعتر پیش‌بینی خود را وارد کنید:'
        for u in Users:
            if (u, n) not in Predictions:
                text += "\n@{}".format(Users[u][0])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    return {
        "warn": warn,
        "calc": calc,
        "set": set_game_handler,
        "play": play,
        "unplay": unplay,
        "delu": delu,
    }
