from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
import game_sessions as gs

KIND = "ttt"
MARKS = {"X": "❌", "O": "⭕"}
WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]


def _check_win(board):
    for a, b, c in WIN_LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return True
    return False


def _keyboard(session, game_id, active):
    board = session["board"]
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            val = board[i]
            label = MARKS[val] if val else "➖"
            cb = f"ttt_pick_{game_id}_{i}" if (active and not val) else "ttt_noop"
            row.append(InlineKeyboardButton(label, callback_data=cb))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def _status_text(session):
    p1, p2 = session["players"]
    turn_name = p1["name"] if session["turn"] == p1["user_id"] else p2["name"]
    return f"❌ {p1['name']}   🆚   ⭕ {p2['name']}\n\nنوبت: {turn_name}"


async def ttt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    db.upsert_user(user.id, user.username, user.first_name)

    session = gs.create_game(
        KIND, user, chat.id,
        extra={"board": [None] * 9, "turn": None, "mark": {user.id: "X"}},
    )
    link = f"https://t.me/{context.bot.username}?start=join_{KIND}_{session['id']}"
    text = f"⭕❌ {session['players'][0]['name']} یه بازی دوز ساخت!\n\nاین لینک رو برای دوستت بفرست تا بهت ملحق بشه 👇"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 دعوت به بازی", url=link)]])
    msg = await update.message.reply_text(text, reply_markup=keyboard)
    session["players"][0]["msg_id"] = msg.message_id


async def ttt_join(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    user = update.effective_user
    chat = update.effective_chat
    session = gs.get_game(game_id)

    if not session or session["kind"] != KIND:
        await update.message.reply_text("این لینک بازی دیگه معتبر نیست یا منقضی شده.")
        return
    if session["status"] != "waiting":
        await update.message.reply_text("این بازی از قبل شروع شده.")
        return
    if gs.find_player(session, user.id):
        await update.message.reply_text("این لینک بازی خودته! باید برای دوستت بفرستیش.")
        return

    db.upsert_user(user.id, user.username, user.first_name)
    session["players"].append({
        "user_id": user.id,
        "name": user.first_name or user.username or "بازیکن",
        "chat_id": chat.id,
        "msg_id": None,
    })
    session["mark"][user.id] = "O"
    session["turn"] = session["players"][0]["user_id"]
    session["status"] = "playing"

    def render(p):
        active = p["user_id"] == session["turn"]
        return _status_text(session), _keyboard(session, game_id, active)

    await gs.broadcast_custom(context.bot, session, render)


async def ttt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "ttt_noop":
        await query.answer()
        return

    _, _, game_id, idx = data.split("_")
    idx = int(idx)
    session = gs.get_game(game_id)
    if not session:
        await query.answer("این بازی دیگه فعال نیست.", show_alert=True)
        return

    user = query.from_user
    if not gs.find_player(session, user.id):
        await query.answer("شما بازیکن این بازی نیستید.", show_alert=True)
        return
    if user.id != session["turn"]:
        await query.answer("نوبت شما نیست!", show_alert=True)
        return
    if session["board"][idx]:
        await query.answer("این خونه پره!", show_alert=True)
        return

    mark = session["mark"][user.id]
    session["board"][idx] = mark
    await query.answer()

    p1, p2 = session["players"]

    if _check_win(session["board"]):
        winner = gs.find_player(session, user.id)
        loser = p2 if winner["user_id"] == p1["user_id"] else p1
        db.record_result(winner["user_id"], KIND, "win")
        db.record_result(loser["user_id"], KIND, "loss")
        text = _status_text(session) + f"\n\n🏆 {winner['name']} برد!"
        await gs.broadcast_custom(context.bot, session, lambda p: (text, _keyboard(session, game_id, False)))
        gs.remove_game(game_id)
        return

    if all(session["board"]):
        db.record_result(p1["user_id"], KIND, "draw")
        db.record_result(p2["user_id"], KIND, "draw")
        text = _status_text(session) + "\n\n🤝 مساوی شد!"
        await gs.broadcast_custom(context.bot, session, lambda p: (text, _keyboard(session, game_id, False)))
        gs.remove_game(game_id)
        return

    session["turn"] = p2["user_id"] if session["turn"] == p1["user_id"] else p1["user_id"]

    def render(p):
        active = p["user_id"] == session["turn"]
        return _status_text(session), _keyboard(session, game_id, active)

    await gs.broadcast_custom(context.bot, session, render)
