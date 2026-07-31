from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db

sessions = {}
MARKS = {"X": "❌", "O": "⭕"}

WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]


def _name(user):
    return user.first_name or user.username or "بازیکن"


def _render_keyboard(board, active):
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            val = board[i]
            label = MARKS[val] if val else "➖"
            cb = f"ttt_{i}" if (active and not val) else "ttt_noop"
            row.append(InlineKeyboardButton(label, callback_data=cb))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def _status_text(session):
    turn_name = session["p1_name"] if session["turn"] == session["p1"] else session["p2_name"]
    return (
        f"❌ {session['p1_name']}   🆚   ⭕ {session['p2_name']}\n\n"
        f"نوبت: {turn_name}"
    )


def _check_win(board):
    for line in WIN_LINES:
        a, b, c = line
        if board[a] and board[a] == board[b] == board[c]:
            return line
    return None


async def ttt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    challenged = None
    if update.message.reply_to_message:
        challenged = update.message.reply_to_message.from_user
        if challenged.is_bot:
            await update.message.reply_text("نمی‌تونی ربات رو چالش کنی 😅")
            return

    if challenged:
        text = f"⭕❌ {_name(user)} به {_name(challenged)} چالش دوز داد!"
        keyboard = [[InlineKeyboardButton("✅ قبول چالش", callback_data="ttt_accept")]]
    else:
        text = f"⭕❌ {_name(user)} یه بازی دوز باز کرد. کی بازی می‌کنه؟"
        keyboard = [[InlineKeyboardButton("🤝 پیوستن", callback_data="ttt_accept")]]

    msg = await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    sessions[(chat.id, msg.message_id)] = {
        "p1": user.id, "p1_name": _name(user), "mark1": "X",
        "p2": challenged.id if challenged else None,
        "p2_name": _name(challenged) if challenged else None, "mark2": "O",
        "board": [None] * 9, "turn": None, "status": "waiting",
    }


async def ttt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    msg_id = query.message.message_id
    key = (chat_id, msg_id)
    session = sessions.get(key)
    if not session:
        await query.answer("این بازی دیگه فعال نیست.", show_alert=True)
        return

    user = query.from_user
    data = query.data

    if data == "ttt_accept":
        if session["status"] != "waiting":
            await query.answer("بازی شروع شده.", show_alert=True)
            return
        if user.id == session["p1"]:
            await query.answer("منتظر حریف باش.", show_alert=True)
            return
        if session["p2"] and user.id != session["p2"]:
            await query.answer("این چالش برای شما نیست.", show_alert=True)
            return

        db.upsert_user(user.id, user.username, user.first_name)
        session["p2"] = user.id
        session["p2_name"] = _name(user)
        session["status"] = "playing"
        session["turn"] = session["p1"]

        await query.edit_message_text(
            _status_text(session), reply_markup=_render_keyboard(session["board"], True)
        )
        await query.answer("بازی شروع شد!")
        return

    if data == "ttt_noop":
        await query.answer()
        return

    if data.startswith("ttt_"):
        if session["status"] != "playing":
            await query.answer("بازی هنوز شروع نشده.", show_alert=True)
            return
        if user.id != session["turn"]:
            await query.answer("نوبت شما نیست!", show_alert=True)
            return

        idx = int(data.replace("ttt_", ""))
        if session["board"][idx]:
            await query.answer("این خونه پره!", show_alert=True)
            return

        mark = session["mark1"] if user.id == session["p1"] else session["mark2"]
        session["board"][idx] = mark
        await query.answer()

        if _check_win(session["board"]):
            winner_id = session["p1"] if mark == session["mark1"] else session["p2"]
            loser_id = session["p2"] if winner_id == session["p1"] else session["p1"]
            db.record_result(winner_id, "ttt", "win")
            db.record_result(loser_id, "ttt", "loss")
            winner_name = session["p1_name"] if winner_id == session["p1"] else session["p2_name"]
            text = _status_text(session) + f"\n\n🏆 {winner_name} برد!"
            await query.edit_message_text(text, reply_markup=_render_keyboard(session["board"], False))
            del sessions[key]
            return

        if all(session["board"]):
            db.record_result(session["p1"], "ttt", "draw")
            db.record_result(session["p2"], "ttt", "draw")
            text = _status_text(session) + "\n\n🤝 مساوی شد!"
            await query.edit_message_text(text, reply_markup=_render_keyboard(session["board"], False))
            del sessions[key]
            return

        session["turn"] = session["p2"] if session["turn"] == session["p1"] else session["p1"]
        await query.edit_message_text(
            _status_text(session), reply_markup=_render_keyboard(session["board"], True)
        )
