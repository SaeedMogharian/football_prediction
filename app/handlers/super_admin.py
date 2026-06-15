from telegram import Update
from telegram.ext import ContextTypes

from app.core import super_admin


def build_super_admin_handlers(service, unknown):
    def parse_multiline_command_payload(update: Update) -> str:
        text = update.effective_message.text or ""
        parts = text.split("\n", 1)
        if len(parts) == 1:
            cmd_parts = text.split(maxsplit=1)
            return cmd_parts[1] if len(cmd_parts) > 1 else ""
        return parts[1]

    @super_admin
    async def verify_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            group_id = int(context.args[0])
            if service.verify_group(group_id):
                text = f"گروه {group_id} تایید شد."
            else:
                text = f"گروه {group_id} پیدا نشد. اول /request_group_verification را در گروه اجرا کنید."
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="فرمت درست:\n/verify_group <group_id>")

    @super_admin
    async def pending_groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        pending_groups = service.list_pending_groups()
        if not pending_groups:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="گروه تاییدنشده‌ای وجود ندارد.")
            return
        lines = ["گروه‌های در انتظار تایید:"]
        for chat_id, title, requested_by, username in pending_groups:
            requester = f"@{username}" if username else str(requested_by or "unknown")
            lines.append(f"{chat_id} | {title or '-'} | درخواست‌دهنده: {requester}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="\n".join(lines))

    @super_admin
    async def add_teams_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            payload = parse_multiline_command_payload(update)
            team_names = [line.strip() for line in payload.splitlines() if line.strip()]
            if not team_names:
                raise ValueError
            service.add_teams(team_names)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{len(team_names)} تیم اضافه/به‌روزرسانی شد.")
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="فرمت درست:\n/add_teams\nTeam A\nTeam B")

    @super_admin
    async def add_games_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            payload = parse_multiline_command_payload(update)
            game_lines = [line.strip() for line in payload.splitlines() if line.strip()]
            if not game_lines:
                raise ValueError
            games_to_add = []
            for game_line in game_lines:
                fields = [part.strip() for part in game_line.split(",")]
                if len(fields) not in (2, 5, 6):
                    raise ValueError
                if len(fields) == 2:
                    team_a, team_b = fields
                    goals_a, goals_b, is_played = 0, 0, 0
                    played_at = None
                elif len(fields) == 5:
                    team_a, team_b = fields[0], fields[1]
                    goals_a, goals_b, is_played = int(fields[2]), int(fields[3]), int(fields[4])
                    played_at = None
                else:
                    team_a, team_b = fields[0], fields[1]
                    goals_a, goals_b, is_played = int(fields[2]), int(fields[3]), int(fields[4])
                    played_at = fields[5]
                games_to_add.append((team_a, team_b, goals_a, goals_b, is_played, played_at))
            service.add_games(games_to_add)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{len(games_to_add)} بازی اضافه شد.")
        except Exception as error:
            message = (
                "فرمت درست:\n/add_games\n"
                "Team A, Team B\n"
                "Team C, Team D, goals_a, goals_b, is_played\n"
                "Team E, Team F, goals_a, goals_b, is_played, YYYY-MM-DDTHH:MM:SS"
            )
            if str(error):
                message += f"\n\nخطا: {error}"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

    @super_admin
    async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            username = context.args[0]
            users = service.get_all_users()
            user_row = next((row for row in users if row[1] == username), None)
            if not user_row:
                raise KeyError
            user_id, _, _ = user_row
            score = service.get_total_user_group_score(user_id)
            admin_ids = context.application.bot_data["admin_ids"]
            if user_id in admin_ids:
                raise KeyError
            force_delete = context.args[1] if len(context.args) > 1 else None
            if score != 0 and force_delete not in ("1", "f"):
                await context.bot.send_message(chat_id=update.effective_chat.id, text="یوزر امتیاز دارد!")
                return
            service.delete_user(user_id)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"یوزر {username} پاک شد!")
        except Exception:
            await unknown(update, context)

    @super_admin
    async def set_game_result_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            game_id = int(context.args[0])
            goals_a = int(context.args[1])
            goals_b = int(context.args[2])
            if not service.game_exists(game_id):
                raise ValueError
            service.set_game(game_id, goals_a, goals_b, 1)
            game = service.game(game_id)
            text = f"نتیجه ثبت شد\n{game_id}: {game.team_a} {game.goals_a} - {game.goals_b} {game.team_b}"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        except Exception:
            await unknown(update, context)

    @super_admin
    async def close_predictions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            game_id = int(context.args[0])
            game = service.game(game_id)
            if game.is_played:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="این بازی قبلا بسته شده است.")
                return
            service.set_game(game_id, game.goals_a, game.goals_b, 1)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"پیش‌بینی بازی {game_id} بسته شد.")
        except Exception:
            await unknown(update, context)

    @super_admin
    async def open_predictions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            game_id = int(context.args[0])
            game = service.game(game_id)
            if not game.is_played:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="این بازی از قبل باز است.")
                return
            service.set_game(game_id, game.goals_a, game.goals_b, 0)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"پیش‌بینی بازی {game_id} باز شد.")
        except Exception:
            await unknown(update, context)

    @super_admin
    async def recalculate_scores_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        service.calculate_user_scores()
        await context.bot.send_message(chat_id=update.effective_chat.id, text="محاسبه امتیاز انجام شد")

    @super_admin
    async def set_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            payload = parse_multiline_command_payload(update)
            rows = [line.strip() for line in payload.splitlines() if line.strip()]
            if not rows:
                if len(context.args) < 2:
                    raise ValueError
                rows = ["{},{}".format(context.args[0], context.args[1])]

            updated_ids = []
            for row in rows:
                fields = [part.strip() for part in row.split(",")]
                if len(fields) != 2:
                    raise ValueError
                game_id = int(fields[0])
                played_at = fields[1]
                if not service.set_game_time(game_id, played_at):
                    raise ValueError(f"game_not_found:{game_id}")
                updated_ids.append(game_id)

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"زمان {len(updated_ids)} بازی تنظیم شد: {', '.join(map(str, updated_ids))}",
            )
        except Exception as error:
            message = (
                "فرمت درست:\n"
                "/set_time <game_id> <YYYY-MM-DDTHH:MM:SS>\n\n"
                "یا چند خطی:\n"
                "/set_time\n"
                "1, 2026-06-21T21:30:00\n"
                "2, 2026-06-21T23:30:00"
            )
            if str(error):
                message += f"\n\nخطا: {error}"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

    return {
        "verify_group": verify_group_command,
        "pending_groups": pending_groups_command,
        "recalc_scores": recalculate_scores_command,
        "set_time": set_time_command,
        "set_result": set_game_result_command,
        "close_predictions": close_predictions_command,
        "open_predictions": open_predictions_command,
        "delete_user": delete_user_command,
        "add_teams": add_teams_command,
        "add_games": add_games_command,
    }
