from pathlib import Path
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from .models import Base


class DatabaseManager:
    """Менеджер базы данных для асинхронной работы с SQLite"""

    def __init__(self, database_path: str, echo: bool = False):
        self.database_path = database_path
        self.echo = echo
        self._engine: Optional[AsyncEngine] = None
        self._async_session_maker: Optional[sessionmaker] = None

        # Создаем директорию для базы данных если нет
        db_dir = Path(database_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    async def create_engine(self) -> AsyncEngine:
        """Создание асинхронного движка SQLite"""
        if self._engine is None:
            # SQLite требует специального URL для async
            sqlite_url = f"sqlite+aiosqlite:///{self.database_path}"

            self._engine = create_async_engine(
                sqlite_url,
                echo=self.echo,
                poolclass=StaticPool,  # SQLite не поддерживает пуллинг соединений
                connect_args={"check_same_thread": False},
            )
        return self._engine

    async def get_session_maker(self) -> sessionmaker:
        """Получение фабрики сессий"""
        if self._async_session_maker is None:
            engine = await self.create_engine()
            self._async_session_maker = sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
        return self._async_session_maker

    async def get_session(self) -> AsyncSession:
        """Получение сессии для работы с БД"""
        session_maker = await self.get_session_maker()
        return session_maker()

    async def create_tables(self):
        """Создание всех таблиц в базе данных"""
        engine = await self.create_engine()
        async with engine.begin() as conn:
            # Включаем поддержку FOREIGN KEY для SQLite
            # await conn.execute("PRAGMA foreign_keys=ON")
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self):
        """Удаление всех таблиц (для тестов)"""
        engine = await self.create_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def execute_raw_sql(self, sql: str, params: dict = None):
        """Выполнение RAW SQL запроса"""
        async with self.get_session() as session:
            result = await session.execute(sql, params or {})
            await session.commit()
            return result

    async def check_connection(self) -> bool:
        """Проверка подключения к БД"""
        try:
            async with self.get_session() as session:
                await session.execute("SELECT 1")
                return True
        except Exception:
            return False

    async def get_database_info(self) -> dict:
        """Получение информации о базе данных"""
        db_path = Path(self.database_path)
        return {
            "path": str(db_path.absolute()),
            "exists": db_path.exists(),
            "size_mb": db_path.stat().st_size / (1024 * 1024)
            if db_path.exists()
            else 0,
            "tables": [table.name for table in Base.metadata.tables.values()],
        }


# Глобальный экземпляр менеджера БД
db_manager: Optional[DatabaseManager] = None


async def init_db(database_path: str, echo: bool = False) -> DatabaseManager:
    """Инициализация базы данных"""
    global db_manager
    db_manager = DatabaseManager(database_path, echo)
    await db_manager.create_tables()
    return db_manager


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для получения сессии БД"""
    global db_manager
    if db_manager is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with await db_manager.get_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
