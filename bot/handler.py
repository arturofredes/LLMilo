from __future__ import annotations

import logging
import os
from collections import defaultdict

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes

from agent.loop import agent_loop
from mcp_tools.client import MCPToolClient

load_dotenv()

logger = logging.getLogger(__name__)

ALLOWED_CHATS: set[int] = {
    int(cid.strip())
    for cid in os.getenv("ALLOWED_CHATS", "").split(",")
    if cid.strip()
}

MAX_HISTORY = 20
_histories: dict[int, list[dict]] = defaultdict(list)


def _is_allowed(chat_id: int) -> bool:
    if not ALLOWED_CHATS:
        return True
    return chat_id in ALLOWED_CHATS


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if not _is_allowed(chat_id):
        logger.warning("Unauthorized chat_id=%s", chat_id)
        return

    mcp_client: MCPToolClient = context.bot_data["mcp_client"]

    history = _histories[chat_id]
    history.append({"role": "user", "content": text})

    if len(history) > MAX_HISTORY * 2:
        history[:] = history[-MAX_HISTORY * 2 :]

    try:
        reply = await agent_loop(history, mcp_client)
    except Exception:
        logger.exception("Agent loop failed for chat_id=%s", chat_id)
        reply = "Sorry, something went wrong."

    history.append({"role": "assistant", "content": reply})

    await update.message.reply_text(reply)
