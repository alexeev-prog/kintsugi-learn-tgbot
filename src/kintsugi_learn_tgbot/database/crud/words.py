from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DictionaryWord


class WordCRUD:
    """CRUD операции для слов словаря"""

    @staticmethod
    async def get_or_create_from_jisho(
        session: AsyncSession, jisho_data: Dict[str, Any]
    ) -> DictionaryWord:
        """Создать или получить слово из данных Jisho"""
        slug = jisho_data.get("slug")

        if slug:
            stmt = select(DictionaryWord).where(DictionaryWord.jisho_slug == slug)
            result = await session.execute(stmt)
            existing_word = result.scalar_one_or_none()

            if existing_word:
                return existing_word

        # Создаем новое слово
        word_data = jisho_data.get("japanese", [{}])[0]
        senses = jisho_data.get("senses", [{}])[0]

        word = DictionaryWord(
            word=word_data.get("word", ""),
            reading=word_data.get("reading", ""),
            meaning=", ".join(senses.get("english_definitions", [])[:3]),
            meanings=senses.get("english_definitions", []),
            pos=", ".join(senses.get("parts_of_speech", [])[:2])
            if senses.get("parts_of_speech")
            else None,
            jisho_slug=jisho_data.get("slug"),
            is_common=jisho_data.get("is_common", False),
            jlpt_level=jisho_data.get("jlpt", [None])[0]
            if jisho_data.get("jlpt")
            else None,
            jisho_tags=jisho_data.get("tags", []),
            times_searched=1,
        )

        session.add(word)
        await session.commit()
        await session.refresh(word)

        return word

    @staticmethod
    async def get_by_id(
        session: AsyncSession, word_id: int
    ) -> Optional[DictionaryWord]:
        """Получить слово по ID"""
        stmt = select(DictionaryWord).where(DictionaryWord.id == word_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_slug(session: AsyncSession, slug: str) -> Optional[DictionaryWord]:
        """Получить слово по Jisho slug"""
        stmt = select(DictionaryWord).where(DictionaryWord.jisho_slug == slug)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def search_words(
        session: AsyncSession, query: str, limit: int = 10
    ) -> List[DictionaryWord]:
        """Поиск слов в словаре"""
        stmt = (
            select(DictionaryWord)
            .where(
                DictionaryWord.word.contains(query)
                | DictionaryWord.reading.contains(query)
                | DictionaryWord.meaning.contains(query)
            )
            .limit(limit)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def increment_search_count(session: AsyncSession, word_id: int) -> bool:
        """Увеличить счетчик поисков"""
        stmt = (
            update(DictionaryWord)
            .where(DictionaryWord.id == word_id)
            .values(times_searched=DictionaryWord.times_searched + 1)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def get_random_words(
        session: AsyncSession, limit: int = 10, is_common: bool = True
    ) -> List[DictionaryWord]:
        """Получить случайные слова"""
        stmt = select(DictionaryWord)

        if is_common:
            stmt = stmt.where(DictionaryWord.is_common)

        stmt = stmt.order_by(func.random()).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())
