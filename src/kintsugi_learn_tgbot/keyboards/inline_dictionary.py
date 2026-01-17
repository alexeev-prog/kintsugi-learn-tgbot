from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict, Any, Optional


class DictionaryKeyboards:
    """Клавиатуры для работы со словарем"""

    @staticmethod
    def get_search_results_keyboard(
        words: List[Dict[str, Any]],
        current_page: int = 0,
        total_pages: int = 1,
        query: str = "",
    ) -> InlineKeyboardMarkup:
        """
        Клавиатура для результатов поиска

        Args:
            words: Список найденных слов
            current_page: Текущая страница
            total_pages: Всего страниц
            query: Поисковый запрос
        """
        builder = InlineKeyboardBuilder()

        # Кнопки для каждого слова (первые 5)
        for i, word_data in enumerate(words[:5], 1):
            # Используем первое японское написание
            japanese = word_data["japanese"][0] if word_data["japanese"] else {}
            word = japanese.get("word", "") or japanese.get("reading", "")

            if len(word) > 15:
                word = word[:15] + "..."

            builder.button(
                text=f"{i}. {word}",
                callback_data=f"word_detail:{word_data.get('slug', '')}",
            )

        # Переносим на новую строку
        builder.adjust(1)

        # Навигация по страницам
        if total_pages > 1:
            nav_buttons = []

            if current_page > 0:
                nav_buttons.append(
                    InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data=f"search_page:{query}:{current_page - 1}",
                    )
                )

            nav_buttons.append(
                InlineKeyboardButton(
                    text=f"{current_page + 1}/{total_pages}", callback_data="no_action"
                )
            )

            if current_page < total_pages - 1:
                nav_buttons.append(
                    InlineKeyboardButton(
                        text="Вперед ▶️",
                        callback_data=f"search_page:{query}:{current_page + 1}",
                    )
                )

            builder.row(*nav_buttons)

        # Кнопка нового поиска
        builder.row(
            InlineKeyboardButton(text="🔍 Новый поиск", callback_data="new_search")
        )

        return builder.as_markup()

    @staticmethod
    def get_word_detail_keyboard(
        word_slug: str,
        is_in_user_dict: bool = False,
        user_word_id: Optional[int] = None,
    ) -> InlineKeyboardMarkup:
        """
        Клавиатура для детального просмотра слова

        Args:
            word_slug: Slug слова из Jisho
            is_in_user_dict: В словаре ли пользователя
            user_word_id: ID слова в словаре пользователя
        """
        builder = InlineKeyboardBuilder()

        if is_in_user_dict and user_word_id:
            # Если слово уже в словаре
            builder.button(
                text="🗑 Удалить из словаря",
                callback_data=f"remove_from_dict:{user_word_id}",
            )
            builder.button(
                text="🏷 Изменить теги", callback_data=f"edit_tags:{user_word_id}"
            )
        else:
            # Если слова нет в словаре
            builder.button(
                text="➕ Добавить в словарь", callback_data=f"add_to_dict:{word_slug}"
            )

        builder.button(
            text="🔍 Еще варианты", callback_data=f"more_variants:{word_slug}"
        )

        builder.button(text="📋 В список", callback_data="back_to_list")

        builder.adjust(1)  # Все кнопки в столбик

        return builder.as_markup()

    @staticmethod
    def get_user_dictionary_keyboard(
        words: List[Dict[str, Any]],
        current_page: int = 0,
        total_pages: int = 1,
        items_per_page: int = 10,
    ) -> InlineKeyboardMarkup:
        """
        Клавиатура для просмотра словаря пользователя

        Args:
            words: Список слов пользователя
            current_page: Текущая страница
            total_pages: Всего страниц
            items_per_page: Слов на странице
        """
        builder = InlineKeyboardBuilder()

        # Кнопки для слов на текущей странице
        start_idx = current_page * items_per_page
        end_idx = start_idx + items_per_page
        page_words = words[start_idx:end_idx]

        for i, word in enumerate(page_words, start_idx + 1):
            word_text = word.get("word", "") or word.get("reading", "")
            if len(word_text) > 20:
                word_text = word_text[:20] + "..."

            status_icon = (
                "🟢"
                if word.get("status") == "known"
                else "🟡"
                if word.get("status") == "learning"
                else "🔵"
            )

            builder.button(
                text=f"{i}. {status_icon} {word_text}",
                callback_data=f"view_user_word:{word.get('id')}",
            )

        builder.adjust(1)  # Все кнопки в столбик

        # Навигация
        nav_buttons = []

        if current_page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="◀️ Назад", callback_data=f"dict_page:{current_page - 1}"
                )
            )

        # Информация о странице
        nav_buttons.append(
            InlineKeyboardButton(
                text=f"📄 {current_page + 1}/{total_pages}", callback_data="no_action"
            )
        )

        if current_page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Вперед ▶️", callback_data=f"dict_page:{current_page + 1}"
                )
            )

        if nav_buttons:
            builder.row(*nav_buttons)

        # Действия
        action_buttons = [
            InlineKeyboardButton(text="🔍 Поиск по ID", callback_data="search_by_id"),
            InlineKeyboardButton(
                text="🏷 Управление тегами", callback_data="manage_tags"
            ),
            InlineKeyboardButton(text="❌ Выйти", callback_data="exit_dictionary"),
        ]

        builder.row(*action_buttons[:2])
        builder.row(action_buttons[2])

        return builder.as_markup()

    @staticmethod
    def get_user_word_detail_keyboard(
        user_word_id: int, current_page: int = 0
    ) -> InlineKeyboardMarkup:
        """
        Клавиатура для детального просмотра слова пользователя
        """
        builder = InlineKeyboardBuilder()

        # Основные действия
        builder.button(
            text="🗑 Удалить слово", callback_data=f"confirm_remove:{user_word_id}"
        )

        builder.button(
            text="🏷 Изменить теги", callback_data=f"edit_user_tags:{user_word_id}"
        )

        # Навигация
        builder.button(text="◀️ Назад", callback_data=f"back_to_dict:{current_page}")

        builder.button(text="📋 В словарь", callback_data="back_to_dict_main")

        builder.adjust(1)  # Все кнопки в столбик

        return builder.as_markup()

    @staticmethod
    def get_edit_tags_keyboard(
        user_word_id: int, current_tags: List[str] = None
    ) -> InlineKeyboardMarkup:
        """
        Клавиатура для редактирования тегов
        """
        builder = InlineKeyboardBuilder()

        if current_tags:
            # Кнопки для удаления тегов
            for tag in current_tags[:5]:  # Ограничиваем 5 тегами
                builder.button(
                    text=f"❌ {tag}", callback_data=f"remove_tag:{user_word_id}:{tag}"
                )

        # Кнопка добавления тега
        builder.button(text="➕ Добавить тег", callback_data=f"add_tag:{user_word_id}")

        # Навигация
        builder.button(text="✅ Готово", callback_data=f"finish_tags:{user_word_id}")

        builder.button(text="❌ Отмена", callback_data=f"cancel_tags:{user_word_id}")

        builder.adjust(1)

        return builder.as_markup()

    @staticmethod
    def get_confirmation_keyboard(
        action: str,
        item_id: int,
        confirm_text: str = "✅ Да",
        cancel_text: str = "❌ Нет",
    ) -> InlineKeyboardMarkup:
        """
        Клавиатура подтверждения действия
        """
        builder = InlineKeyboardBuilder()

        builder.button(text=confirm_text, callback_data=f"confirm_{action}:{item_id}")

        builder.button(text=cancel_text, callback_data=f"cancel_{action}:{item_id}")

        builder.adjust(2)

        return builder.as_markup()

    @staticmethod
    def get_empty_keyboard() -> InlineKeyboardMarkup:
        """Пустая клавиатура (для удаления кнопок)"""
        return InlineKeyboardMarkup(inline_keyboard=[])


# Глобальный экземпляр
keyboards = DictionaryKeyboards()
