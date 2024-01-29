# import nest_asyncio
# nest_asyncio.apply()

import logging
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes

f = open("token", "r")
BOT_TOKEN = f.read()
f.close()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
# {id: FirstName, username, points}
Users={}
def add_user(user):
    Users[str(user.id)] = [user.first_name, user.username, 0]
    f = open("Users.csv", "a")
    f.write('\n{}, {}, {}, {}'.format(str(user.id), user.first_name, user.username, 0))
    f.close()
def rewrite_users():
    f = open("Users.csv", "w")
    i = 1
    for x in Users:
        if i == 1:
            f.write('{}, {}, {}, {}'.format(x, Users[x][0], Users[x][1], Users[x][2]))
        else:
            f.write('\n{}, {}, {}, {}'.format(x, Users[x][0], Users[x][1], Users[x][2]))
        i += 1
    f.close()
# [T1, T2, Res1, Res2]
Games=[]
def rewrite_games():
    f = open("Games.csv", "w")
    i = 1
    for x in Games:
        if i == 1:
            f.write('{}, {}, {}, {}'.format(x[0], x[1], x[2], x[3]))
        else:
            f.write('\n{}, {}, {}, {}'.format(x[0], x[1], x[2], x[3]))
        i += 1
    f.close()
# ['UserID', 'GameID', 'Pred1', 'Pred2']
Predictions=[]
def view_pred(u = True, g = True): 
    if u == g == True:
        return Predictions
    if u == True:
        return [i for i in Predictions if i[1]==g]
    if g == True:
        return [i for i in Predictions if i[0]==u]
    return [i for i in Predictions if i[0]==u and i[1]==g]
def pred_is_new(p):
    pred_uid_gid = [[i[0], i[1]] for i in Predictions]
    if [str(p[0]), str(p[1])] not in pred_uid_gid and [p[0], p[1]] not in pred_uid_gid:
        return True
    return False
def pred_is_av(p):
    if 'TBD' in Games[int(p[1])-1]:
        return True
    return False
def add_pred(p):
    Predictions.append(p)
    f = open("Predictions.csv", "a")
    f.write('\n{}, {}, {}, {}'.format(str(p[0]), str(p[1]), str(p[2]), str(p[3])))
    f.close()
def point_calc(pr):
        gm = Games[int(pr[1])-1]
        if 'TBD' in gm:
            return 0
        # if(AND(Matches!C2=Pre!C2,Matches!D2=Pre!D2),10,
        if int(pr[2]) == int(gm[2]) and int(pr[3]) == int(gm[3]):
            return 10
        # if(Matches!C2-Matches!D2=Pre!C2-Pre!D2,7,
        if int(pr[2])-int(pr[3])==int(gm[2])-int(gm[3]):
            return 7
        point = 0
        # if(AND(OR(Matches!C2=Pre!C2,Matches!D2=Pre!D2),OR(AND(Matches!C2>Matches!D2,Pre!C2>Pre!D2),AND(Matches!C2<Matches!D2,Pre!C2<Pre!D2),AND(Matches!C2=Matches!D2,Pre!C2=Pre!D2))),5,
        if (int(pr[2])>int(pr[3]) and int(gm[2])>int(gm[3])) or (int(pr[2])<int(pr[3]) and int(gm[2])<int(gm[3])):
            point+=4
        if int(pr[2]) == int(gm[2]) or int(pr[3]) == int(gm[3]):
            point+=1
        return point


def init():
    f = open("Users.csv", "r")
    ft = f.read().split('\n')
    for line in ft:
        x = line.split(',')
        for i in range(len(x)): x[i] = x[i].strip()
        x[3] = int(x[3])
        Users[x[0]] = x[1:]
    f.close()

    f = open("Games.csv", "r")
    ft = f.read().split('\n')
    for line in ft:
        x = line.split(',')
        for i in range(len(x)): x[i] = x[i].strip()
        Games.append(x)
    f.close()

    f = open("Predictions.csv", "r")
    ft = f.read().split('\n')
    for line in ft:
        x = line.split(',')
        for i in range(len(x)): x[i] = x[i].strip()
        Predictions.append(x)
    f.close()

def is_auth(update: Update):
    user = update.effective_message.from_user
    if str(user.id) in Users:
        return True
    return False
async def not_authed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "لطفا ابتدا /start کنید"
    await context.bot.send_message(
    chat_id=update.effective_chat.id,
    text=text
    )
    
'''commands'''
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_message.from_user
    text = 'سلام {}'.format(user.first_name)
    text += '\nبه بات پیش‌بینی خوش اومدی!'
    text += "\nبرای پیش بینی لیست بازی‌ها رو از /games ببین و این جوری پیش‌بینی‌ت رو ثبت کن:"
    text+= "\n/pred <gameID> <team1 goal> <team2 goal>"

    if str(user.id) not in Users:
        add_user(user)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )
async def games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update):
        await not_authed(update, context)
    text = 'بازی‌ها:\n'
    i = 1
    for x in Games:
        text+= '{}: {} {} - {} {}\n'.format(i, x[0], x[2], x[3], x[1])
        i += 1

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )
#gameID res1 res2
async def set_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update):
        await not_authed(update, context)
    user = update.effective_message.from_user
    try:
        n = int(context.args[0])
        if 0 < n < len(Games):
            Games[n-1][2] = context.args[1]
            Games[n-1][3] = context.args[2]
            rewrite_games()
            text = "نتیجه نهایی بازی ثبت شد"
            text+="\n{}: {} {} - {} {}".format(n, Games[n-1][0], Games[n-1][2], Games[n-1][3], Games[n-1][1])
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text
            )
        else:
            text = "بازی مورد نظر وجود ندارد"
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text
            )
    except:
       await unknown(update, context)
#gameID pred1 pred2
async def pred(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update):
        await not_authed(update, context) 
    user = update.effective_message.from_user
    try:
        p = [str(user.id), context.args[0], context.args[1], context.args[2]]
        if pred_is_new(p) and pred_is_av(p):
            add_pred(p)
            text = "@{} \n پیش بینی شما اضافه شد:".format(user.username)
            text+="\n{}: {} {} - {} {}".format(p[1], Games[int(p[1])-1][0], p[2], p[3], Games[int(p[1])-1][1])
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text
            )
        elif not pred_is_new(p):
            text = "@{}\n شما قبلا این بازی را پیش بینی کرده‌اید".format(user.username)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text
            )
        elif not pred_is_av(p):
            text = "@{}\n این بازی برای پیش‌بینی در دسترس نیست".format(user.username)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text
            )
    except:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="لطفا طبق الگوی خواسته شده پیش‌بینی را وارد کنید"
        )
async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update):
        await not_authed(update, context)
    text = 'رده‌بندی:\n'
    i = 1
    player = []
    for x in Users:
        player.append([Users[x][2], Users[x][1]])
    player.sort(reverse=True)
    for x in player:
        text+= '{} - {} : {}\n'.format(i, x[1], x[0])
        i += 1

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )
async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update):
        await not_authed(update, context)
    for x in Users:
        Users[x][2] = 0
    for x in Predictions:
        if 'TBD' not in Games[int(x[1])-1]:
            a = point_calc(x)
            Users[x[0]][2]+=a
    rewrite_users()

    text = 'محاسبه امتیاز انجام شد'
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )
#gameID
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update):
        await not_authed(update, context)
    n = context.args[0]
    text = 'بازی شماره {} به زودی شروع خواهد شد.'.format(n)
    text += '\nهرچه سریعتر پیش‌بینی خود را وارد کنید:'
    pred_g = [i[0] for i in Predictions if i[1]==n]
    w = [Users[i][1] for i in Users if i not in pred_g]
    for u in w:
        text += "\n@{}".format(u)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    ) 
async def mine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update):
        await not_authed(update, context)
    user = update.effective_message.from_user
    text = "@{}".format(user.username)
    text += "\nپیش‌بینی‌های شما"
    m = view_pred(u = str(user.id))
    m.sort()
    for x in m:
        n = int(x[1])
        text += "\n{}: {} {} - {} {}: {}".format(n, Games[n-1][0], x[2], x[3], Games[n-1][1], point_calc(x))

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )
#gameID | None
async def res(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    if not is_auth(update):
        await not_authed(update, context)
    def for_game(text, g):
        text += "\n\nبرای بازی {}: {} {} - {} {}".format(g, Games[int(g)-1][0], Games[int(g)-1][2], Games[int(g)-1][3], Games[int(g)-1][1])
        a = []
        for u in Users:
            m = view_pred(u = str(u), g = g)
            for x in m:
                a.append([point_calc(x), Users[u][1], x[2], x[3]])
        a.sort(reverse=True, key=lambda k : k[0])
        for x in a:
            text+="\n{}: {} - {}: {}".format(x[1], x[2], x[3], x[0])
        return text
    t = ":تمام پیش‌‌بینی‌ها"
    try:
        g = context.args[0]
        t = for_game(t, g)
    except:
        for g in range(1, len(Games)+1):
            t = for_game(t, str(g))     

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=t
    )


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="درخواست مورد نظر صحیح نمی‌باشد")


if __name__ == '__main__':
    init()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    start_handler = CommandHandler('start', start)
    pred_handler = CommandHandler('pred', pred)
    games_handler = CommandHandler('games', games)
    rank_handler = CommandHandler('rank', rank)
    mine_handler = CommandHandler('mine', mine)
    res_handler = CommandHandler('res', res)

    warn_handler = CommandHandler('warn', warn)
    calc_handler = CommandHandler('calc', calc)
    set_handler = CommandHandler('set', set_game)
    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    application.add_handler(start_handler)
    application.add_handler(pred_handler)
    application.add_handler(games_handler)
    application.add_handler(rank_handler)
    application.add_handler(mine_handler)
    application.add_handler(res_handler)

    application.add_handler(warn_handler)
    application.add_handler(calc_handler)
    application.add_handler(set_handler)
    application.add_handler(unknown_handler)
    application.run_polling()