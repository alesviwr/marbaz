import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters,
)

import config
import database as db
from games import rps, tictactoe, connect4, bulls_cows
from games import snakes_ladders as sl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

GAME_FA = {
    "rps": "سنگ‌کاغذقیچی",
    "ttt": "دوز",
    "sl": "مار و پله",
    "c4": "چهار در ردیف",
    "bc": "گاو و گوسفند",
}

MENU_GAMES = [
    ("rps", "🪨📄✂️ سنگ کاغذ قیچی (۳ دست)"),
    ("ttt", "❌⭕ دوز"),
    ("c4", "🔴🟡 چهار در ردیف"),
    ("sl", "🐍🪜 مار و پله"),
    ("bc", "🐄🐑 گاو و گوسفند"),
]

WELCOME_TEXT = (
    "سلام! 👋 به ربات بازی‌های گروهی خوش اومدی 🎮\n\n"
    "برای دیدن لیست بازی‌ها و شروع بازی از دکمه‌ها استفاده کن، یا /play رو بزن.\n\n"
    "📊 /score — امتیازات من\n\n"
    "هر بازی رو که شروع کنی یه لینک دعوت می‌گیری — همون لینک رو برای دوستت بفرست "
    "(تو همین ربات یا هر چت دیگه‌ای)، وقتی روش بزنه با ربات چت خصوصی باز می‌شه و بازی شروع می‌شه."
)


def _menu_keyboard():
    rows = [[InlineKeyboardButton(label, callback_data=f"menu_{key}")] for key, label in MENU_GAMES]
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        payload = args[0]
        for kind, join_fn in (
            ("rps", rps.rps_join),
            ("ttt", tictactoe.ttt_join),
            ("sl", sl.sl_join),
            ("c4", connect4.c4_join),
            ("bc", bulls_cows.bc_join),
        ):
            prefix = f"join_{kind}_"
            if payload.startswith(prefix):
                game_id = payload[len(prefix):]
                await join_fn(update, context, game_id)
                return

    await update.message.reply_text(WELCOME_TEXT, reply_markup=_menu_keyboard())


async def play_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎮 کدوم بازی رو می‌خوای شروع کنی؟", reply_markup=_menu_keyboard())


class _UpdateShim:
    """Adapts a CallbackQuery into the minimal Update-like shape the game
    start functions expect (.effective_user, .effective_chat, .message)."""

    def __init__(self, query):
        self.effective_user = query.from_user
        self.effective_chat = query.message.chat
        self.message = query.message


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key = query.data.replace("menu_", "")
    await query.answer()

    starters = {
        "rps": rps.rps_start,
        "ttt": tictactoe.ttt_start,
        "sl": sl.sl_start,
        "c4": connect4.c4_start,
        "bc": bulls_cows.bc_start,
    }
    starter = starters.get(key)
    if not starter:
        return

    await starter(_UpdateShim(query), context)


async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    stats = db.get_stats(user.id)
    if not stats:
        await update.message.reply_text(
            "هنوز تو هیچ بازی‌ای شرکت نکردی! /play رو بزن و یه بازی شروع کن."
        )
        return
    lines = [f"📊 امتیازات {user.first_name}:\n"]
    for s in stats:
        game_name = GAME_FA.get(s["game"], s["game"])
        lines.append(f"{game_name}: ✅ {s['wins']} برد | ❌ {s['losses']} باخت | 🤝 {s['draws']} مساوی")
    await update.message.reply_text("\n".join(lines))


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        await update.message.reply_text("این دستور فقط برای ادمین ربات در دسترسه.")
        return

    game = "rps"
    if context.args:
        mapping = {
            "rps": "rps", "ttt": "ttt", "sl": "sl", "c4": "c4", "bc": "bc",
            "دوز": "ttt", "مار": "sl", "پله": "sl", "سنگ": "rps",
            "چهار": "c4", "گاو": "bc",
        }
        game = mapping.get(context.args[0].lower(), "rps")

    rows = db.get_leaderboard(game)
    if not rows:
        await update.message.reply_text("هنوز کسی تو این بازی امتیازی نگرفته.")
        return

    lines = [f"🏆 جدول برترین‌های {GAME_FA[game]}:\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i + 1}."
        name = r["first_name"] or r["username"] or "بازیکن"
        lines.append(f"{medal} {name} — {r['wins']} برد / {r['losses']} باخت")
    lines.append("\nبرای بازی‌های دیگه: /leaderboard ttt، /leaderboard c4، /leaderboard sl، /leaderboard bc")
    await update.message.reply_text("\n".join(lines))


async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        await update.message.reply_text("این دستور فقط برای ادمین ربات در دسترسه.")
        return

    all_users = db.get_all_users()
    if not all_users:
        await update.message.reply_text("هنوز کاربری ثبت نشده.")
        return

    lines = [f"👤 لیست کاربران ({len(all_users)} نفر):\n"]
    for u in all_users:
        uname = f"@{u['username']}" if u["username"] else "—"
        first_name = u["first_name"] or "—"
        lines.append(f"• {first_name} | {uname} | ID: {u['user_id']}")

    text = "\n".join(lines)
    for i in range(0, len(text), 3500):
        await update.message.reply_text(text[i:i + 3500])


def main():
    if not config.BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN تنظیم نشده. فایل .env رو از روی .env.example بساز و توکن ربات رو توش بذار."
        )

    db.init_db()
    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("play", play_menu))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu_"))

    app.add_handler(CommandHandler("rps", rps.rps_start))
    app.add_handler(CallbackQueryHandler(rps.rps_callback, pattern=r"^rps_"))

    app.add_handler(CommandHandler("ttt", tictactoe.ttt_start))
    app.add_handler(CallbackQueryHandler(tictactoe.ttt_callback, pattern=r"^ttt_"))

    app.add_handler(CommandHandler("sl", sl.sl_start))
    app.add_handler(CallbackQueryHandler(sl.sl_callback, pattern=r"^sl_"))

    app.add_handler(CommandHandler("c4", connect4.c4_start))
    app.add_handler(CallbackQueryHandler(connect4.c4_callback, pattern=r"^c4_"))

    app.add_handler(CommandHandler("bc", bulls_cows.bc_start))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, bulls_cows.handle_text
    ))

    logger.info("ربات در حال اجراست...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
