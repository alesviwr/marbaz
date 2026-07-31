from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
import game_sessions as gs

KIND = "rps"
EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
NAMES_FA = {"rock": "سنگ", "paper": "کاغذ", "scissors": "قیچی"}
BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}


async def rps_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    db.upsert_user(user.id, user.username, user.first_name)

    session = gs.create_game(KIND, user, chat.id, extra={"choices": {}})
    link = f"https://t.me/{context.bot.username}?start=join_{KIND}_{session['id']}"

    text = (
        f"🎮 {session['players'][0]['name']} یه بازی سنگ‌کاغذقیچی ساخت!\n\n"
        "این لینک رو برای دوستت بفرست تا بهت ملحق بشه 👇"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 دعوت به بازی", url=link)]])
    msg = await update.message.reply_text(text, reply_markup=keyboard)
    session["players"][0]["msg_id"] = msg.message_id


async def rps_join(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
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
    session["status"] = "playing"

    p1, p2 = session["players"]
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🪨 سنگ", callback_data=f"rps_pick_{game_id}_rock"),
        InlineKeyboardButton("📄 کاغذ", callback_data=f"rps_pick_{game_id}_paper"),
        InlineKeyboardButton("✂️ قیچی", callback_data=f"rps_pick_{game_id}_scissors"),
    ]])

    def render(p):
        text = f"🎮 {p1['name']} 🆚 {p2['name']}\n\nانتخابتو بزن — فقط خودت می‌بینیش 👇"
        return text, keyboard

    await gs.broadcast_custom(context.bot, session, render)


async def rps_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data  # rps_pick_<game_id>_<choice>
    _, _, game_id, choice = data.split("_")

    session = gs.get_game(game_id)
    if not session:
        await query.answer("این بازی دیگه فعال نیست.", show_alert=True)
        return

    user = query.from_user
    player = gs.find_player(session, user.id)
    if not player:
        await query.answer("شما بازیکن این بازی نیستید.", show_alert=True)
        return
    if session["status"] != "playing":
        await query.answer("بازی هنوز شروع نشده.", show_alert=True)
        return
    if user.id in session["choices"]:
        await query.answer(f"انتخاب قبلی شما: {NAMES_FA[session['choices'][user.id]]}", show_alert=True)
        return

    session["choices"][user.id] = choice
    await query.answer(f"انتخاب شما: {NAMES_FA[choice]} ✅", show_alert=True)

    if len(session["choices"]) == 2:
        p1, p2 = session["players"]
        c1, c2 = session["choices"][p1["user_id"]], session["choices"][p2["user_id"]]

        if c1 == c2:
            result = "🤝 مساوی شد!"
            db.record_result(p1["user_id"], KIND, "draw")
            db.record_result(p2["user_id"], KIND, "draw")
        elif BEATS[c1] == c2:
            result = f"🏆 {p1['name']} برنده شد!"
            db.record_result(p1["user_id"], KIND, "win")
            db.record_result(p2["user_id"], KIND, "loss")
        else:
            result = f"🏆 {p2['name']} برنده شد!"
            db.record_result(p2["user_id"], KIND, "win")
            db.record_result(p1["user_id"], KIND, "loss")

        text = (
            f"🎮 {p1['name']} 🆚 {p2['name']}\n\n"
            f"{p1['name']}: {EMOJI[c1]} {NAMES_FA[c1]}\n"
            f"{p2['name']}: {EMOJI[c2]} {NAMES_FA[c2]}\n\n"
            f"{result}"
        )
        await gs.broadcast_custom(context.bot, session, lambda p: (text, None))
        gs.remove_game(game_id)
