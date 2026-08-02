from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
import game_sessions as gs
import board_images as bi

KIND = "c4"
ROWS, COLS = bi.ROWS, bi.COLS
DISC = {"R": "🔴", "Y": "🟡"}


def _new_grid():
    return [[None] * COLS for _ in range(ROWS)]


def _drop(grid, col, color):
    """Returns the row the piece landed on, or None if the column is full."""
    for r in range(ROWS - 1, -1, -1):
        if grid[r][col] is None:
            grid[r][col] = color
            return r
    return None


def _check_win(grid, color):
    for r in range(ROWS):
        for c in range(COLS):
            if grid[r][c] != color:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                cells = [(r + dr * k, c + dc * k) for k in range(4)]
                if all(0 <= rr < ROWS and 0 <= cc < COLS and grid[rr][cc] == color for rr, cc in cells):
                    return True
    return False


def _keyboard(game_id, grid, active):
    row = []
    for c in range(COLS):
        full = grid[0][c] is not None
        cb = f"c4_pick_{game_id}_{c}" if (active and not full) else "c4_noop"
        row.append(InlineKeyboardButton(str(c + 1), callback_data=cb))
    return InlineKeyboardMarkup([row])


def _caption(session):
    p1, p2 = session["players"]
    turn_name = p1["name"] if session["turn"] == p1["user_id"] else p2["name"]
    return f"🔴 {p1['name']}   🆚   🟡 {p2['name']}\n\nنوبت: {turn_name}"


async def c4_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    db.upsert_user(user.id, user.username, user.first_name)

    session = gs.create_game(
        KIND, user, chat.id,
        extra={"grid": _new_grid(), "turn": None, "color": {user.id: "R"}},
    )
    link = f"https://t.me/{context.bot.username}?start=join_{KIND}_{session['id']}"
    text = f"🔴🟡 {session['players'][0]['name']} یه بازی چهار در ردیف ساخت!\n\nاین لینک رو برای دوستت بفرست تا بهت ملحق بشه 👇"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 دعوت به بازی", url=link)]])
    msg = await update.message.reply_text(text, reply_markup=keyboard)
    session["players"][0]["msg_id"] = msg.message_id


async def c4_join(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
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
    session["color"][user.id] = "Y"
    session["turn"] = session["players"][0]["user_id"]
    session["status"] = "playing"

    def render(p):
        active = p["user_id"] == session["turn"]
        img = bi.render_connect4(session["grid"])
        return img, _caption(session), _keyboard(game_id, session["grid"], active)

    await gs.broadcast_photo(context.bot, session, render)


async def c4_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "c4_noop":
        await query.answer()
        return

    _, _, game_id, col = data.split("_")
    col = int(col)
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

    grid = session["grid"]
    color = session["color"][user.id]
    landed_row = _drop(grid, col, color)
    if landed_row is None:
        await query.answer("این ستون پره!", show_alert=True)
        return
    await query.answer()

    p1, p2 = session["players"]

    if _check_win(grid, color):
        winner = gs.find_player(session, user.id)
        loser = p2 if winner["user_id"] == p1["user_id"] else p1
        db.record_result(winner["user_id"], KIND, "win")
        db.record_result(loser["user_id"], KIND, "loss")
        caption = _caption(session) + f"\n\n🏆 {winner['name']} برد!"

        def render(p):
            img = bi.render_connect4(grid)
            return img, caption, _keyboard(game_id, grid, False)

        await gs.broadcast_photo(context.bot, session, render)
        gs.remove_game(game_id)
        return

    if all(grid[0][c] is not None for c in range(COLS)):
        db.record_result(p1["user_id"], KIND, "draw")
        db.record_result(p2["user_id"], KIND, "draw")
        caption = _caption(session) + "\n\n🤝 مساوی شد!"

        def render(p):
            img = bi.render_connect4(grid)
            return img, caption, _keyboard(game_id, grid, False)

        await gs.broadcast_photo(context.bot, session, render)
        gs.remove_game(game_id)
        return

    session["turn"] = p2["user_id"] if session["turn"] == p1["user_id"] else p1["user_id"]

    def render(p):
        active = p["user_id"] == session["turn"]
        img = bi.render_connect4(grid)
        return img, _caption(session), _keyboard(game_id, grid, active)

    await gs.broadcast_photo(context.bot, session, render)
