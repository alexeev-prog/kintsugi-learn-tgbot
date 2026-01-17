from typing import Dict, Any, List
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from ..models import User, ReviewLog, DictionaryWord


class StatsCRUD:
    """CRUD операции для статистики"""

    @staticmethod
    async def get_global_stats(session: AsyncSession) -> Dict[str, Any]:
        """Получить глобальную статистику"""
        # Общее количество пользователей
        stmt = select(func.count(User.id))
        result = await session.execute(stmt)
        total_users = result.scalar() or 0

        # Активные пользователи за последние 7 дней
        week_ago = datetime.utcnow() - timedelta(days=7)
        stmt = select(func.count(User.id)).where(
            and_(User.last_activity >= week_ago, User.is_active)
        )
        result = await session.execute(stmt)
        active_users = result.scalar() or 0

        # Общее количество слов в словаре
        stmt = select(func.count(DictionaryWord.id))
        result = await session.execute(stmt)
        total_words = result.scalar() or 0

        # Самые популярные слова
        stmt = (
            select(
                DictionaryWord.word,
                DictionaryWord.meaning,
                DictionaryWord.times_searched,
            )
            .order_by(DictionaryWord.times_searched.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        popular_words = [
            {"word": word, "meaning": meaning, "searches": searches}
            for word, meaning, searches in result
        ]

        # Статистика по дням
        week_stats = []
        for i in range(7):
            day = datetime.utcnow().date() - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())

            stmt = select(func.count(ReviewLog.id)).where(
                and_(
                    ReviewLog.reviewed_at >= day_start, ReviewLog.reviewed_at <= day_end
                )
            )
            result = await session.execute(stmt)
            reviews = result.scalar() or 0

            week_stats.append({"date": day.strftime("%Y-%m-%d"), "reviews": reviews})

        week_stats.reverse()  # От старых к новым

        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_words": total_words,
            "popular_words": popular_words,
            "week_stats": week_stats,
        }

    @staticmethod
    async def get_user_activity_stats(
        session: AsyncSession, user_id: int, days: int = 30
    ) -> Dict[str, Any]:
        """Получить статистику активности пользователя"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Повторения по дням
        daily_stats = []
        for i in range(days):
            day = (end_date - timedelta(days=i)).date()
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())

            stmt = select(func.count(ReviewLog.id)).where(
                and_(
                    ReviewLog.user_id == user_id,
                    ReviewLog.reviewed_at >= day_start,
                    ReviewLog.reviewed_at <= day_end,
                )
            )
            result = await session.execute(stmt)
            reviews = result.scalar() or 0

            daily_stats.append({"date": day.strftime("%Y-%m-%d"), "reviews": reviews})

        daily_stats.reverse()

        # Статистика по действиям
        stmt = (
            select(ReviewLog.action, func.count(ReviewLog.id).label("count"))
            .where(
                and_(ReviewLog.user_id == user_id, ReviewLog.reviewed_at >= start_date)
            )
            .group_by(ReviewLog.action)
        )

        result = await session.execute(stmt)
        actions_stats = {row.action: row.count for row in result}

        # Распределение по времени суток
        stmt = (
            select(
                func.extract("hour", ReviewLog.reviewed_at).label("hour"),
                func.count(ReviewLog.id).label("count"),
            )
            .where(
                and_(ReviewLog.user_id == user_id, ReviewLog.reviewed_at >= start_date)
            )
            .group_by("hour")
            .order_by("hour")
        )

        result = await session.execute(stmt)
        hourly_stats = {int(row.hour): row.count for row in result}

        return {
            "daily_stats": daily_stats,
            "actions_stats": actions_stats,
            "hourly_stats": hourly_stats,
            "period_days": days,
        }

    @staticmethod
    async def get_leaderboard(
        session: AsyncSession, metric: str = "total_reviews", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Получить таблицу лидеров"""
        valid_metrics = ["total_reviews", "total_words", "streak_days"]
        if metric not in valid_metrics:
            metric = "total_reviews"

        order_column = getattr(User, metric)

        stmt = (
            select(User.username, User.first_name, order_column)
            .where(and_(User.is_active, User.role == "user"))
            .order_by(order_column.desc())
            .limit(limit)
        )

        result = await session.execute(stmt)

        leaderboard = []
        for i, (username, first_name, value) in enumerate(result, 1):
            name = username or first_name or f"User{i}"
            leaderboard.append(
                {"rank": i, "name": name, "value": value, "metric": metric}
            )

        return leaderboard
