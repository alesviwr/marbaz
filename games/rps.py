from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db

EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
NAMES_FA = {"rock": "سنگ", "paper": "کاغذ", "scissors": "قیچی"}
BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

# key: (chat_id, message_id) -> session dict
sessions = {}


def _name(user):
    return user.first_name or user.username or "بازیکن"


async def rps_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        text = f"⚔️ {_name(user)} به {_name(challenged)} چالش سنگ‌کاغذقیچی داد!\n\nمنتظر پاسخ..."
        keyboard = [[InlineKeyboardButton("✅ قبول چالش", callback_data="rps_accept")]]
    else:
        text = f"🎮 {_name(user)} یه بازی سنگ‌کاغذقیچی باز کرد!\n\nکی می‌خواد بازی کنه؟"
        keyboard = [[InlineKeyboardButton("🤝 پیوستن به بازی", callback_data="rps_accept")]]

    msg = await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    sessions[(chat.id, msg.message_id)] = {
        "p1": user.id, "p1_name": _name(user),
        "p2": challenged.id if challenged else None,
        "p2_name": _name(challenged) if challenged else None,
        "choices": {}, "status": "waiting",
    }


async def rps_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    if data == "rps_accept":
        if session["status"] != "waiting":
            await query.answer("بازی از قبل شروع شده.", show_alert=True)
            return
        if user.id == session["p1"]:
            await query.answer("نمی‌تونی با خودت بازی کنی! منتظر حریف باش.", show_alert=True)
            return
        if session["p2"] and user.id != session["p2"]:
            await query.answer("این چالش برای شما نیست.", show_alert=True)
            return

        db.upsert_user(user.id, user.username, user.first_name)
        session["p2"] = user.id
        session["p2_name"] = _name(user)
        session["status"] = "playing"

        keyboard = [[
            InlineKeyboardButton("🪨 سنگ", callback_data="rps_rock"),
            InlineKeyboardButton("📄 کاغذ", callback_data="rps_paper"),
            InlineKeyboardButton("✂️ قیچی", callback_data="rps_scissors"),
        ]]
        text = (
            f"🎮 {session['p1_name']} 🆚 {session['p2_name']}\n\n"
            "هر دو نفر، انتخابتون رو با دکمه زیر مخفیانه انجام بدید 👇"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer("بازی شروع شد!")
        return

    if data in ("rps_rock", "rps_paper", "rps_scissors"):
        choice = data.replace("rps_", "")
        if user.id not in (session["p1"], session["p2"]):
            await query.answer("شما بازیکن این راند نیستید.", show_alert=True)
            return
        if session["status"] != "playing":
            await query.answer("بازی هنوز شروع نشده.", show_alert=True)
            return
        if user.id in session["choices"]:
            await query.answer(
                f"انتخاب قبلی شما: {NAMES_FA[session['choices'][user.id]]}", show_alert=True
            )
            return

        session["choices"][user.id] = choice
        await query.answer(
            f"انتخاب شما: {NAMES_FA[choice]} ✅ (تا حریف انتخاب نکنه مخفی می‌مونه)",
            show_alert=True,
        )

        if len(session["choices"]) == 2:
            c1 = session["choices"][session["p1"]]
            c2 = session["choices"][session["p2"]]

            if c1 == c2:
                result_text = "🤝 مساوی شد!"
                db.record_result(session["p1"], "rps", "draw")
                db.record_result(session["p2"], "rps", "draw")
            elif BEATS[c1] == c2:
                result_text = f"🏆 {session['p1_name']} برنده شد!"
                db.record_result(session["p1"], "rps", "win")
                db.record_result(session["p2"], "rps", "loss")
            else:
                result_text = f"🏆 {session['p2_name']} برنده شد!"
                db.record_result(session["p2"], "rps", "win")
                db.record_result(session["p1"], "rps", "loss")

            text = (
                f"🎮 {session['p1_name']} 🆚 {session['p2_name']}\n\n"
                f"{session['p1_name']}: {EMOJI[c1]} {NAMES_FA[c1]}\n"
                f"{session['p2_name']}: {EMOJI[c2]} {NAMES_FA[c2]}\n\n"
                f"{result_text}"
            )
            await query.edit_message_text(text)
            del sessions[key]
