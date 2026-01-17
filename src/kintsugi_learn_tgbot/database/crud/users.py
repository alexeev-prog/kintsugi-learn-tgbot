from typing import Optional, Dict, Any
from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ..models import User, UserWord, ReviewLog


class UserCRUD:
    """CRUD операции для пользователей"""

    @staticmethod
    async def get_or_create(
        session: AsyncSession,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        language_code: str = "ru",
    ) -> User:
        """Получить или создать пользователя"""
        # Ищем существующего пользователя
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Обновляем информацию если есть изменения
            update_data = {}
            if username and username != user.username:
                update_data["username"] = username
            if first_name and first_name != user.first_name:
                update_data["first_name"] = first_name
            if last_name and last_name != user.last_name:
                update_data["last_name"] = last_name
            if phone_number and phone_number != user.phone_number:
                update_data["phone_number"] = phone_number
            if language_code and language_code != user.language_code:
                update_data["language_code"] = language_code

            if update_data:
                update_data["last_activity"] = datetime.utcnow()
                stmt = update(User).where(User.id == user.id).values(**update_data)
                await session.execute(stmt)
                await session.refresh(user)
            else:
                # Просто обновляем last_activity
                user.last_activity = datetime.utcnow()
                await session.commit()

            return user

        # Создаем нового пользователя
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            language_code=language_code,
            registered_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)

        return user

    @staticmethod
    async def get_by_telegram_id(
        session: AsyncSession, telegram_id: int
    ) -> Optional[User]:
        """Получить пользователя по telegram_id"""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_activity(session: AsyncSession, telegram_id: int) -> bool:
        """Обновить время последней активности"""
        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(last_activity=datetime.utcnow())
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def update_stats(session: AsyncSession, user_id: int, **stats) -> bool:
        """Обновить статистику пользователя"""
        valid_fields = {"total_words", "total_reviews", "streak_days", "max_streak"}

        update_data = {k: v for k, v in stats.items() if k in valid_fields}
        if not update_data:
            return False

        stmt = update(User).where(User.id == user_id).values(**update_data)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def get_user_stats(session: AsyncSession, user_id: int) -> Dict[str, Any]:
        """Получить статистику пользователя"""
        # Получаем пользователя
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return {}

        # Считаем слова по статусам
        stmt_status = (
            select(UserWord.status, func.count(UserWord.id).label("count"))
            .where(UserWord.user_id == user_id)
            .group_by(UserWord.status)
        )

        status_result = await session.execute(stmt_status)
        status_counts = {row.status: row.count for row in status_result}

        # Сегодняшние повторения
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())

        stmt_today = select(func.count(ReviewLog.id)).where(
            and_(ReviewLog.user_id == user_id, ReviewLog.reviewed_at >= today_start)
        )
        today_result = await session.execute(stmt_today)
        today_reviews = today_result.scalar() or 0

        return {
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "registered_at": user.registered_at,
                "last_activity": user.last_activity,
            },
            "stats": {
                "total_words": user.total_words,
                "total_reviews": user.total_reviews,
                "streak_days": user.streak_days,
                "max_streak": user.max_streak,
                "today_reviews": today_reviews,
            },
            "words_by_status": status_counts,
        }
