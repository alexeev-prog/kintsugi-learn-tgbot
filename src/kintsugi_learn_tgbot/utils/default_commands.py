from aiogram.types import BotCommand, BotCommandScopeDefault


async def setup_default_commands(bot):
    """
    Setup default bot commands with categories

    :param bot: Bot
    :type bot: bot
    """
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота Kintsugi"),
        BotCommand(command="help", description="📖 Помощь и инструкции"),
        BotCommand(command="stop", description="⏹️ Остановить текущее действие"),
        # Words
        BotCommand(command="search", description="🔍 Поиск слова"),
        BotCommand(command="dictionary", description="📖 Показать мой словарь"),
        BotCommand(command="add_word", description="➕ Добавить слово вручную"),
        BotCommand(command="remove_word", description="🗑️ Удалить слово из словаря"),
        # Cards
        BotCommand(command="cards", description="📚 Карточки для повторения (SRS)"),
        BotCommand(command="review", description="🔄 Повторить сложные слова"),
        BotCommand(command="new_cards", description="🆕 Новые карточки для изучения"),
        # Quiz
        BotCommand(command="quiz", description="🎯 Начать викторину"),
        BotCommand(command="quiz_reading", description="📖 Викторина: угадай чтение"),
        BotCommand(command="quiz_audio", description="🔊 Аудио-викторина"),
        BotCommand(command="quiz_meaning", description="💡 Викторина: выбери перевод"),
        # Stats
        BotCommand(command="list_tags", description="📝 Показать все мои теги"),
        BotCommand(command="words_by_tag", description="🏷️ Слова по тегу"),
        BotCommand(command="stats", description="📊 Моя статистика"),
        BotCommand(command="progress", description="📈 Прогресс обучения"),
        BotCommand(command="achievements", description="🏆 Мои достижения"),
        # Settings
        BotCommand(command="settings", description="⚙️ Настройки бота"),
        BotCommand(command="export", description="📤 Экспорт словаря"),
        BotCommand(command="import", description="📥 Импорт словаря"),
    ]

    await bot.set_my_commands(commands, BotCommandScopeDefault())
