from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from kintsugi_learn_tgbot.database.base import get_db


class DBSessionMiddleware(BaseMiddleware):
    """Middleware для внедрения сессии БД"""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        async for session in get_db():
            data["session"] = session
            try:
                result = await handler(event, data)
                return result
            finally:
                break
