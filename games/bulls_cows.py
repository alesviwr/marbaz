"""Bulls & Cows (گاو و گوسفند): each player picks a secret 4-digit number with
unique digits, then players take turns guessing the opponent's number. Text-based,
so it works via plain messages (private chat only) rather than inline buttons."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
import game_sessions as gs

KIND = "bc"

# chat_id -> game_id, so incoming plain-text messages know which game they belong to
PENDING = {}


def _valid_number(text):
    text = text.strip()
    if len(text) != 4 or not text.isdigit():
        return None
    if text[0] == "0":
        return None
    if len(set(text)) != 4:
        return None
    return text


def _score(secret, guess):
    cows = sum(1 for a, b in zip(secret, guess) if a == b)
    sheep = len(set(secret) & set(guess)) - cows
    return cows, sheep


async def bc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type != "private":
        await update.message.reply_text(
            "این بازی چون شامل عدد مخفیه، فقط تو چت خصوصی با ربات کار می‌کنه.\n"
            f"به @{context.bot.username} پیام بده و اونجا /bc رو بزن."
        )
        return

    db.upsert_user(user.id, user.username, user.first_name)
    session = gs.create_game(KIND, user, chat.id, extra={"secrets": {}, "turn": None})
    link = f"https://t.me/{context.bot.username}?start=join_{KIND}_{session['id']}"

    PENDING[chat.id] = session["id"]
    host_name = session["players"][0]["name"]
    text = (
        f"🐄🐑 {host_name} یه بازی گاو‌و‌گوسفند ساخت!\n\n"
        "این لینک رو برای دوستت بفرست تا بهت ملحق بشه 👇\n\n"
        "بعد از پیوستنِ دوستت، هر دو نفر باید یه عدد چهار رقمی با ارقام متفاوت "
        "(رقم اول غیر صفر) براش بفرستید تا مخفیانه ثبت بشه."
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 دعوت به بازی", url=link)]])
    msg = await update.message.reply_text(text, reply_markup=keyboard)
    session["players"][0]["msg_id"] = msg.message_id


async def bc_join(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
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
    session["status"] = "setup"
    PENDING[chat.id] = game_id

    for p in session["players"]:
        try:
            await context.bot.send_message(
                p["chat_id"],
                "🔢 عدد مخفیت رو بفرست: یه عدد چهار رقمی با ارقام متفاوت، رقم اول غیر صفر.",
            )
        except Exception:
            pass


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    game_id = PENDING.get(chat.id)
    if not game_id:
        return

    session = gs.get_game(game_id)
    if not session or session["kind"] != KIND:
        PENDING.pop(chat.id, None)
        return

    raw = update.message.text or ""
    number = _valid_number(raw)
    if not number:
        await update.message.reply_text(
            "❗️ باید یه عدد چهار رقمی با ارقام متفاوت باشه و رقم اول صفر نباشه. دوباره امتحان کن."
        )
        return

    if session["status"] == "setup":
        await _handle_secret(update, context, session, user, number)
    elif session["status"] == "playing":
        await _handle_guess(update, context, session, user, number)


async def _handle_secret(update, context, session, user, number):
    if user.id in session["secrets"]:
        await update.message.reply_text("عدد مخفیت از قبل ثبت شده — منتظر حریف باش.")
        return

    session["secrets"][user.id] = number
    await update.message.reply_text("✅ عدد مخفیت ثبت شد.")

    if len(session["secrets"]) < len(session["players"]):
        return

    session["status"] = "playing"
    session["turn"] = session["players"][0]["user_id"]
    session["guess_count"] = {p["user_id"]: 0 for p in session["players"]}
    turn_name = gs.find_player(session, session["turn"])["name"]

    for p in session["players"]:
        try:
            note = "نوبت شماست! یه عدد چهار رقمی حدس بزن." if p["user_id"] == session["turn"] \
                else f"هر دو عدد ثبت شد. نوبت {turn_name}ه — منتظر بمون."
            await context.bot.send_message(p["chat_id"], f"🐄🐑 بازی شروع شد!\n{note}")
        except Exception:
            pass


async def _handle_guess(update, context, session, user, guess):
    if user.id != session["turn"]:
        await update.message.reply_text("الان نوبت شما نیست.")
        return

    opponent = next(p for p in session["players"] if p["user_id"] != user.id)
    secret = session["secrets"][opponent["user_id"]]
    cows, sheep = _score(secret, guess)
    session["guess_count"][user.id] += 1

    guesser_name = gs.find_player(session, user.id)["name"]
    result_line = f"{guesser_name} حدس زد: {guess}\n🐄 {cows} گاو   🐑 {sheep} گوسفند"

    if cows == 4:
        db.record_result(user.id, KIND, "win")
        db.record_result(opponent["user_id"], KIND, "loss")
        final = f"{result_line}\n\n🏆 {guesser_name} برنده شد! عدد درست بود: {secret}"
        for p in session["players"]:
            try:
                await context.bot.send_message(p["chat_id"], final)
            except Exception:
                pass
        PENDING.pop(session["players"][0]["chat_id"], None)
        PENDING.pop(session["players"][1]["chat_id"], None)
        gs.remove_game(session["id"])
        return

    session["turn"] = opponent["user_id"]
    next_name = opponent["name"]
    for p in session["players"]:
        try:
            tail = "نوبت شماست!" if p["user_id"] == opponent["user_id"] else f"نوبت {next_name}ه."
            await context.bot.send_message(p["chat_id"], f"{result_line}\n\n{tail}")
        except Exception:
            pass
