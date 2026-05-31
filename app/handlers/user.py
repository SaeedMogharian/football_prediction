from telegram import Update
from telegram.ext import ContextTypes

from app.core import Users, Games, Predictions, auth
from app import services


#
# Public entry handlers
#
def build_user_handlers(cursor, connection, is_open):
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_message.from_user
        text = 'سلام {}'.format(user.first_name)

        try:
            if not user.username:
                raise NameError
            if user.id not in Users:
                if is_open:
                    services.add_user(cursor, connection, user)
                else:
                    text += '\n\n شرمنده عضویت نداریم!'
            if user.id in Users:
                text += '\nبه بات پیش‌بینی خوش اومدی!'
                text += "\nبرای پیش بینی لیست بازی‌ها رو از /games ببین و این جوری پیش‌بینی‌ت رو ثبت کن:"
                text += "\n/pred <gameID> <team_a goals> <team_b goals>"

            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        except:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="بدون داشتن یوزرنیم نمی‌توانید از بات استفاده کنید")

    #
    # User gameplay handlers
    #
    @auth
    async def games(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = 'بازی‌ها:\n'
        try:
            n = int(context.args[0])
        except:
            n = 12
        c = services.current_game(cursor)
        a = max(c - n // 4, 1)
        a = min(len(Games) - n + 1, a)
        r = range(a, min(a + n, len(Games) + 1))
        while a in r and a in Games:
            g = Games[a]
            if g[4] == 0:
                g = (g[0], g[1], "TBD", "TBD", g[4])
            text += '{}: {} {} - {} {}\n'.format(a, g[0], g[2], g[3], g[1])
            a += 1

        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    @auth
    async def pred(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_message.from_user
        text = "@{}".format(user.username)
        try:
            p = (user.id, int(context.args[0]), int(context.args[1]), int(context.args[2]), 0)
            av = services.pred_is_av(p[1])
            new = services.pred_is_new(p[0], p[1])
            if services.pred_is_possib(p):
                if av and new:
                    text += "\n پیش بینی شما اضافه شد:"
                    text += "\n{}: {} {} - {} {}".format(p[1], Games[p[1]][0], p[2], p[3], Games[p[1]][1])
                    services.add_pred(cursor, connection, p)
                elif not av:
                    text += "\n این بازی برای پیش‌بینی در دسترس نیست"
                elif not new:
                    text += "\nشما قبلا این بازی را پیش بینی کرده‌اید\n لطفا دقت کنید :)\n"
                    if Predictions[(p[0], p[1])] != p[2:]:
                        services.edit_pred(cursor, connection, p)
                        text += "\n پیش بینی شما تغییر کرد:"
                        text += "\n{}: {} {} - {} {}".format(p[1], Games[p[1]][0], p[2], p[3], Games[p[1]][1])
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            else:
                raise ValueError
        except:
            text = "لطفا طبق الگوی خواسته شده و از بین بازی‌های موجود پیش‌بینی را وارد کنید"
            text += "\n/pred <gameID> <team_a goals> <team_b goals>"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    #
    # User stats/report handlers
    #
    @auth
    async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = 'رده‌بندی:\n'
        player = sorted(list(Users.values()), reverse=True, key=lambda k: k[1])
        c = player[0][1]
        i = 1
        j = 0
        for x in player:
            if x[1] < c:
                i += player.index(x) - j
                j = player.index(x)
                c = x[1]
            text += '{} - {} : {}\n'.format(i, x[0], x[1])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    @auth
    async def mine(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            n = int(context.args[0])
        except:
            n = 10

        user = update.effective_message.from_user
        text = "@{}\nآمار شما:".format(user.username)
        mp = {}
        s = []
        for g in Games:
            if (user.id, g) in Predictions:
                mp[g] = Predictions[(user.id, g)]
                s.append(mp[g][2])

        c = services.current_game(cursor)
        d = min(len(mp), c) * 100 // c
        text += "\n {} پیش‌بینی ({} بازی برگزار شده) ".format(len(mp), c)
        text += "\n امتیاز ثبت شده: {}".format(Users[user.id][1])
        text += "\n پیش بینی {}٪ بازی‌ها تا کنون".format(d)
        text += "\n {} پیش‌بینی دقیق ".format(s.count(10))
        text += "\n میانگین {} امتیاز از هر پیش‌بینی. ".format(round(sum(s) / min(c, len(s)), 2))

        text += "\n\nآخرین پیش‌بینی‌ها "
        g = max(list(mp.keys()))
        i = 0
        r = range(1, g + 1)
        while g in r:
            if g in mp:
                i += 1
                if i >= n:
                    break
            g -= 1
        i = 0
        g = max(g, 1)
        while g in r and i < n:
            if g in mp:
                sc = mp[g][2] if Games[g][4] else "np"
                text += "\n{}: {} {} - {} {}: {}".format(g, Games[g][0], mp[g][0], mp[g][1], Games[g][1], sc)
                i += 1
            g += 1
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    @auth
    async def res(update: Update, context: ContextTypes.DEFAULT_TYPE):
        def for_game(text, g):
            text += "\n\nبرای بازی {}: {} {} - {} {}".format(g, Games[g][0], Games[g][2], Games[g][3], Games[g][1])
            a = []
            for u in Users:
                if (u, g) in Predictions:
                    m = Predictions[(u, g)]
                    a.append([m[2], Users[u][0], m[0], m[1]])
            a.sort(reverse=True)
            for x in a:
                text += "\n{}: {} - {}: {}".format(x[1], x[2], x[3], x[0])
            return text

        try:
            a = int(context.args[0])
            g = a if 0 < a < len(Games) + 1 else services.current_game(cursor)
        except:
            g = services.current_game(cursor)

        if Games[g][4]:
            t = ":تمام پیش‌‌بینی‌ها"
            try:
                services.fetch_result(cursor, connection, g)
            except:
                print("Google Didn't Respond!")
            t = for_game(t, g)
        else:
            t = "بازی شماره {} هنوز برگزار نشده است!".format(g)

        await context.bot.send_message(chat_id=update.effective_chat.id, text=t)

    return {
        "start": start,
        "pred": pred,
        "games": games,
        "rank": rank,
        "mine": mine,
        "res": res,
    }
