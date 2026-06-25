from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from telegram.ext import Application, MessageHandler, filters

from bot.handler import handle_message
from mcp_tools.client import MCPToolClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name__)] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    mcp_client = MCPToolClient()
    await mcp_client.start()
    logger.info("MCP client started with %d tools", len(mcp_client.get_tools()))
    application.bot_data["mcp_client"] = mcp_client


async def post_shutdown(application: Application) -> None:
    mcp_client: MCPToolClient | None = application.bot_data.get("mcp_client")
    if mcp_client:
        await mcp_client.stop()
        logger.info("MCP client stopped")


if __name__ == "__main__":
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting polling...")
    app.run_polling()
