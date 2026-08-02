import secrets

from telegram import InputMediaPhoto
from telegram.error import TelegramError

GAMES = {}


def new_game_id():
    return secrets.token_hex(4)  # 8 hex chars, safe for deep-link payloads and callback_data


def create_game(kind, host_user, host_chat_id, extra=None):
    game_id = new_game_id()
    while game_id in GAMES:
        game_id = new_game_id()

    session = {
        "id": game_id,
        "kind": kind,
        "status": "waiting",
        "players": [{
            "user_id": host_user.id,
            "name": host_user.first_name or host_user.username or "بازیکن",
            "chat_id": host_chat_id,
            "msg_id": None,
        }],
    }
    if extra:
        session.update(extra)
    GAMES[game_id] = session
    return session


def get_game(game_id):
    return GAMES.get(game_id)


def remove_game(game_id):
    GAMES.pop(game_id, None)


def find_player(session, user_id):
    for p in session["players"]:
        if p["user_id"] == user_id:
            return p
    return None


async def broadcast_custom(bot, session, render_fn):
    """render_fn(player_dict) -> (text, keyboard_or_None). Sends/updates each
    player's own private copy of the game message, in their own chat."""
    for p in session["players"]:
        text, keyboard = render_fn(p)
        try:
            if p["msg_id"] is None:
                msg = await bot.send_message(p["chat_id"], text, reply_markup=keyboard)
                p["msg_id"] = msg.message_id
            else:
                await bot.edit_message_text(
                    text, chat_id=p["chat_id"], message_id=p["msg_id"], reply_markup=keyboard
                )
        except TelegramError:
            # e.g. "message is not modified", or the chat became unreachable
            pass


async def broadcast_photo(bot, session, render_fn):
    """render_fn(player_dict) -> (photo_bytesio, caption, keyboard_or_None).
    Sends a fresh photo if the player has no message yet (or is switching from
    a text message), otherwise edits the existing photo message in place."""
    for p in session["players"]:
        photo_buf, caption, keyboard = render_fn(p)
        try:
            if p["msg_id"] is None:
                msg = await bot.send_photo(p["chat_id"], photo=photo_buf, caption=caption, reply_markup=keyboard)
                p["msg_id"] = msg.message_id
            else:
                media = InputMediaPhoto(media=photo_buf, caption=caption)
                await bot.edit_message_media(
                    chat_id=p["chat_id"], message_id=p["msg_id"], media=media, reply_markup=keyboard
                )
        except TelegramError:
            # e.g. trying to edit a text message into a photo — fall back to a fresh send
            try:
                msg = await bot.send_photo(p["chat_id"], photo=photo_buf, caption=caption, reply_markup=keyboard)
                p["msg_id"] = msg.message_id
            except TelegramError:
                pass


async def broadcast(bot, session, text, keyboard=None):
    await broadcast_custom(bot, session, lambda p: (text, keyboard))
