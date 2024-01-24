# import nest_asyncio
# nest_asyncio.apply()


import logging
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = '6507408473:AAGPZf4a95mL9b2SqDXYFyORYxq75_Vt04U'
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

Users={}
def add_user(user):
    Users[str(user.id)] = [user.first_name, user.username, 0]
    f = open("Users.csv", "a")
    f.write('\n{}, {}, {}, {}'.format(str(user.id), user.first_name, user.username, 0))
    f.close()
def rewrite_all():
    f = open("Users.csv", "w")
    i = 1
    for x in Users:
        if i == 1:
            f.write('{}, {}, {}, {}'.format(x, Users[x][0], Users[x][1], Users[x][2]))
        else:
            f.write('\n{}, {}, {}, {}'.format(x, Users[x][0], Users[x][1], Users[x][2]))
        i += 1
    f.close()
# T1, T2, Res1, Res2
Games=[]
# ['UserID', 'GameID', 'Pred1', 'Pred2']
Predictions=[]
def pred_is_new(p):
    pred_uid_gid = [[i[0], i[1]] for i in Predictions]
    if [str(p[0]), str(p[1])] not in pred_uid_gid and [p[0], p[1]] not in pred_uid_gid:
        return True
    # i = pred_uid_gid.index([p[0], p[1]])
    # Predictions.remove(Predictions[i])
    return False
def pred_is_av(p):
    if 'TBD' in Games[p[1]-1]:
        return True
    return False
def add_pred(p):
    Predictions.append(p)
    f = open("Predictions.csv", "a")
    f.write('\n{}, {}, {}, {}'.format(str(p[0]), str(p[1]), str(p[2]), str(p[3])))
    f.close()

def init():
    f = open("Users.csv", "r")
    ft = f.read().split('\n')
    for line in ft:
        x = line.split(',')
        for i in range(len(x)): x[i] = x[i].strip()
        print(x)
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

def calculate_all():
    def point_calc(pr, gm):
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
    for x in Predictions:
        if 'TBD' not in Games[int(x[1])-1]:
            a = point_calc(x, Games[x[1]-1])
            Users[x[0]][2]+=a
    rewrite_all()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_message.from_user
    text = 'سلام {}'.format(user.first_name)
    text += '\nبه بات پیش‌بینی خوش اومدی!'
    text += "\nبرای پیش بینی لیست بازی‌ها رو از /games ببین و این جوری پیش‌بینی‌ت رو ثبت کن:"
    text+= "\n/pred <gameID> <team1 goal> <team2 goal>"

    if user.id not in Users:
        add_user(user)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )

async def games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = 'بازی‌ها:\n'
    i = 1
    for x in Games:
        text+= '{}: {} {} - {} {}\n'.format(i, x[0], x[2], x[3], x[1])
        i += 1

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )

async def pred(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_message.from_user
    if str(user.id) not in Users:
        await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="لطفا ابتدا /start کنید"
    )
    else:
        p = [user.id, int(context.args[0]), int(context.args[1]), int(context.args[2])]
        if pred_is_new(p) and pred_is_av(p):
            add_pred(p)
            text = "@{} \n پیش بینی شما اضافه شد:".format(user.username)
            text+="\n{}: {} {} - {} {}".format(p[1], Games[p[1]-1][0], p[2], p[3], Games[p[1]-1][1])
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

async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    calculate_all()
    text = 'رده‌بندی:\n'
    i = 1
    player = []
    for x in Users:
        player.append([Users[x][2], Users[x][1]])
    player.sort()
    for x in player:
        text+= '{} - {} : {}\n'.format(i, x[1], x[0])
        i += 1

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="متاسفانه متوجه نشدم. دوباره امتحان کن")

if __name__ == '__main__':
    init()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    start_handler = CommandHandler('start', start)
    pred_handler = CommandHandler('pred', pred)
    games_handler = CommandHandler('games', games)
    rank_handler = CommandHandler('rank', rank)
    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    application.add_handler(start_handler)
    application.add_handler(pred_handler)
    application.add_handler(games_handler)
    application.add_handler(rank_handler)
    application.add_handler(unknown_handler)
    application.run_polling()