from telegram import Update
from telegram.ext import ContextTypes

from app.core import restricted


#
# Admin moderation handlers
#
def build_admin_handlers(service, admins, unknown):
    def _command_payload(update: Update) -> str:
        text = update.effective_message.text or ""
        parts = text.split("\n", 1)
        if len(parts) == 1:
            cmd_parts = text.split(maxsplit=1)
            return cmd_parts[1] if len(cmd_parts) > 1 else ""
        return parts[1]

    @restricted(admins)
    async def add_teams(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            payload = _command_payload(update)
            teams = [line.strip() for line in payload.splitlines() if line.strip()]
            if not teams:
                raise ValueError
            service.add_teams(teams)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{len(teams)} تیم اضافه/به‌روزرسانی شد.",
            )
        except Exception:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="فرمت درست:\n/addteams\nTeam A\nTeam B\nTeam C",
            )

    @restricted(admins)
    async def add_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            payload = _command_payload(update)
            lines = [line.strip() for line in payload.splitlines() if line.strip()]
            if not lines:
                raise ValueError

            games = []
            for line in lines:
                parts = [x.strip() for x in line.split(",")]
                if len(parts) not in (2, 5):
                    raise ValueError
                if len(parts) == 2:
                    team_a, team_b = parts
                    goals_a, goals_b, is_played = 0, 0, 0
                else:
                    team_a, team_b = parts[0], parts[1]
                    goals_a, goals_b, is_played = int(parts[2]), int(parts[3]), int(parts[4])
                games.append((team_a, team_b, goals_a, goals_b, is_played))

            service.add_games(games)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{len(games)} بازی اضافه شد.",
            )
        except Exception as error:
            msg = "فرمت درست:\n/addgames\nTeam A, Team B\nTeam C, Team D"
            if str(error):
                msg += f"\n\nخطا: {error}"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

    @restricted(admins)
    async def delu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            username = context.args[0]
            users = service.get_all_users()
            user_row = next((u for u in users if u[1] == username), None)
            if not user_row:
                raise KeyError

            uid, _, score = user_row
            if uid in admins:
                raise KeyError

            if score != 0:
                force = context.args[1] if len(context.args) > 1 else None
                if force in ("1", "f"):
                    service.del_user(uid)
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"یوزر {username} پاک شد!")
                else:
                    await context.bot.send_message(chat_id=update.effective_chat.id, text="یوزر امتیاز دارد!")
            else:
                service.del_user(uid)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"یوزر {username} پاک شد!")
        except Exception:
            await unknown(update, context)

    @restricted(admins)
    async def set_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            n = int(context.args[0])
            if service.game_exists(n):
                p1 = int(context.args[1])
                p2 = int(context.args[2])
                service.set_game(n, p1, p2, 1)
                g = service.game(n)
                text = "نتیجه ثبت شده به صورت دستی تغییر کرد"
                text += f"\n{n}: {g.team_a} {g.goals_a} - {g.goals_b} {g.team_b}"
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=" مشخصات بازی اشتباه وارد شده است")
        except Exception:
            await unknown(update, context)

    @restricted(admins)
    async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            n = int(context.args[0])
            if not service.game_exists(n) or service.game(n).is_played:
                text = "بازی {} فعال است یا مشخصات بازی اشتباه وارد شده است".format(n)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            else:
                g = service.game(n)
                service.set_game(n, g.goals_a, g.goals_b, 1)
                g = service.game(n)
                text = "بازی: "
                text += f"\n{n}: {g.team_a} -  {g.team_b}"
                text += "\n شروع شد و فرصت پیش‌بینی به پایان رسید."
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        except Exception:
            await unknown(update, context)

    @restricted(admins)
    async def unplay(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            n = int(context.args[0])
            if not service.game_exists(n) or not service.game(n).is_played:
                text = "بازی {} غیر فعال است یا مشخصات بازی اشتباه وارد شده است".format(n)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            else:
                g = service.game(n)
                service.set_game(n, g.goals_a, g.goals_b, 0)
                g = service.game(n)
                text = "بازی: "
                text += f"\n{n}: {g.team_a} - {g.team_b}"
                text += "\n برای پیش‌بینی فعال شد."
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        except Exception:
            await unknown(update, context)

    @restricted(admins)
    async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
        service.calculate_user_scores()
        await context.bot.send_message(chat_id=update.effective_chat.id, text="محاسبه امتیاز انجام شد")

    @restricted(admins)
    async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            n = int(context.args[0])
        except Exception:
            c = service.current_game()
            n = c + 1 if service.game_exists(c) and service.game(c).is_played else c

        text = "بازی شماره {} به زودی شروع خواهد شد.".format(n)
        text += "\nهرچه سریعتر پیش‌بینی خود را وارد کنید:"

        users = service.get_all_users()
        for uid, username, _ in users:
            if service.pred_is_new(uid, n):
                text += f"\n@{username}"

        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    return {
        "warn": warn,
        "calc": calc,
        "set": set_game_handler,
        "play": play,
        "unplay": unplay,
        "delu": delu,
        "addteams": add_teams,
        "addgames": add_games,
    }
