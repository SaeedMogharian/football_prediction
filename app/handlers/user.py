from telegram import Update
from telegram.ext import ContextTypes

from app.core import auth


#
# Public entry handlers
#
def build_user_handlers(service, is_open):
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_message.from_user
        text = "سلام {}".format(user.first_name)

        try:
            if not user.username:
                raise NameError

            if not service.user_exists(user.id):
                if is_open:
                    service.add_user(user)
                else:
                    text += "\n\n شرمنده عضویت نداریم!"

            if service.user_exists(user.id):
                text += "\nبه بات پیش‌بینی خوش اومدی!"
                text += "\nبرای پیش بینی لیست بازی‌ها رو از /games ببین و این جوری پیش‌بینی‌ت رو ثبت کن:"
                text += "\n/pred <gameID> <team_a goals> <team_b goals>"

            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="بدون داشتن یوزرنیم نمی‌توانید از بات استفاده کنید")

    @auth
    async def games(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = "بازی‌ها:\n"
        game_ids = service.list_game_ids()
        if not game_ids:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            return

        try:
            n = int(context.args[0])
        except Exception:
            n = 12

        c = service.current_game()
        a = max(c - n // 4, 1)
        a = min(max(len(game_ids) - n + 1, 1), a)
        end = min(a + n, len(game_ids) + 1)

        for game_id in range(a, end):
            if not service.game_exists(game_id):
                continue
            g = service.game(game_id)
            goals_a = g.goals_a if g.is_played else "TBD"
            goals_b = g.goals_b if g.is_played else "TBD"
            text += f"{game_id}: {g.team_a} {goals_a} - {goals_b} {g.team_b}\n"

        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    @auth
    async def pred(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_message.from_user
        text = "@{}".format(user.username)
        try:
            p = (user.id, int(context.args[0]), int(context.args[1]), int(context.args[2]), 0)
            av = service.pred_is_av(p[1])
            new = service.pred_is_new(p[0], p[1])

            if service.pred_is_possib(p):
                g = service.game(p[1])
                if av and new:
                    text += "\n پیش بینی شما اضافه شد:"
                    text += f"\n{p[1]}: {g.team_a} {p[2]} - {p[3]} {g.team_b}"
                    service.add_pred(p)
                elif not av:
                    text += "\n این بازی برای پیش‌بینی در دسترس نیست"
                elif not new:
                    text += "\nشما قبلا این بازی را پیش بینی کرده‌اید\n لطفا دقت کنید :)\n"
                    current = service.get_prediction(p[0], p[1])
                    if current and current != p[2:]:
                        service.edit_pred(p)
                        text += "\n پیش بینی شما تغییر کرد:"
                        text += f"\n{p[1]}: {g.team_a} {p[2]} - {p[3]} {g.team_b}"
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            else:
                raise ValueError
        except Exception:
            text = "لطفا طبق الگوی خواسته شده و از بین بازی‌های موجود پیش‌بینی را وارد کنید"
            text += "\n/pred <gameID> <team_a goals> <team_b goals>"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    @auth
    async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = "رده‌بندی:\n"
        players = sorted(service.get_all_users(), reverse=True, key=lambda k: k[2])
        if not players:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            return

        c = players[0][2]
        i = 1
        j = 0
        for x in players:
            if x[2] < c:
                i += players.index(x) - j
                j = players.index(x)
                c = x[2]
            text += "{} - {} : {}\n".format(i, x[1], x[2])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    @auth
    async def mine(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            n = int(context.args[0])
        except Exception:
            n = 10

        user = update.effective_message.from_user
        text = "@{}\nآمار شما:".format(user.username)

        mp = service.get_user_predictions(user.id)
        s = [x[2] for x in mp.values()]

        c = service.current_game()
        d = min(len(mp), c) * 100 // c if c else 0
        me = service.get_user(user.id)

        text += "\n {} پیش‌بینی ({} بازی برگزار شده) ".format(len(mp), c)
        text += "\n امتیاز ثبت شده: {}".format(me[2] if me else 0)
        text += "\n پیش بینی {}٪ بازی‌ها تا کنون".format(d)
        text += "\n {} پیش‌بینی دقیق ".format(s.count(10))
        avg_den = min(c, len(s)) if s and c else 1
        text += "\n میانگین {} امتیاز از هر پیش‌بینی. ".format(round(sum(s) / avg_den, 2) if s else 0)

        text += "\n\nآخرین پیش‌بینی‌ها "
        if mp:
            g = max(mp.keys())
            shown = 0
            while g >= 1 and shown < n:
                if g in mp and service.game_exists(g):
                    game = service.game(g)
                    sc = mp[g][2] if game.is_played else "np"
                    text += f"\n{g}: {game.team_a} {mp[g][0]} - {mp[g][1]} {game.team_b}: {sc}"
                    shown += 1
                g -= 1

        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    @auth
    async def res(update: Update, context: ContextTypes.DEFAULT_TYPE):
        def for_game(text, game_id):
            game = service.game(game_id)
            text += f"\n\nبرای بازی {game_id}: {game.team_a} {game.goals_a} - {game.goals_b} {game.team_b}"
            rows = service.get_predictions_for_game(game_id)
            data = sorted([[r[4], r[1], r[2], r[3]] for r in rows], reverse=True)
            for x in data:
                text += "\n{}: {} - {}: {}".format(x[1], x[2], x[3], x[0])
            return text

        try:
            a = int(context.args[0])
            g = a if service.game_exists(a) else service.current_game()
        except Exception:
            g = service.current_game()

        if service.game_exists(g) and service.game(g).is_played:
            t = ":تمام پیش‌‌بینی‌ها"
            try:
                service.fetch_result(g)
            except Exception:
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
