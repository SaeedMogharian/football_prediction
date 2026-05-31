from telegram import Update
from telegram.ext import ContextTypes

from app.core import restricted


#
# Admin moderation handlers
#
def build_admin_handlers(service, admins, unknown):
    def parse_multiline_command_payload(update: Update) -> str:
        text = update.effective_message.text or ""
        parts = text.split("\n", 1)
        if len(parts) == 1:
            cmd_parts = text.split(maxsplit=1)
            return cmd_parts[1] if len(cmd_parts) > 1 else ""
        return parts[1]

    @restricted(admins)
    async def add_teams_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            payload = parse_multiline_command_payload(update)
            team_names = [line.strip() for line in payload.splitlines() if line.strip()]
            if not team_names:
                raise ValueError
            service.add_teams(team_names)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{len(team_names)} تیم اضافه/به‌روزرسانی شد.",
            )
        except Exception:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="فرمت درست:\n/add_teams\nTeam A\nTeam B\nTeam C",
            )

    @restricted(admins)
    async def add_games_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            payload = parse_multiline_command_payload(update)
            game_lines = [line.strip() for line in payload.splitlines() if line.strip()]
            if not game_lines:
                raise ValueError

            games_to_add = []
            for game_line in game_lines:
                fields = [part.strip() for part in game_line.split(",")]
                if len(fields) not in (2, 5):
                    raise ValueError
                if len(fields) == 2:
                    team_a, team_b = fields
                    goals_a, goals_b, is_played = 0, 0, 0
                else:
                    team_a, team_b = fields[0], fields[1]
                    goals_a, goals_b, is_played = int(fields[2]), int(fields[3]), int(fields[4])
                games_to_add.append((team_a, team_b, goals_a, goals_b, is_played))

            service.add_games(games_to_add)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{len(games_to_add)} بازی اضافه شد.",
            )
        except Exception as error:
            msg = "فرمت درست:\n/add_games\nTeam A, Team B\nTeam C, Team D"
            if str(error):
                msg += f"\n\nخطا: {error}"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

    @restricted(admins)
    async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            username = context.args[0]
            users = service.get_all_users()
            user_row = next((u for u in users if u[1] == username), None)
            if not user_row:
                raise KeyError

            user_id, _, score = user_row
            if user_id in admins:
                raise KeyError

            if score != 0:
                force = context.args[1] if len(context.args) > 1 else None
                if force in ("1", "f"):
                    service.delete_user(user_id)
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"یوزر {username} پاک شد!")
                else:
                    await context.bot.send_message(chat_id=update.effective_chat.id, text="یوزر امتیاز دارد!")
            else:
                service.delete_user(user_id)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"یوزر {username} پاک شد!")
        except Exception:
            await unknown(update, context)

    @restricted(admins)
    async def set_game_result_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            game_id = int(context.args[0])
            if service.game_exists(game_id):
                goals_a = int(context.args[1])
                goals_b = int(context.args[2])
                service.set_game(game_id, goals_a, goals_b, 1)
                game = service.game(game_id)
                text = "نتیجه ثبت شده به صورت دستی تغییر کرد"
                text += f"\n{game_id}: {game.team_a} {game.goals_a} - {game.goals_b} {game.team_b}"
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=" مشخصات بازی اشتباه وارد شده است")
        except Exception:
            await unknown(update, context)

    @restricted(admins)
    async def play_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            game_id = int(context.args[0])
            if not service.game_exists(game_id) or service.game(game_id).is_played:
                text = "بازی {} فعال است یا مشخصات بازی اشتباه وارد شده است".format(game_id)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            else:
                game = service.game(game_id)
                service.set_game(game_id, game.goals_a, game.goals_b, 1)
                game = service.game(game_id)
                text = "بازی: "
                text += f"\n{game_id}: {game.team_a} -  {game.team_b}"
                text += "\n شروع شد و فرصت پیش‌بینی به پایان رسید."
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        except Exception:
            await unknown(update, context)

    @restricted(admins)
    async def unplay_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            game_id = int(context.args[0])
            if not service.game_exists(game_id) or not service.game(game_id).is_played:
                text = "بازی {} غیر فعال است یا مشخصات بازی اشتباه وارد شده است".format(game_id)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            else:
                game = service.game(game_id)
                service.set_game(game_id, game.goals_a, game.goals_b, 0)
                game = service.game(game_id)
                text = "بازی: "
                text += f"\n{game_id}: {game.team_a} - {game.team_b}"
                text += "\n برای پیش‌بینی فعال شد."
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        except Exception:
            await unknown(update, context)

    @restricted(admins)
    async def recalculate_scores_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        service.calculate_user_scores()
        await context.bot.send_message(chat_id=update.effective_chat.id, text="محاسبه امتیاز انجام شد")

    @restricted(admins)
    async def warn_missing_predictions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            game_id = int(context.args[0])
        except Exception:
            current_game_id = service.current_game()
            game_id = current_game_id + 1 if service.game_exists(current_game_id) and service.game(current_game_id).is_played else current_game_id

        text = "بازی شماره {} به زودی شروع خواهد شد.".format(game_id)
        text += "\nهرچه سریعتر پیش‌بینی خود را وارد کنید:"

        users = service.get_all_users()
        for uid, username, _ in users:
            if service.is_new_prediction(uid, game_id):
                text += f"\n@{username}"

        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    return {
        "remind": warn_missing_predictions_command,
        "recalc_scores": recalculate_scores_command,
        "set_result": set_game_result_command,
        "close_predictions": play_game_command,
        "open_predictions": unplay_game_command,
        "delete_user": delete_user_command,
        "add_teams": add_teams_command,
        "add_games": add_games_command,
    }
