import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    Float,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class WordStatus(str, enum.Enum):
    NEW = "new"  # Новое слово
    LEARNING = "learning"  # В процессе изучения
    KNOWN = "known"  # Уже знаю
    SKIPPED = "skipped"  # Пропущено


class User(Base):
    """
    Таблица пользователей Telegram
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)

    # Информация из профиля Telegram
    username = Column(String(100), nullable=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone_number = Column(String(20), nullable=True)
    language_code = Column(String(10), default="ru")

    # Статус
    role = Column(String(20), default="user")
    is_active = Column(Boolean, default=True)

    # Даты
    registered_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_activity = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Статистика
    total_words = Column(Integer, default=0)
    total_reviews = Column(Integer, default=0)
    streak_days = Column(Integer, default=0)
    max_streak = Column(Integer, default=0)

    # Внешние ключи
    words = relationship(
        "UserWord", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.telegram_id} ({self.username or self.first_name})>"


class DictionaryWord(Base):
    """
    Основная таблица слов из Jisho API
    """

    __tablename__ = "dictionary_words"

    id = Column(Integer, primary_key=True)

    # Основная информация
    word = Column(String(100), nullable=False, index=True)
    reading = Column(String(100), nullable=False)
    meaning = Column(Text, nullable=False)
    meanings = Column(JSON)  # Все переводы
    pos = Column(String(50))  # Часть речи

    # Информация из Jisho
    jisho_slug = Column(String(100), unique=True, index=True)
    is_common = Column(Boolean, default=False)
    jlpt_level = Column(String(10), nullable=True)
    jisho_tags = Column(JSON)

    # Метаданные
    audio_file_path = Column(String(255), nullable=True)
    example_sentences = Column(JSON)

    # Статистика
    times_searched = Column(Integer, default=0)
    times_added = Column(Integer, default=0)

    # Внешние ключи
    user_words = relationship("UserWord", back_populates="dictionary_word")

    def __repr__(self):
        return f"<DictionaryWord {self.word} ({self.reading})>"


class UserWord(Base):
    """
    Слова пользователя
    """

    __tablename__ = "user_words"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    word_id = Column(
        Integer,
        ForeignKey("dictionary_words.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Статус и даты
    status = Column(String(20), default="new")  # new, learning, known, skipped
    added_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_reviewed = Column(DateTime, nullable=True)

    # Пользовательские данные
    custom_meaning = Column(Text, nullable=True)
    personal_note = Column(Text, nullable=True)
    user_tags = Column(JSON)

    # Индексы
    __table_args__ = (
        Index("ix_user_words_user_word", "user_id", "word_id", unique=True),
        Index("ix_user_words_status", "user_id", "status"),
    )

    # Отношения
    user = relationship("User", back_populates="words")
    dictionary_word = relationship("DictionaryWord", back_populates="user_words")

    def __repr__(self):
        return (
            f"<UserWord user:{self.user_id} word:{self.word_id} status:{self.status}>"
        )


class ReviewLog(Base):
    """
    Лог повторений карточек
    """

    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_word_id = Column(
        Integer,
        ForeignKey("user_words.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Данные о повторении
    reviewed_at = Column(DateTime, default=datetime.datetime.utcnow)
    action = Column(String(20))  # show, skip, know, repeat, exit
    time_taken = Column(Float)  # Время в секундах

    # Контекст
    session_id = Column(String(100), nullable=True)

    # Отношения
    user = relationship("User")
    user_word = relationship("UserWord")

    def __repr__(self):
        return f"<ReviewLog user:{self.user_id} word:{self.user_word_id} action:{self.action}>"
