from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

default_router = Router()

@default_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🇯🇵 Добро пожаловать в Kintsugi-Learn-Bot! Я позволяю изучать японский через карточки, квизы и личный словарь, предоставляя неограниченные возможности для самообучения\n\n"
        "Бот для изучения японского языка с помощью:\n"
        "• 📚 Карточек для запоминания\n"
        "• 🎯 Интерактивных викторин на произношщение, чтение и перевод\n"
        "• 🔍 Личного словаря со всей справочной информацией по слову\n\n"
        "Используйте /help для списка команд"
    )


@default_router.message(Command("stop"))
async def cmd_stop(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("⚠️ Нет активных действий для остановки")
        return

    await state.clear()
    await message.answer("✅ Действие остановлено. Используйте /help для списка команд")


@default_router.message(Command("help"))
async def cmd_help(message: Message):
    """
    Send help message with all available commands
    """
    help_text = (
        "<b>🇯🇵 Kintsugi-Learn-Bot — Помощь по командам</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "🚀 <b>Основные команды</b>\n"
        "/start — Запустить бота и получить приветствие\n"
        "/help — Показать эту справку\n"
        "/stop — Остановить текущее действие\n\n"

        "🔍 <b>Словарь и поиск</b>\n"
        "/search [слово] — Найти слово в Jisho API\n"
        "   <i>Пример:</i> /search 寿司 или /search sushi\n"
        "/dictionary — Показать мой личный словарь\n"
        "/add_word — Добавить слово вручную\n"
        "/remove_word — Удалить слово из словаря\n\n"

        "📚 <b>Карточки для запоминания (SRS)</b>\n"
        "/cards — Карточки для повторения\n"
        "/review — Повторить сложные слова\n"
        "/new_cards — Новые слова для изучения\n\n"

        "🎯 <b>Викторины и тесты</b>\n"
        "/quiz — Начать викторину (меню выбора типа)\n"
        "/quiz_reading — Викторина: угадай чтение кандзи\n"
        "/quiz_audio — Аудио-викторина по произношению\n"
        "/quiz_meaning — Викторина: выбери правильный перевод\n\n"

        "🏷️ <b>Теги и категории</b>\n"
        "/list_tags — Показать все мои теги\n"
        "/words_by_tag [тег] — Слова по определенному тегу\n"
        "   <i>Пример:</i> /words_by_tag еда\n\n"

        "📊 <b>Статистика и прогресс</b>\n"
        "/stats — Подробная статистика обучения\n"
        "/progress — Прогресс по дням и неделям\n"
        "/achievements — Мои достижения\n\n"

        "⚙️ <b>Настройки и управление</b>\n"
        "/settings — Настройки бота\n"
        "/export — Экспортировать словарь в файл\n"
        "/import — Импортировать словарь из файла\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    await message.answer(help_text, parse_mode="HTML")


@default_router.message(Command("commands"))
async def cmd_commands(message: Message):
    """
    Alternative simple command list
    """
    commands_list = (
        "<b>📋 Быстрый список команд:</b>\n\n"
        "🚀 start | help | stop\n"
        "🔍 search | dictionary | add_word | remove_word\n"
        "📚 cards | review | new_cards\n"
        "🎯 quiz | quiz_reading | quiz_audio | quiz_meaning\n"
        "🏷️ list_tags | words_by_tag\n"
        "📊 stats | progress | achievements\n"
        "⚙️ settings | export | import\n\n"
        "<i>Используйте /help для подробного описания каждой команды</i>"
    )

    await message.answer(commands_list, parse_mode="HTML")
