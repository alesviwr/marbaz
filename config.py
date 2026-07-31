import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Comma-separated Telegram user IDs allowed to use admin-only commands (e.g. /users)
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {int(x) for x in _admin_ids_raw.split(",") if x.strip().lstrip("-").isdigit()}
