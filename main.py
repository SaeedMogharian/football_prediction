# import nest_asyncio
# nest_asyncio.apply()

import logging
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes
import sqlite3

f = open("token", "r")
BOT_TOKEN = f.read()
f.close()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def create_connection():
    connection = None
    try:
        connection = sqlite3.connect("db.sqlite3")
        print("Connection to SQLite DB successful")
    except sqlite3.Error as e:
        print(f"The error '{e}' occurred")
    return connection


Conn = create_connection()
cursor = Conn.cursor()

# {id: (username, points)}
Users = {}

def add_user(user):
    Users[user.id] = (user.username, 0)
    cursor.execute("INSERT INTO Users VALUES ({}, '{}', {})".format(user.id, user.username, 0))
    Conn.commit()


def update_scores(s):
    for x in s:
        if s[x] != Users[x]:
            Users[x] = (Users[x][0], s[x])
            cursor.execute("UPDATE Users Set score = {} WHERE t_id = {}".format(s[x], x))
            Conn.commit()


# {id: (team1, team2, res1, res2, isPlayed)}
Games = {}

def set_game(n, r1, r2, pl=1):
    if Games[n]!=(Games[n][0], Games[n][1], r1, r2, pl):
        Games[n] = (Games[n][0], Games[n][1], r1, r2, pl)
        score_calc(n)
        cursor.execute("UPDATE Games Set res1 = {}, res2 = {}, isPlayed = {} WHERE id = {}".format(r1, r2, pl, n))
        Conn.commit()


def current_game():
    g = cursor.execute("SELECT * FROM Games WHERE isPlayed = 1").fetchall()
    try:
        return g[-1][0]
    except:
        return 1

from bs4 import BeautifulSoup
import requests

def fetch_result(n):
    
    query = 'https://www.google.com/search?q=' + Games[n][0] + '+vs+' + Games[n][1]
    source = requests.get(query, headers={'accept-language':'en-US,en;q=0.9'}).text
    soup = BeautifulSoup(source, 'lxml')
    soup = soup.find_all('div', class_="BNeawe deIvCb AP7Wnd")

    print("Google Says: ", n, soup[1].text, soup[2].text)
    
    if soup[0].text.split(" ")[0] == Games[n][0]:
        set_game(n, soup[1].text, soup[2].text)
    else :
        set_game(n, soup[2].text, soup[1].text)
    

# {(user, game): (pred1, pred2, score)}
Predictions = {}


def pred_is_new(u, g):
    if (u, g) not in Predictions:
        return True
    return False


def pred_is_av(g):
    if Games[g][4]:
        return False
    return True

def pred_is_possib(p):
    if p[1] in Games and p[2]>=0 and p[3]>=0:
        return True
    return False

def add_pred(p):
    Predictions[(p[0], p[1])] = (p[2], p[3], p[4])
    cursor.execute(
        "INSERT INTO Predictions (user, game, pred1, pred2, score) VALUES ({}, {}, {}, {}, {});".format(p[0], p[1], p[2], p[3], p[4]))
    Conn.commit()

def edit_pred(p):
    Predictions[(p[0], p[1])] = p[2:]
    cursor.execute(
        "UPDATE Predictions Set pred1 = {}, pred2 = {} , score = {} WHERE user = {} AND game = {}".format(p[2], p[3], p[4], p[0], p[1]))
    Conn.commit()

def point_calc(g, p1, p2):
    if Games[g][4] == 0:
        return 'np'
    r1 = Games[g][2]
    r2 = Games[g][3]
    # if(AND(Matches!C2=Pre!C2,Matches!D2=Pre!D2),10,
    if int(p1) == int(r1) and int(p2) == int(r2):
        return 10
    # if(Matches!C2-Matches!D2=Pre!C2-Pre!D2,7,
    if int(p1) - int(p2) == int(r1) - int(r2):
        return 7
    point = 0
    # if(AND(OR(Matches!C2=Pre!C2,Matches!D2=Pre!D2),OR(AND(Matches!C2>Matches!D2,Pre!C2>Pre!D2),AND(Matches!C2<Matches!D2,Pre!C2<Pre!D2),AND(Matches!C2=Matches!D2,Pre!C2=Pre!D2))),5,
    if (int(p1) > int(p2) and int(r1) > int(r2)) or (int(p1) < int(p2) and int(r1) < int(r2)):
        point += 4
    if int(p1) == int(r1) or int(p2) == int(r2):
        point += 1
    return point

def score_calc(g):
    for u in Users:
        if (u, g) in Predictions:
            x = Predictions[(u, g)]
            p = point_calc(g, x[0], x[1])
            if Predictions[(u, g)] != (x[0], x[1], p):
                Predictions[(u, g)] = (x[0], x[1], p)
                edit_pred((u, g, x[0], x[1], p))


def init():
    rows = cursor.execute("SELECT * FROM Predictions").fetchall()
    for p in rows:
        Predictions[(p[0], p[1])] = p[2:]

    rows = cursor.execute("SELECT * FROM Games").fetchall()
    for g in rows:
        Games[g[0]] = g[1:]

    rows = cursor.execute("SELECT * FROM Users").fetchall()
    for u in rows:
        Users[u[0]] = u[1:]
    
from functools import wraps

def auth(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_message.from_user.id
        if user_id not in Users:
            print(f"Unauthorized access denied.")
            return
        return await func(update, context)
    return wrapped

Admins = [102285108]
def restricted(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_message.from_user.id
        if user_id not in Admins:
            print(f"Unauthorized only admin access.")
            return
        return await func(update, context)
    return wrapped


'''commands'''

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_message.from_user
    text = 'سلام {}'.format(user.first_name)

    if user.id not in Users:
            add_user(user)
            # text += '\n\n شرمنده عضویت نداریم!'
    text += '\nبه بات پیش‌بینی خوش اومدی!'
    text += "\nبرای پیش بینی لیست بازی‌ها رو از /games ببین و این جوری پیش‌بینی‌ت رو ثبت کن:"
    text += "\n/pred <gameID> <team1 goal> <team2 goal>"
    # else:
    #     text += '\nبه بات پیش‌بینی خوش اومدی!'
    #     text += "\nبرای پیش بینی لیست بازی‌ها رو از /games ببین و این جوری پیش‌بینی‌ت رو ثبت کن:"
        # text += "\n/pred <gameID> <team1 goal> <team2 goal>"

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )

@auth
async def games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = 'بازی‌ها:\n'
    try:
        n = int(context.args[0])
    except:
        n = 12
    c = current_game()
    a = max(c - n//3, 1)
    a = min(len(Games) - n, a)
    r = range(a, min(a + n, len(Games) + 1))
    while a in r and a in Games:
        g = Games[a]
        if g[4] == 0:
            g = (g[0], g[1], "TBD", "TBD", g[4])
        text += '{}: {} {} - {} {}\n'.format(a, g[0], g[2], g[3], g[1])
        a += 1

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )


# gameID res1 res2
@restricted
async def set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = int(context.args[0])
        if 0 < n < len(Games) + 1:
            try:
                p1 = int(context.args[1])
                p2 = int(context.args[2])
                set_game(n, p1, p2)
                text = "نتیجه ثبت شد"
                text += "\n{}: {} {} - {} {}".format(n, Games[n][0], Games[n][2], Games[n][3], Games[n][1])
            except:
                set_game(n, 0, 0, 0)
                text = "بازی برای پیش‌بینی فعال شد"
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text
            )
        else:
            text = " مشخصات بازی اشتباه وارد شده است"
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text
            )
    except:
        await unknown(update, context)


# gameID pred1 pred2
@auth
async def pred(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_message.from_user
    text = "@{}".format(user.username)
    try:
        p = (user.id, int(context.args[0]), int(context.args[1]), int(context.args[2]), 0)
        av = pred_is_av(p[1])
        new = pred_is_new(p[0], p[1])
        if pred_is_possib(p):
            if av and new:
                text += "\n پیش بینی شما اضافه شد:"
                text += "\n{}: {} {} - {} {}".format(p[1], Games[p[1]][0], p[2], p[3], Games[p[1]][1])
                add_pred(p)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text
                )
            elif not av:
                text += "\n این بازی برای پیش‌بینی در دسترس نیست"
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text
                )
            elif not new:
                text += "\nشما قبلا این بازی را پیش بینی کرده‌اید" + "\n لطفا دقت کنید :)\n"
                if Predictions[(p[0], p[1])] != p[2:]:
                    edit_pred(p)
                    text += "\n پیش بینی شما تغییر کرد:"
                    text += "\n{}: {} {} - {} {}".format(p[1], Games[p[1]][0], p[2], p[3], Games[p[1]][1])
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text
                )
        else:
            raise ValueError
    except:
            text = "لطفا طبق الگوی خواسته شده و از بین بازی‌های موجود پیش‌بینی را وارد کنید"
            text += "\n/pred <gameID> <team1 goal> <team2 goal>"
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text
            )
    

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
        

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )

@restricted
async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = {}
    for x in Users:
        s[x] = 0
    for x in Predictions:
        if Games[x[1]][4]:
            a = Predictions[x][2]
            s[x[0]] += a
    update_scores(s)

    text = 'محاسبه امتیاز انجام شد'
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )

# gameID | None
@auth
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = int(context.args[0])
    except:
        c = current_game()
        if Games[c][4]:
            n = c + 1
        else:
            n = c
    text = 'بازی شماره {} به زودی شروع خواهد شد.'.format(n)
    text += '\nهرچه سریعتر پیش‌بینی خود را وارد کنید:'
    for u in Users:
        if (u, n) not in Predictions:
            text += "\n@{}".format(Users[u][0])
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )

@auth
async def mine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = int(context.args[0])
    except:
        n = 10

    user = update.effective_message.from_user
    text = "@{}".format(user.username)
    text += "\nآمار شما:"
    mp = {}
    s = []
    for g in Games:
        if (user.id, g) in Predictions:
            mp[g] = Predictions[(user.id, g)]
            s.append(mp[g][2])
    
    c = current_game()
    d = min(len(mp),c)*100//c
    text += "\n {} پیش‌بینی ({} بازی برگزار شده) ".format(c)
    text += "\n امتیاز ثبت شده: {}".format(Users[user.id][1])
    text += "\n پیش بینی {} درصد بازی‌ها تا کنون".format(d)
    text += "\n {} پیش‌بینی دقیق ".format(s.count(10))
    text += "\n دریافت میانگین {} امتیاز از هر پیش‌بینی. ".format(round(sum(s)/min(c, len(s)),2))


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
            sc = mp[g][2]
            if not Games[g][4]:
                sc = "np"
            text += "\n{}: {} {} - {} {}: {}".format(g, Games[g][0], mp[g][0], mp[g][1], Games[g][1], sc)
            i += 1
        g += 1
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text
    )

# gameID | None
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
        if 0 < a < len(Games) + 1:
            g = a
    except:
        g = current_game()
        try:
            fetch_result(g)
        except:
            print("Google Didn't Respond!")
    
    if Games[g][4]:
        t = ":تمام پیش‌‌بینی‌ها"
        t = for_game(t, g)
    else:
        t= "بازی شماره {} هنوز برگزار نشده است!".format(g)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=t
    )


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="درخواست مورد نظر صحیح نمی‌باشد"
    )


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
    set_handler = CommandHandler('set', set)
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
