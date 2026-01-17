import asyncio
import platform
from loguru import logger
from datetime import datetime

from kintsugi_learn_tgbot.database.base import init_db, db_manager, DatabaseManager
from kintsugi_learn_tgbot import handlers, utils
from kintsugi_learn_tgbot.utils import setup_logger, setup_default_commands
from kintsugi_learn_tgbot.loader import bot, dp, config
from kintsugi_learn_tgbot.middlewares.db import DBSessionMiddleware


async def on_startup() -> None:
    uname = platform.uname()

    system = f"\nСистема:\n 🖥️ {uname.system} {uname.release}\n 🌐 Node: {uname.node}\n 🕛 {datetime.now()}"

    await utils.setup_default_commands(bot)

    for admin_id in config.ADMINS_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=f"Бот был запущен: {system}")
        except Exception:
            pass


async def setup_database() -> DatabaseManager:
    await init_db(database_path=config.database.database_path, echo=False)

    return db_manager


async def start_bot() -> None:
    setup_logger()
    await setup_database()

    dp.include_routers(handlers.default_router)
    dp.include_router(handlers.dictionary_router)
    dp.message.middleware(DBSessionMiddleware())
    dp.callback_query.middleware(DBSessionMiddleware())

    try:
        await setup_default_commands(bot)
        await on_startup()
        logger.info("Start polling...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        logger.info("Close bot session...")
        await bot.session.close()


def main() -> None:
    asyncio.run(start_bot())
