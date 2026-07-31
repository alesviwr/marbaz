import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db

sessions = {}
MAX_PLAYERS = 4
PLAYER_EMOJIS = ["🔵", "🔴", "🟢", "🟡"]

SNAKES = {16: 6, 47: 26, 49: 11, 56: 53, 62: 19, 64: 60, 87: 24, 93: 73, 95: 75, 98: 78}
LADDERS = {1: 38, 4: 14, 9: 31, 21: 42, 28: 84, 36: 44, 51: 67, 71: 91, 80: 100}


def _name(user):
    return user.first_name or user.username or "بازیکن"


def _board_text(session):
    lines = []
    for row in range(9, -1, -1):
        nums = range(row * 10 + 1, row * 10 + 11)
        nums = list(nums) if row % 2 == 0 else list(reversed(list(nums)))
        cells = []
        for n in nums:
            marker = None
            for i, p in enumerate(session["order"]):
                if session["positions"][p] == n:
                    marker = PLAYER_EMOJIS[i]
            if marker:
                cells.append(marker)
            elif n in SNAKES:
                cells.append("🐍")
            elif n in LADDERS:
                cells.append("🪜")
            else:
                cells.append("▫️")
        lines.append("".join(cells))
    return "\n".join(lines)


def _players_text(session):
    lines = []
    for i, p in enumerate(session["order"]):
        lines.append(f"{PLAYER_EMOJIS[i]} {session['names'][p]} — خونه {session['positions'][p]}")
    return "\n".join(lines)


def _lobby_text(session):
    return (
        "🐍🪜 بازی مار و پله راه افتاد!\n\n"
        f"{_players_text(session)}\n\n"
        "بازیکنای بیشتر بپیوندن یا سازنده بازی رو شروع کنه (حداقل ۲ نفر لازمه)."
    )


def _lobby_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤝 پیوستن", callback_data="sl_join")],
        [InlineKeyboardButton("▶️ شروع بازی", callback_data="sl_begin")],
    ])


async def sl_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    session = {
        "order": [user.id],
        "names": {user.id: _name(user)},
        "positions": {user.id: 0},
        "status": "lobby",
        "turn_idx": 0,
        "host": user.id,
    }
    msg = await update.message.reply_text(_lobby_text(session), reply_markup=_lobby_keyboard())
    sessions[(chat.id, msg.message_id)] = session


async def _render_turn(query, session, extra_note=""):
    current = session["order"][session["turn_idx"]]
    note_block = f"{extra_note}\n\n" if extra_note else ""
    text = (
        f"🐍🪜 بازی مار و پله\n\n{_board_text(session)}\n\n{_players_text(session)}\n\n"
        f"{note_block}نوبت: {session['names'][current]}"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🎲 پرتاب تاس", callback_data="sl_roll")]])
    await query.edit_message_text(text, reply_markup=keyboard)


async def sl_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    if data == "sl_join":
        if session["status"] != "lobby":
            await query.answer("بازی شروع شده.", show_alert=True)
            return
        if user.id in session["order"]:
            await query.answer("شما از قبل تو بازی هستید.", show_alert=True)
            return
        if len(session["order"]) >= MAX_PLAYERS:
            await query.answer("ظرفیت بازی تکمیله.", show_alert=True)
            return

        db.upsert_user(user.id, user.username, user.first_name)
        session["order"].append(user.id)
        session["names"][user.id] = _name(user)
        session["positions"][user.id] = 0
        await query.answer("پیوستید به بازی!")
        await query.edit_message_text(_lobby_text(session), reply_markup=_lobby_keyboard())
        return

    if data == "sl_begin":
        if user.id != session["host"]:
            await query.answer("فقط سازنده بازی می‌تونه شروع کنه.", show_alert=True)
            return
        if session["status"] != "lobby":
            await query.answer("بازی از قبل شروع شده.", show_alert=True)
            return
        if len(session["order"]) < 2:
            await query.answer("حداقل ۲ بازیکن لازمه.", show_alert=True)
            return

        session["status"] = "playing"
        await query.answer("بازی شروع شد!")
        await _render_turn(query, session)
        return

    if data == "sl_roll":
        if session["status"] != "playing":
            await query.answer("بازی هنوز شروع نشده.", show_alert=True)
            return
        current = session["order"][session["turn_idx"]]
        if user.id != current:
            await query.answer("نوبت شما نیست!", show_alert=True)
            return

        dice = random.randint(1, 6)
        pos = session["positions"][user.id] + dice

        if pos > 100:
            pos = session["positions"][user.id]
            note = f"🎲 {dice} آوردید ولی جا نیست، سر جاتون موندید."
        elif pos in SNAKES:
            new_pos = SNAKES[pos]
            note = f"🎲 {dice} آوردید، رفتید خونه {pos}... 🐍 مار گازتون گرفت و افتادید خونه {new_pos}!"
            pos = new_pos
        elif pos in LADDERS:
            new_pos = LADDERS[pos]
            note = f"🎲 {dice} آوردید، رفتید خونه {pos}... 🪜 از نردبون رفتید بالا تا خونه {new_pos}!"
            pos = new_pos
        else:
            note = f"🎲 {dice} آوردید و رفتید خونه {pos}."

        session["positions"][user.id] = pos

        if pos == 100:
            for p in session["order"]:
                db.record_result(p, "sl", "win" if p == user.id else "loss")
            text = (
                f"🐍🪜 بازی مار و پله\n\n{_board_text(session)}\n\n{_players_text(session)}\n\n"
                f"{note}\n\n🏆 {session['names'][user.id]} برنده شد و به خونه ۱۰۰ رسید!"
            )
            await query.answer(note[:200])
            await query.edit_message_text(text)
            del sessions[key]
            return

        session["turn_idx"] = (session["turn_idx"] + 1) % len(session["order"])
        await query.answer(note[:200])
        await _render_turn(query, session, extra_note=note)
