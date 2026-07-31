import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import config
import database as db
from games import rps, tictactoe
from games import snakes_ladders as sl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

GAME_FA = {"rps": "سنگ‌کاغذقیچی", "ttt": "دوز", "sl": "مار و پله"}

WELCOME_TEXT = (
    "سلام! 👋 به ربات بازی‌های گروهی خوش اومدی 🎮\n\n"
    "بازی‌های موجود:\n"
    "🪨📄✂️ /rps — سنگ کاغذ قیچی\n"
    "❌⭕ /ttt — دوز\n"
    "🐍🪜 /sl — مار و پله (تا ۴ نفر)\n\n"
    "📊 /score — امتیازات من\n"
    "🏆 /leaderboard — جدول برترین‌ها\n\n"
    "هر کدوم از دستورها رو بزنی، یه لینک دعوت می‌گیری — همون لینک رو برای دوستت "
    "بفرست (تو همین ربات یا هر چت دیگه‌ای)، وقتی روش بزنه با ربات چت خصوصی باز می‌شه "
    "و بازی شروع می‌شه."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        payload = args[0]
        for kind, join_fn in (
            ("rps", rps.rps_join),
            ("ttt", tictactoe.ttt_join),
            ("sl", sl.sl_join),
        ):
            prefix = f"join_{kind}_"
            if payload.startswith(prefix):
                game_id = payload[len(prefix):]
                await join_fn(update, context, game_id)
                return

    await update.message.reply_text(WELCOME_TEXT)


async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    stats = db.get_stats(user.id)
    if not stats:
        await update.message.reply_text(
            "هنوز تو هیچ بازی‌ای شرکت نکردی! یکی از دستورهای /rps /ttt /sl رو امتحان کن."
        )
        return
    lines = [f"📊 امتیازات {user.first_name}:\n"]
    for s in stats:
        lines.append(
            f"{GAME_FA.get(s['game'], s['game'])}: ✅ {s['wins']} برد | ❌ {s['losses']} باخت | 🤝 {s['draws']} مساوی"
        )
    await update.message.reply_text("\n".join(lines))


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game = "rps"
    if context.args:
        mapping = {
            "rps": "rps", "ttt": "ttt", "sl": "sl",
            "دوز": "ttt", "مار": "sl", "پله": "sl", "سنگ": "rps",
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
    lines.append("\nبرای بازی‌های دیگه: /leaderboard ttt یا /leaderboard sl")
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
        lines.append(f"• {u['first_name'] or '—'} | {uname} | ID: {u['user_id']}")

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
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("users", users_cmd))

    app.add_handler(CommandHandler("rps", rps.rps_start))
    app.add_handler(CallbackQueryHandler(rps.rps_callback, pattern=r"^rps_"))

    app.add_handler(CommandHandler("ttt", tictactoe.ttt_start))
    app.add_handler(CallbackQueryHandler(tictactoe.ttt_callback, pattern=r"^ttt_"))

    app.add_handler(CommandHandler("sl", sl.sl_start))
    app.add_handler(CallbackQueryHandler(sl.sl_callback, pattern=r"^sl_"))

    logger.info("ربات در حال اجراست...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
