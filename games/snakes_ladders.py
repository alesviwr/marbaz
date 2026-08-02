import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
import game_sessions as gs
import board_images as bi

KIND = "sl"
MAX_PLAYERS = 4

SNAKES = {16: 6, 47: 26, 49: 11, 56: 53, 62: 19, 64: 60, 87: 24, 93: 73, 95: 75, 98: 78}
LADDERS = {1: 38, 4: 14, 9: 31, 21: 42, 28: 84, 36: 44, 51: 67, 71: 91, 80: 100}


def _players_text(session):
    lines = []
    for p in session["players"]:
        pos = session["positions"].get(p["user_id"], 0)
        lines.append(f"{p['name']} — خونه {pos}")
    return "\n".join(lines)


def _lobby_text(session):
    return (
        "🐍🪜 بازی مار و پله راه افتاد!\n\n"
        f"{_players_text(session)}\n\n"
        "بازیکنای بیشتر با لینک بپیوندن، یا سازنده بازی رو شروع کنه (حداقل ۲ نفر لازمه)."
    )


def _lobby_keyboard(session, game_id, is_host):
    rows = [[InlineKeyboardButton("🔗 دعوت به بازی", url=session["invite_link"])]]
    if is_host:
        rows.append([InlineKeyboardButton("▶️ شروع بازی", callback_data=f"sl_begin_{game_id}")])
    return InlineKeyboardMarkup(rows)


async def sl_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    db.upsert_user(user.id, user.username, user.first_name)

    session = gs.create_game(KIND, user, chat.id, extra={"positions": {user.id: 0}, "turn_idx": 0})
    link = f"https://t.me/{context.bot.username}?start=join_{KIND}_{session['id']}"
    session["invite_link"] = link

    msg = await update.message.reply_text(
        _lobby_text(session), reply_markup=_lobby_keyboard(session, session["id"], True)
    )
    session["players"][0]["msg_id"] = msg.message_id


async def sl_join(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
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
        await update.message.reply_text("شما از قبل تو این بازی هستید.")
        return
    if len(session["players"]) >= MAX_PLAYERS:
        await update.message.reply_text("ظرفیت این بازی تکمیله (حداکثر ۴ نفر).")
        return

    db.upsert_user(user.id, user.username, user.first_name)
    session["players"].append({
        "user_id": user.id,
        "name": user.first_name or user.username or "بازیکن",
        "chat_id": chat.id,
        "msg_id": None,
    })
    session["positions"][user.id] = 0

    host_id = session["players"][0]["user_id"]

    def render(p):
        return _lobby_text(session), _lobby_keyboard(session, game_id, p["user_id"] == host_id)

    await gs.broadcast_custom(context.bot, session, render)


def _board_image(session):
    positions = [session["positions"][p["user_id"]] for p in session["players"]]
    return bi.render_snakes_ladders(positions, SNAKES, LADDERS)


async def _render_turn(bot, session, game_id, extra_note=""):
    current_id = session["players"][session["turn_idx"]]["user_id"]
    current_name = gs.find_player(session, current_id)["name"]
    note_block = f"{extra_note}\n\n" if extra_note else ""
    caption = f"🐍🪜 {_players_text(session)}\n\n{note_block}نوبت: {current_name}"

    def render(p):
        img = _board_image(session)
        if p["user_id"] == current_id:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎲 پرتاب تاس", callback_data=f"sl_roll_{game_id}")]])
        else:
            kb = None
        return img, caption, kb

    await gs.broadcast_photo(bot, session, render)


async def sl_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = query.from_user

    if data.startswith("sl_begin_"):
        game_id = data[len("sl_begin_"):]
        session = gs.get_game(game_id)
        if not session:
            await query.answer("این بازی دیگه فعال نیست.", show_alert=True)
            return
        host_id = session["players"][0]["user_id"]
        if user.id != host_id:
            await query.answer("فقط سازنده بازی می‌تونه شروع کنه.", show_alert=True)
            return
        if session["status"] != "waiting":
            await query.answer("بازی از قبل شروع شده.", show_alert=True)
            return
        if len(session["players"]) < 2:
            await query.answer("حداقل ۲ بازیکن لازمه.", show_alert=True)
            return

        session["status"] = "playing"
        await query.answer("بازی شروع شد!")
        await _render_turn(context.bot, session, game_id)
        return

    if data.startswith("sl_roll_"):
        game_id = data[len("sl_roll_"):]
        session = gs.get_game(game_id)
        if not session:
            await query.answer("این بازی دیگه فعال نیست.", show_alert=True)
            return

        current_id = session["players"][session["turn_idx"]]["user_id"]
        if user.id != current_id:
            await query.answer("نوبت شما نیست!", show_alert=True)
            return

        dice = random.randint(1, 6)
        pos = session["positions"][user.id] + dice

        if pos > 100:
            pos = session["positions"][user.id]
            note = f"🎲 {dice} آوردید ولی جا نیست، سر جاتون موندید."
        elif pos in SNAKES:
            new_pos = SNAKES[pos]
            note = f"🎲 {dice} آوردید، رفتید خونه {pos}... 🐍 مار گازتون گرفت، افتادید خونه {new_pos}!"
            pos = new_pos
        elif pos in LADDERS:
            new_pos = LADDERS[pos]
            note = f"🎲 {dice} آوردید، رفتید خونه {pos}... 🪜 از نردبون رفتید بالا، خونه {new_pos}!"
            pos = new_pos
        else:
            note = f"🎲 {dice} آوردید و رفتید خونه {pos}."

        session["positions"][user.id] = pos
        await query.answer(note[:200])

        if pos == 100:
            for p in session["players"]:
                db.record_result(p["user_id"], KIND, "win" if p["user_id"] == user.id else "loss")
            winner_name = gs.find_player(session, user.id)["name"]
            caption = f"🐍🪜 {_players_text(session)}\n\n{note}\n\n🏆 {winner_name} برنده شد و به خونه ۱۰۰ رسید!"

            def render(p):
                return _board_image(session), caption, None

            await gs.broadcast_photo(context.bot, session, render)
            gs.remove_game(game_id)
            return

        session["turn_idx"] = (session["turn_idx"] + 1) % len(session["players"])
        await _render_turn(context.bot, session, game_id, extra_note=note)
