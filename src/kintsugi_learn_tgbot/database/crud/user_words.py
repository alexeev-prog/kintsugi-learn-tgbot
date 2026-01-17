from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ..models import UserWord, DictionaryWord, User, ReviewLog


class UserWordCRUD:
    """CRUD операции для слов пользователя"""

    @staticmethod
    async def add_word_to_user(
        session: AsyncSession, user_id: int, word_id: int, status: str = "new"
    ) -> Optional[UserWord]:
        """Добавить слово пользователю"""
        # Проверяем, есть ли уже это слово у пользователя
        stmt = select(UserWord).where(
            and_(UserWord.user_id == user_id, UserWord.word_id == word_id)
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        # Создаем новую запись
        user_word = UserWord(
            user_id=user_id, word_id=word_id, status=status, added_at=datetime.utcnow()
        )

        session.add(user_word)

        # Обновляем счетчик слов пользователя
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(total_words=User.total_words + 1)
        )
        await session.execute(stmt)

        # Обновляем счетчик добавлений слова
        stmt = (
            update(DictionaryWord)
            .where(DictionaryWord.id == word_id)
            .values(times_added=DictionaryWord.times_added + 1)
        )
        await session.execute(stmt)

        await session.commit()
        await session.refresh(user_word)

        return user_word

    @staticmethod
    async def get_user_word(
        session: AsyncSession, user_id: int, word_id: int
    ) -> Optional[UserWord]:
        """Получить слово пользователя"""
        stmt = select(UserWord).where(
            and_(UserWord.user_id == user_id, UserWord.word_id == word_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_word_status(
        session: AsyncSession, user_word_id: int, status: str, action: str = None
    ) -> bool:
        """Обновить статус слова пользователя"""
        stmt = (
            update(UserWord)
            .where(UserWord.id == user_word_id)
            .values(status=status, last_reviewed=datetime.utcnow())
        )
        result = await session.execute(stmt)
        await session.commit()

        # Если был action, логируем
        if action and result.rowcount > 0:
            user_word = await UserWordCRUD.get_by_id(session, user_word_id)
            if user_word:
                review_log = ReviewLog(
                    user_id=user_word.user_id,
                    user_word_id=user_word_id,
                    action=action,
                    reviewed_at=datetime.utcnow(),
                )
                session.add(review_log)

                # Обновляем счетчик повторений пользователя
                stmt = (
                    update(User)
                    .where(User.id == user_word.user_id)
                    .values(total_reviews=User.total_reviews + 1)
                )
                await session.execute(stmt)

                await session.commit()

        return result.rowcount > 0

    @staticmethod
    async def get_by_id(session: AsyncSession, user_word_id: int) -> Optional[UserWord]:
        """Получить слово пользователя по ID"""
        stmt = select(UserWord).where(UserWord.id == user_word_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_words(
        session: AsyncSession,
        user_id: int,
        status: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[UserWord]:
        """Получить слова пользователя"""
        stmt = select(UserWord).where(UserWord.user_id == user_id)

        if status:
            stmt = stmt.where(UserWord.status == status)

        stmt = stmt.order_by(UserWord.added_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_user_words_with_details(
        session: AsyncSession, user_id: int, status: str = None
    ) -> List[Dict[str, Any]]:
        """Получить слова пользователя с деталями из словаря"""
        stmt = (
            select(
                UserWord,
                DictionaryWord.word,
                DictionaryWord.reading,
                DictionaryWord.meaning,
            )
            .join(DictionaryWord, UserWord.word_id == DictionaryWord.id)
            .where(UserWord.user_id == user_id)
        )

        if status:
            stmt = stmt.where(UserWord.status == status)

        stmt = stmt.order_by(UserWord.added_at.desc())
        result = await session.execute(stmt)

        words = []
        for user_word, word, reading, meaning in result:
            words.append(
                {
                    "id": user_word.id,
                    "word": word,
                    "reading": reading,
                    "meaning": meaning,
                    "status": user_word.status,
                    "added_at": user_word.added_at,
                    "last_reviewed": user_word.last_reviewed,
                    "custom_meaning": user_word.custom_meaning,
                    "user_tags": user_word.user_tags,
                }
            )

        return words

    @staticmethod
    async def get_random_word_for_review(
        session: AsyncSession, user_id: int, exclude_ids: List[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Получить случайное слово для карточки"""
        stmt = (
            select(
                UserWord,
                DictionaryWord.word,
                DictionaryWord.reading,
                DictionaryWord.meaning,
                DictionaryWord.meanings,
            )
            .join(DictionaryWord, UserWord.word_id == DictionaryWord.id)
            .where(
                and_(
                    UserWord.user_id == user_id,
                    UserWord.status.in_(["new", "learning"]),
                )
            )
        )

        if exclude_ids:
            stmt = stmt.where(UserWord.id.notin_(exclude_ids))

        stmt = stmt.order_by(func.random()).limit(1)
        result = await session.execute(stmt)

        row = result.first()
        if not row:
            return None

        user_word, word, reading, meaning, meanings = row

        return {
            "user_word_id": user_word.id,
            "word": word,
            "reading": reading,
            "meaning": meaning,
            "meanings": meanings,
            "status": user_word.status,
            "user_tags": user_word.user_tags,
        }

    @staticmethod
    async def remove_word(session: AsyncSession, user_word_id: int) -> bool:
        """Удалить слово у пользователя"""
        # Получаем запись чтобы обновить счетчики
        stmt = select(UserWord).where(UserWord.id == user_word_id)
        result = await session.execute(stmt)
        user_word = result.scalar_one_or_none()

        if not user_word:
            return False

        # Удаляем запись
        stmt = delete(UserWord).where(UserWord.id == user_word_id)
        await session.execute(stmt)

        # Обновляем счетчик слов пользователя
        stmt = (
            update(User)
            .where(User.id == user_word.user_id)
            .values(total_words=User.total_words - 1)
        )
        await session.execute(stmt)

        await session.commit()
        return True
