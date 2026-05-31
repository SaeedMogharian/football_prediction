from bs4 import BeautifulSoup
import requests

from app.core import Users, Games, Predictions


#
# State initialization
#
def init_state(cursor):
    rows = cursor.execute("SELECT * FROM Predictions").fetchall()
    for prediction in rows:
        Predictions[(prediction[0], prediction[1])] = prediction[2:]

    rows = cursor.execute("SELECT * FROM Games").fetchall()
    for game in rows:
        Games[game[0]] = game[1:]

    rows = cursor.execute("SELECT * FROM Users").fetchall()
    for user in rows:
        Users[user[0]] = user[1:]


#
# User helpers
#
def add_user(cursor, connection, user):
    Users[user.id] = (user.username, 0)
    cursor.execute("INSERT INTO Users VALUES ({}, '{}', {})".format(user.id, user.username, 0))
    connection.commit()


def update_scores(cursor, connection, scores):
    for user_id in scores:
        if scores[user_id] != Users[user_id]:
            Users[user_id] = (Users[user_id][0], scores[user_id])
            cursor.execute("UPDATE Users Set score = {} WHERE t_id = {}".format(scores[user_id], user_id))
            connection.commit()


def del_user(cursor, connection, user_id):
    del Users[user_id]
    cursor.execute("DELETE FROM Users WHERE t_id={};".format(user_id))
    connection.commit()


#
# Game helpers
#
def current_game(cursor):
    games = cursor.execute("SELECT * FROM Games WHERE isPlayed = 1").fetchall()
    try:
        return games[-1][0]
    except:
        return 1


def set_game(cursor, connection, game_id, goals_a, goals_b, pl=1):
    if Games[game_id] != (Games[game_id][0], Games[game_id][1], goals_a, goals_b, pl):
        Games[game_id] = (Games[game_id][0], Games[game_id][1], goals_a, goals_b, pl)
        if pl:
            score_calc(cursor, connection, game_id)
        cursor.execute(
            "UPDATE Games Set goals_a = {}, goals_b = {}, isPlayed = {} WHERE id = {}".format(
                goals_a, goals_b, pl, game_id
            )
        )
        connection.commit()


def fetch_result(cursor, connection, game_id):
    query = 'https://www.google.com/search?q=' + Games[game_id][0] + '+vs+' + Games[game_id][1]
    source = requests.get(query, headers={'accept-language': 'en-US,en;q=0.9'}).text
    soup = BeautifulSoup(source, 'lxml')
    soup = soup.find_all('div', class_="BNeawe deIvCb AP7Wnd")

    print("Google Says: ", game_id, soup[1].text, soup[2].text)

    if soup[0].text.split(" ")[0] == Games[game_id][0]:
        set_game(cursor, connection, game_id, soup[1].text, soup[2].text)
    else:
        set_game(cursor, connection, game_id, soup[2].text, soup[1].text)


#
# Prediction helpers
#
def pred_is_new(user_id, game_id):
    return (user_id, game_id) not in Predictions


def pred_is_av(game_id):
    return not Games[game_id][4]


def pred_is_possib(pred):
    return pred[1] in Games and pred[2] >= 0 and pred[3] >= 0


def add_pred(cursor, connection, pred):
    Predictions[(pred[0], pred[1])] = (pred[2], pred[3], pred[4])
    cursor.execute(
        "INSERT INTO Predictions (user, game, pred_a, pred_b, score) VALUES ({}, {}, {}, {}, {});".format(
            pred[0], pred[1], pred[2], pred[3], pred[4]
        )
    )
    connection.commit()


def edit_pred(cursor, connection, pred):
    Predictions[(pred[0], pred[1])] = pred[2:]
    cursor.execute(
        "UPDATE Predictions Set pred_a = {}, pred_b = {} , score = {} WHERE user = {} AND game = {}".format(
            pred[2], pred[3], pred[4], pred[0], pred[1]
        )
    )
    connection.commit()


#
# Scoring helpers
#
def point_calc(game_id, pred_a, pred_b):
    if Games[game_id][4] == 0:
        return 0
    goals_a = Games[game_id][2]
    goals_b = Games[game_id][3]
    if int(pred_a) == int(goals_a) and int(pred_b) == int(goals_b):
        return 10
    if int(pred_a) - int(pred_b) == int(goals_a) - int(goals_b):
        return 7
    point = 0
    if (int(pred_a) > int(pred_b) and int(goals_a) > int(goals_b)) or (
        int(pred_a) < int(pred_b) and int(goals_a) < int(goals_b)
    ):
        point += 4
    if int(pred_a) == int(goals_a) or int(pred_b) == int(goals_b):
        point += 1
    return point


def score_calc(cursor, connection, game_id):
    for user_id in Users:
        if (user_id, game_id) in Predictions:
            prediction = Predictions[(user_id, game_id)]
            point = point_calc(game_id, prediction[0], prediction[1])
            if Predictions[(user_id, game_id)] != (prediction[0], prediction[1], point):
                Predictions[(user_id, game_id)] = (prediction[0], prediction[1], point)
                edit_pred(cursor, connection, (user_id, game_id, prediction[0], prediction[1], point))
