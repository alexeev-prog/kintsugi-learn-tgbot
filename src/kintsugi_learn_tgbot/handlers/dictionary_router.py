from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from typing import List, Dict, Any
from datetime import datetime

from kintsugi_learn_tgbot.services.jisho_service import jisho_service
from kintsugi_learn_tgbot.keyboards.inline_dictionary import keyboards
from kintsugi_learn_tgbot.database.crud.users import UserCRUD
from kintsugi_learn_tgbot.database.crud.words import WordCRUD
from kintsugi_learn_tgbot.database.crud.user_words import UserWordCRUD
from kintsugi_learn_tgbot.database.models import DictionaryWord

logger = logging.getLogger(__name__)

dictionary_router = Router()


# Состояния FSM
class DictionaryStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_word_id = State()
    waiting_for_tags = State()
    waiting_for_manual_word = State()
    waiting_for_manual_reading = State()
    waiting_for_manual_meaning = State()


@dictionary_router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext):
    """
    Обработчик команды /search
    Запрашивает слово для поиска
    """
    await message.answer(
        "🔍 <b>Введите слово для поиска:</b>\n\n"
        "Можно искать на:\n"
        "• 🇯🇵 Японском (кандзи, хирагана, катакана)\n"
        "• 🇬🇧 Английском\n"
        "• 🇷🇺 Русском (будет переведено на английский)\n\n"
        "<i>Примеры: 寿司, sushi, суши</i>",
        parse_mode="HTML",
    )
    await state.set_state(DictionaryStates.waiting_for_search)


@dictionary_router.message(DictionaryStates.waiting_for_search)
async def process_search_query(
    message: Message, state: FSMContext, session: AsyncSession
):
    """
    Обработка поискового запроса
    """
    query = message.text.strip()

    if not query:
        await message.answer("❌ Пожалуйста, введите слово для поиска")
        return

    # Проверяем язык ввода
    if jisho_service.is_japanese_text(query) or jisho_service.is_english_text(query):
        # Если японский или английский - ищем как есть
        search_query = query
    else:
        # Если русский или другой язык - переводим на английский
        # Здесь можно добавить переводчик, пока используем как есть
        search_query = query
        await message.answer(
            f"<i>Поиск по запросу: {query}</i>\n"
            f"<i>Для лучших результатов используйте английский или японский</i>",
            parse_mode="HTML",
        )

    # Показываем индикатор поиска
    searching_msg = await message.answer("🔍 Ищем слово...")

    try:
        # Ищем слово через Jisho API
        raw_data = await jisho_service.search_word(search_query)

        if not raw_data or not raw_data.get("data"):
            await searching_msg.edit_text(
                f"❌ Слово '<b>{query}</b>' не найдено\n\n"
                f"Попробуйте:\n"
                f"• Проверить написание\n"
                f"• Использовать английский перевод\n"
                f"• Ввести слово в другой форме",
                parse_mode="HTML",
            )
            await state.clear()
            return

        # Парсим результаты
        parsed_words = jisho_service.parse_jisho_response(raw_data)

        if not parsed_words:
            await searching_msg.edit_text("❌ Не удалось обработать результаты поиска")
            await state.clear()
            return

        # Сохраняем результаты в состоянии
        await state.update_data(
            search_results=parsed_words, search_query=query, current_page=0
        )

        # Форматируем первый результат
        first_word = parsed_words[0]
        formatted_text = jisho_service.format_word_for_display(first_word)

        # Проверяем, есть ли слово в словаре пользователя
        user = await UserCRUD.get_by_telegram_id(session, message.from_user.id)

        if user and first_word.get("slug"):
            # Проверяем, есть ли слово в общем словаре
            dict_word = await WordCRUD.get_by_slug(session, first_word["slug"])
            if dict_word:
                await UserWordCRUD.get_user_word(session, user.id, dict_word.id)

        # Создаем клавиатуру
        total_pages = len(parsed_words)  # Каждое слово на отдельной странице
        keyboard = keyboards.get_search_results_keyboard(
            words=parsed_words, current_page=0, total_pages=total_pages, query=query
        )

        await searching_msg.edit_text(
            f"🔍 <b>Результаты поиска для '{query}':</b>\n\n{formatted_text}",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        await searching_msg.edit_text(f"❌ Ошибка при поиске слова: {str(e)[:100]}")
        await state.clear()


@dictionary_router.callback_query(F.data.startswith("search_page:"))
async def process_search_page(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    """
    Обработка переключения страниц поиска
    """
    try:
        # Получаем данные из callback
        _, query, page_str = callback.data.split(":", 2)
        page = int(page_str)

        # Получаем сохраненные результаты
        state_data = await state.get_data()
        search_results = state_data.get("search_results", [])

        if page < 0 or page >= len(search_results):
            await callback.answer("Нет такой страницы")
            return

        # Получаем слово для текущей страницы
        word_data = search_results[page]
        formatted_text = jisho_service.format_word_for_display(word_data)

        # Проверяем, есть ли слово в словаре пользователя
        user = await UserCRUD.get_by_telegram_id(session, callback.from_user.id)

        if user and word_data.get("slug"):
            dict_word = await WordCRUD.get_by_slug(session, word_data["slug"])
            if dict_word:
                await UserWordCRUD.get_user_word(session, user.id, dict_word.id)

        # Обновляем состояние
        await state.update_data(current_page=page)

        # Создаем клавиатуру
        keyboard = keyboards.get_search_results_keyboard(
            words=search_results,
            current_page=page,
            total_pages=len(search_results),
            query=query,
        )

        await callback.message.edit_text(
            f"🔍 <b>Результаты поиска для '{query}':</b>\n\n{formatted_text}",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Page navigation error: {str(e)}")
        await callback.answer("Ошибка при переключении страницы")


@dictionary_router.callback_query(F.data == "new_search")
async def new_search_callback(callback: CallbackQuery, state: FSMContext):
    """
    Обработка кнопки нового поиска
    """
    await callback.message.edit_text(
        "🔍 <b>Введите слово для поиска:</b>\n\n"
        "Можно искать на японском, английском или русском",
        parse_mode="HTML",
    )
    await state.set_state(DictionaryStates.waiting_for_search)
    await callback.answer()


@dictionary_router.callback_query(F.data.startswith("word_detail:"))
async def word_detail_callback(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    """
    Просмотр деталей слова
    """
    try:
        _, word_slug = callback.data.split(":", 1)

        # Получаем сохраненные результаты
        state_data = await state.get_data()
        search_results = state_data.get("search_results", [])

        # Ищем слово по slug
        word_data = None
        for word in search_results:
            if word.get("slug") == word_slug:
                word_data = word
                break

        if not word_data:
            await callback.answer("Слово не найдено")
            return

        # Форматируем текст
        formatted_text = jisho_service.format_word_for_display(word_data)

        # Проверяем, есть ли слово в словаре пользователя
        user = await UserCRUD.get_by_telegram_id(session, callback.from_user.id)
        user_word = None
        user_word_id = None

        if user:
            dict_word = await WordCRUD.get_by_slug(session, word_slug)
            if dict_word:
                user_word = await UserWordCRUD.get_user_word(
                    session, user.id, dict_word.id
                )
                if user_word:
                    user_word_id = user_word.id

        # Создаем клавиатуру
        keyboard = keyboards.get_word_detail_keyboard(
            word_slug=word_slug,
            is_in_user_dict=user_word is not None,
            user_word_id=user_word_id,
        )

        await callback.message.edit_text(
            f"📖 <b>Детали слова:</b>\n\n{formatted_text}",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Word detail error: {str(e)}")
        await callback.answer("Ошибка при загрузке деталей")


@dictionary_router.callback_query(F.data.startswith("add_to_dict:"))
async def add_to_dict_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Добавление слова в словарь пользователя
    """
    try:
        _, word_slug = callback.data.split(":", 1)

        # Получаем пользователя
        user = await UserCRUD.get_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer("Пользователь не найден")
            return

        # Получаем слово из словаря или создаем
        dict_word = await WordCRUD.get_by_slug(session, word_slug)

        if not dict_word:
            # Если слова нет в нашем словаре, нужно его добавить
            # Для этого нужно получить данные из Jisho API
            raw_data = await jisho_service.search_word(word_slug)
            if raw_data and raw_data.get("data"):
                # Создаем запись в словаре
                dict_word = await WordCRUD.get_or_create_from_jisho(
                    session, raw_data["data"][0]
                )

        if not dict_word:
            await callback.answer("Не удалось добавить слово")
            return

        # Добавляем слово пользователю
        user_word = await UserWordCRUD.add_word_to_user(
            session, user.id, dict_word.id, status="new"
        )

        if user_word:
            await callback.answer("✅ Слово добавлено в ваш словарь!")

            # Обновляем клавиатуру
            keyboard = keyboards.get_word_detail_keyboard(
                word_slug=word_slug, is_in_user_dict=True, user_word_id=user_word.id
            )

            await callback.message.edit_reply_markup(reply_markup=keyboard)
        else:
            await callback.answer("❌ Не удалось добавить слово")

    except Exception as e:
        logger.error(f"Add to dict error: {str(e)}")
        await callback.answer("Ошибка при добавлении слова")


@dictionary_router.message(Command("dictionary"))
async def cmd_dictionary(message: Message, session: AsyncSession, state: FSMContext):
    """
    Показать словарь пользователя
    """
    # Получаем пользователя
    user = await UserCRUD.get_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return

    # Получаем слова пользователя
    user_words = await UserWordCRUD.get_user_words_with_details(session, user.id)

    if not user_words:
        await message.answer(
            "📖 <b>Ваш словарь пуст</b>\n\n"
            "Используйте команды:\n"
            "• /search - найти и добавить слово\n"
            "• /add_word - добавить слово вручную",
            parse_mode="HTML",
        )
        return

    # Сохраняем слова в состоянии
    await state.update_data(
        user_words=user_words, dict_current_page=0, items_per_page=10
    )

    # Сортируем по дате добавления (новые сначала)
    user_words_sorted = sorted(
        user_words, key=lambda x: x.get("added_at", datetime.min), reverse=True
    )

    # Рассчитываем общее количество страниц
    items_per_page = 10
    total_pages = (len(user_words_sorted) + items_per_page - 1) // items_per_page

    # Формируем текст для первой страницы
    response_text = format_dictionary_page(user_words_sorted, 0, items_per_page)

    # Создаем клавиатуру
    keyboard = keyboards.get_user_dictionary_keyboard(
        words=user_words_sorted,
        current_page=0,
        total_pages=total_pages,
        items_per_page=items_per_page,
    )

    await message.answer(response_text, reply_markup=keyboard, parse_mode="HTML")


def format_dictionary_page(
    words: List[Dict[str, Any]], page: int, items_per_page: int
) -> str:
    """
    Форматирует страницу словаря
    """
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_words = words[start_idx:end_idx]

    if not page_words:
        return "📖 <b>Страница пуста</b>"

    lines = [f"📖 <b>Ваш словарь (стр. {page + 1})</b>\n"]
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    for i, word in enumerate(page_words, start_idx + 1):
        word_text = word.get("word", "") or word.get("reading", "Неизвестно")
        status = word.get("status", "new")

        # Иконка статуса
        status_icons = {"new": "🆕", "learning": "📚", "known": "✅", "skipped": "⏭️"}
        status_icon = status_icons.get(status, "📝")

        # Дата добавления
        added_date = word.get("added_at")
        if isinstance(added_date, datetime):
            date_str = added_date.strftime("%d.%m")
        else:
            date_str = "??.??"

        lines.append(f"{i}. {status_icon} <b>{word_text}</b> ({date_str})")

        # Теги если есть
        tags = word.get("user_tags", [])
        if tags:
            tags_str = ", ".join(tags[:3])  # Показываем только 3 тега
            if len(tags) > 3:
                tags_str += f" (+{len(tags) - 3})"
            lines.append(f"   🏷️ {tags_str}")

    lines.append(f"\n📊 Всего слов: {len(words)}")

    return "\n".join(lines)


@dictionary_router.callback_query(F.data.startswith("dict_page:"))
async def dict_page_callback(callback: CallbackQuery, state: FSMContext):
    """
    Переключение страниц словаря
    """
    try:
        _, page_str = callback.data.split(":", 1)
        page = int(page_str)

        # Получаем данные из состояния
        state_data = await state.get_data()
        user_words = state_data.get("user_words", [])
        items_per_page = state_data.get("items_per_page", 10)

        # Сортируем слова
        user_words_sorted = sorted(
            user_words, key=lambda x: x.get("added_at", datetime.min), reverse=True
        )

        # Проверяем границы
        total_pages = (len(user_words_sorted) + items_per_page - 1) // items_per_page
        if page < 0 or page >= total_pages:
            await callback.answer("Нет такой страницы")
            return

        # Обновляем состояние
        await state.update_data(dict_current_page=page)

        # Формируем текст
        response_text = format_dictionary_page(user_words_sorted, page, items_per_page)

        # Создаем клавиатуру
        keyboard = keyboards.get_user_dictionary_keyboard(
            words=user_words_sorted,
            current_page=page,
            total_pages=total_pages,
            items_per_page=items_per_page,
        )

        await callback.message.edit_text(
            response_text, reply_markup=keyboard, parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Dict page error: {str(e)}")
        await callback.answer("Ошибка при переключении страницы")


@dictionary_router.callback_query(F.data.startswith("view_user_word:"))
async def view_user_word_callback(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Просмотр слова из словаря пользователя
    """
    try:
        _, user_word_id_str = callback.data.split(":", 1)
        user_word_id = int(user_word_id_str)

        # Получаем слово
        user_word = await UserWordCRUD.get_by_id(session, user_word_id)
        if not user_word:
            await callback.answer("Слово не найдено")
            return

        # Получаем детали слова
        dict_word = await WordCRUD.get_by_id(session, user_word.word_id)
        if not dict_word:
            await callback.answer("Информация о слове не найдена")
            return

        # Форматируем текст
        lines = [
            "📖 <b>Слово из вашего словаря</b>\n",
            "━━━━━━━━━━━━━━━━━━━━",
            f"<b>{dict_word.word}</b> ({dict_word.reading})",
            f"<i>{dict_word.pos or 'Не указано'}</i>\n",
            f"<b>Перевод:</b> {dict_word.meaning}",
            f"<b>Статус:</b> {user_word.status}",
            f"<b>Добавлено:</b> {user_word.added_at.strftime('%d.%m.%Y %H:%M')}",
        ]

        if user_word.last_reviewed:
            lines.append(
                f"<b>Последний просмотр:</b> {user_word.last_reviewed.strftime('%d.%m.%Y %H:%M')}"
            )

        if user_word.personal_note:
            lines.append(f"<b>Заметка:</b> {user_word.personal_note}")

        if user_word.user_tags:
            lines.append(f"<b>Теги:</b> {', '.join(user_word.user_tags)}")

        # Получаем текущую страницу из состояния
        state_data = await state.get_data()
        current_page = state_data.get("dict_current_page", 0)

        # Создаем клавиатуру
        keyboard = keyboards.get_user_word_detail_keyboard(
            user_word_id=user_word.id, current_page=current_page
        )

        await callback.message.edit_text(
            "\n".join(lines), reply_markup=keyboard, parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"View user word error: {str(e)}")
        await callback.answer("Ошибка при загрузке слова")


@dictionary_router.callback_query(F.data.startswith("confirm_remove:"))
async def confirm_remove_callback(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Подтверждение удаления слова
    """
    try:
        _, user_word_id_str = callback.data.split(":", 1)
        user_word_id = int(user_word_id_str)

        # Получаем слово для отображения
        user_word = await UserWordCRUD.get_by_id(session, user_word_id)
        if not user_word:
            await callback.answer("Слово не найдено")
            return

        dict_word = await WordCRUD.get_by_id(session, user_word.word_id)
        word_text = dict_word.word if dict_word else "Неизвестное слово"

        # Создаем клавиатуру подтверждения
        keyboard = keyboards.get_confirmation_keyboard(
            action="remove_word",
            item_id=user_word_id,
            confirm_text="🗑 Да, удалить",
            cancel_text="❌ Нет, оставить",
        )

        await callback.message.edit_text(
            f"⚠️ <b>Подтверждение удаления</b>\n\n"
            f"Вы действительно хотите удалить слово:\n"
            f"<b>{word_text}</b>\n\n"
            f"Это действие нельзя отменить!",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Confirm remove error: {str(e)}")
        await callback.answer("Ошибка")


@dictionary_router.callback_query(F.data.startswith("confirm_remove_word:"))
async def process_remove_word(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Удаление слова из словаря
    """
    try:
        _, user_word_id_str = callback.data.split(":", 1)
        user_word_id = int(user_word_id_str)

        # Получаем слово перед удалением
        user_word = await UserWordCRUD.get_by_id(session, user_word_id)
        if not user_word:
            await callback.answer("Слово уже удалено")
            return

        dict_word = await WordCRUD.get_by_id(session, user_word.word_id)
        word_text = dict_word.word if dict_word else "Неизвестное слово"

        # Удаляем слово
        success = await UserWordCRUD.remove_word(session, user_word_id)

        if success:
            await callback.message.edit_text(
                f"✅ <b>Слово удалено</b>\n\n"
                f"Слово <b>{word_text}</b> удалено из вашего словаря.",
                parse_mode="HTML",
            )

            # Возвращаемся к списку слов
            await cmd_dictionary(callback.message, session, state)
        else:
            await callback.message.edit_text(
                "❌ Не удалось удалить слово", parse_mode="HTML"
            )

        await callback.answer()

    except Exception as e:
        logger.error(f"Remove word error: {str(e)}")
        await callback.answer("Ошибка при удалении")


@dictionary_router.callback_query(F.data.startswith("cancel_remove_word:"))
async def cancel_remove_word(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Отмена удаления слова
    """
    try:
        # Возвращаемся к просмотру слова
        _, user_word_id_str = callback.data.split(":", 1)
        int(user_word_id_str)

        # Получаем состояние для текущей страницы
        state_data = await state.get_data()
        state_data.get("dict_current_page", 0)

        # Возвращаемся к просмотру слова
        await view_user_word_callback(callback, session, state)

        await callback.answer("Удаление отменено")

    except Exception as e:
        logger.error(f"Cancel remove error: {str(e)}")
        await callback.answer("Ошибка")


@dictionary_router.callback_query(F.data.startswith("edit_user_tags:"))
async def edit_user_tags_callback(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Редактирование тегов слова
    """
    try:
        _, user_word_id_str = callback.data.split(":", 1)
        user_word_id = int(user_word_id_str)

        # Получаем слово
        user_word = await UserWordCRUD.get_by_id(session, user_word_id)
        if not user_word:
            await callback.answer("Слово не найдено")
            return

        dict_word = await WordCRUD.get_by_id(session, user_word.word_id)
        word_text = dict_word.word if dict_word else "Неизвестное слово"

        # Получаем текущие теги
        current_tags = user_word.user_tags or []

        # Сохраняем ID слова в состоянии
        await state.update_data(
            editing_user_word_id=user_word_id, current_tags=current_tags
        )

        # Создаем клавиатуру для редактирования тегов
        keyboard = keyboards.get_edit_tags_keyboard(
            user_word_id=user_word_id, current_tags=current_tags
        )

        await callback.message.edit_text(
            f"🏷️ <b>Редактирование тегов</b>\n\n"
            f"Слово: <b>{word_text}</b>\n"
            f"Текущие теги: {', '.join(current_tags) if current_tags else 'нет'}\n\n"
            f"Вы можете:\n"
            f"• Нажать на тег чтобы удалить его\n"
            f"• Нажать 'Добавить тег' для ввода нового\n"
            f"• Нажать 'Готово' для сохранения",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Edit tags error: {str(e)}")
        await callback.answer("Ошибка")


@dictionary_router.callback_query(F.data.startswith("remove_tag:"))
async def remove_tag_callback(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Удаление тега
    """
    try:
        _, user_word_id_str, tag_to_remove = callback.data.split(":", 2)
        user_word_id = int(user_word_id_str)

        # Получаем текущие теги из состояния
        state_data = await state.get_data()
        current_tags = state_data.get("current_tags", [])

        # Удаляем тег
        if tag_to_remove in current_tags:
            current_tags.remove(tag_to_remove)

            # Обновляем состояние
            await state.update_data(current_tags=current_tags)

            # Обновляем клавиатуру
            keyboard = keyboards.get_edit_tags_keyboard(
                user_word_id=user_word_id, current_tags=current_tags
            )

            await callback.message.edit_reply_markup(reply_markup=keyboard)

            await callback.answer(f"Тег '{tag_to_remove}' удален")
        else:
            await callback.answer("Тег не найден")

    except Exception as e:
        logger.error(f"Remove tag error: {str(e)}")
        await callback.answer("Ошибка")


@dictionary_router.callback_query(F.data.startswith("add_tag:"))
async def add_tag_callback(callback: CallbackQuery, state: FSMContext):
    """
    Запрос на добавление нового тега
    """
    try:
        _, user_word_id_str = callback.data.split(":", 1)
        user_word_id = int(user_word_id_str)

        # Сохраняем ID слова в состоянии
        await state.update_data(
            adding_tag_to_word=user_word_id, adding_tag_step="waiting_for_tag"
        )

        await callback.message.edit_text(
            "🏷️ <b>Введите новый тег:</b>\n\n"
            "Можно ввести несколько тегов через запятую\n"
            "<i>Пример: еда, суши, японская кухня</i>",
            parse_mode="HTML",
        )

        await state.set_state(DictionaryStates.waiting_for_tags)
        await callback.answer()

    except Exception as e:
        logger.error(f"Add tag callback error: {str(e)}")
        await callback.answer("Ошибка")


@dictionary_router.message(DictionaryStates.waiting_for_tags)
async def process_new_tags(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработка новых тегов
    """
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        user_word_id = state_data.get("adding_tag_to_word")
        current_tags = state_data.get("current_tags", [])

        if not user_word_id:
            await message.answer("❌ Ошибка: слово не найдено")
            await state.clear()
            return

        # Получаем слово
        user_word = await UserWordCRUD.get_by_id(session, user_word_id)
        if not user_word:
            await message.answer("❌ Слово не найдено")
            await state.clear()
            return

        # Обрабатываем введенные теги
        new_tags_text = message.text.strip()
        if not new_tags_text:
            await message.answer("❌ Пожалуйста, введите теги")
            return

        # Разделяем теги по запятой
        new_tags = [tag.strip() for tag in new_tags_text.split(",") if tag.strip()]

        if not new_tags:
            await message.answer("❌ Не найдено валидных тегов")
            return

        # Объединяем с текущими тегами (убираем дубликаты)
        all_tags = list(set(current_tags + new_tags))

        # Обновляем теги в базе данных
        user_word.user_tags = all_tags
        await session.commit()

        # Обновляем состояние
        await state.update_data(current_tags=all_tags)

        # Получаем слово для отображения
        dict_word = await WordCRUD.get_by_id(session, user_word.word_id)
        word_text = dict_word.word if dict_word else "Неизвестное слово"

        # Создаем обновленную клавиатуру
        keyboard = keyboards.get_edit_tags_keyboard(
            user_word_id=user_word_id, current_tags=all_tags
        )

        await message.answer(
            f"✅ <b>Теги обновлены</b>\n\n"
            f"Слово: <b>{word_text}</b>\n"
            f"Теги: {', '.join(all_tags) if all_tags else 'нет'}",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f"Process tags error: {str(e)}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}")
        await state.clear()


@dictionary_router.callback_query(F.data.startswith("finish_tags:"))
async def finish_tags_callback(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Завершение редактирования тегов
    """
    try:
        _, user_word_id_str = callback.data.split(":", 1)
        user_word_id = int(user_word_id_str)

        # Получаем текущие теги из состояния
        state_data = await state.get_data()
        current_tags = state_data.get("current_tags", [])

        # Обновляем теги в базе данных
        user_word = await UserWordCRUD.get_by_id(session, user_word_id)
        if user_word:
            user_word.user_tags = current_tags
            await session.commit()

        # Возвращаемся к просмотру слова
        await view_user_word_callback(callback, session, state)

        await callback.answer("✅ Теги сохранены")

    except Exception as e:
        logger.error(f"Finish tags error: {str(e)}")
        await callback.answer("Ошибка при сохранении тегов")


@dictionary_router.callback_query(F.data.startswith("back_to_dict:"))
async def back_to_dict_callback(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Возврат к словарю с сохранением страницы
    """
    try:
        _, page_str = callback.data.split(":", 1)
        page = int(page_str)

        # Обновляем текущую страницу в состоянии
        await state.update_data(dict_current_page=page)

        # Получаем слова пользователя
        user = await UserCRUD.get_by_telegram_id(session, callback.from_user.id)
        user_words = await UserWordCRUD.get_user_words_with_details(session, user.id)

        # Сохраняем слова в состоянии
        await state.update_data(user_words=user_words)

        # Сортируем слова
        user_words_sorted = sorted(
            user_words, key=lambda x: x.get("added_at", datetime.min), reverse=True
        )

        # Формируем текст
        items_per_page = 10
        response_text = format_dictionary_page(user_words_sorted, page, items_per_page)

        # Создаем клавиатуру
        total_pages = (len(user_words_sorted) + items_per_page - 1) // items_per_page
        keyboard = keyboards.get_user_dictionary_keyboard(
            words=user_words_sorted,
            current_page=page,
            total_pages=total_pages,
            items_per_page=items_per_page,
        )

        await callback.message.edit_text(
            response_text, reply_markup=keyboard, parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Back to dict error: {str(e)}")
        await callback.answer("Ошибка")


@dictionary_router.callback_query(F.data == "exit_dictionary")
async def exit_dictionary_callback(callback: CallbackQuery, state: FSMContext):
    """
    Выход из режима просмотра словаря
    """
    await callback.message.edit_text(
        "📖 <b>Режим словаря закрыт</b>\n\n"
        "Используйте /dictionary чтобы снова открыть словарь",
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()


# Команда /remove_word (удаление слова по ID)
@dictionary_router.message(Command("remove_word"))
async def cmd_remove_word(message: Message, state: FSMContext):
    """
    Удаление слова по ID
    """
    args = message.text.split()

    if len(args) < 2:
        await message.answer(
            "🗑 <b>Удаление слова</b>\n\n"
            "Использование: /remove_word [ID]\n\n"
            "Чтобы узнать ID слова:\n"
            "1. Откройте словарь /dictionary\n"
            "2. Найдите нужное слово\n"
            "3. ID отображается в деталях слова\n\n"
            "<i>Пример: /remove_word 42</i>",
            parse_mode="HTML",
        )
        return

    try:
        word_id = int(args[1])
        await state.update_data(remove_word_id=word_id)

        await message.answer(
            f"⚠️ <b>Подтверждение удаления</b>\n\n"
            f"Вы хотите удалить слово с ID: {word_id}\n\n"
            f"Введите 'да' для подтверждения или 'нет' для отмены:",
            parse_mode="HTML",
        )

    except ValueError:
        await message.answer("❌ ID должен быть числом")


@dictionary_router.message(Command("add_word"))
async def cmd_add_word(message: Message, state: FSMContext):
    """
    Добавление слова вручную
    """
    await message.answer(
        "➕ <b>Добавление слова вручную</b>\n\n"
        "Введите слово на японском (кандзи, хирагана или катакана):\n\n"
        "<i>Пример: 寿司, すし, スシ</i>",
        parse_mode="HTML",
    )
    await state.set_state(DictionaryStates.waiting_for_manual_word)


@dictionary_router.message(DictionaryStates.waiting_for_manual_word)
async def process_manual_word(message: Message, state: FSMContext):
    """
    Обработка японского слова для ручного добавления
    """
    word = message.text.strip()

    if not word:
        await message.answer("❌ Пожалуйста, введите слово")
        return

    # Проверяем, что это японский текст
    if not jisho_service.is_japanese_text(word):
        await message.answer(
            "❌ Это не похоже на японский текст\n\n"
            "Пожалуйста, введите слово на японском:\n"
            "• Кандзи (漢字)\n"
            "• Хирагана (ひらがな)\n"
            "• Катакана (カタカナ)"
        )
        return

    await state.update_data(manual_word=word)

    await message.answer(
        "📝 <b>Введите чтение слова (фуригану):</b>\n\n"
        "<i>Пример: для слова '寿司' введите 'すし'</i>",
        parse_mode="HTML",
    )
    await state.set_state(DictionaryStates.waiting_for_manual_reading)


@dictionary_router.message(DictionaryStates.waiting_for_manual_reading)
async def process_manual_reading(message: Message, state: FSMContext):
    """
    Обработка чтения слова
    """
    reading = message.text.strip()

    if not reading:
        await message.answer("❌ Пожалуйста, введите чтение")
        return

    await state.update_data(manual_reading=reading)

    await message.answer(
        "🌐 <b>Введите перевод слова на английском или русском:</b>\n\n"
        "<i>Пример: sushi, суши</i>",
        parse_mode="HTML",
    )
    await state.set_state(DictionaryStates.waiting_for_manual_meaning)


@dictionary_router.message(DictionaryStates.waiting_for_manual_meaning)
async def process_manual_meaning(
    message: Message, state: FSMContext, session: AsyncSession
):
    """
    Обработка перевода и сохранение слова
    """
    meaning = message.text.strip()

    if not meaning:
        await message.answer("❌ Пожалуйста, введите перевод")
        return

    # Получаем данные из состояния
    state_data = await state.get_data()
    word = state_data.get("manual_word")
    reading = state_data.get("manual_reading")

    if not word or not reading:
        await message.answer("❌ Ошибка: данные не найдены")
        await state.clear()
        return

    # Получаем пользователя
    user = await UserCRUD.get_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return

    try:
        # Создаем запись в словаре
        dict_word = DictionaryWord(
            word=word,
            reading=reading,
            meaning=meaning,
            meanings=[meaning],
            jisho_slug=f"manual_{user.id}_{datetime.utcnow().timestamp()}",
            is_common=False,
        )

        session.add(dict_word)
        await session.commit()
        await session.refresh(dict_word)

        # Добавляем слово пользователю
        user_word = await UserWordCRUD.add_word_to_user(
            session, user.id, dict_word.id, status="new"
        )

        await message.answer(
            f"✅ <b>Слово успешно добавлено!</b>\n\n"
            f"<b>Слово:</b> {word}\n"
            f"<b>Чтение:</b> {reading}\n"
            f"<b>Перевод:</b> {meaning}\n\n"
            f"ID слова: {user_word.id}\n"
            f"Вы можете посмотреть его в словаре: /dictionary",
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f"Manual add word error: {str(e)}")
        await message.answer(f"❌ Ошибка при добавлении слова: {str(e)[:100]}")

    await state.clear()
