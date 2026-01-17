import aiohttp
import ssl
from typing import Dict, Any, Optional, List
from urllib.parse import quote
from loguru import logger
import certifi
from datetime import datetime, timedelta


class JishoService:
    BASE_URL = "https://jisho.org/api/v1/search/words"

    def __init__(self, cache_ttl_hours: int = 24):
        self.session = None
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.cache = {}
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self.session

    def _get_cache_key(self, keyword: str) -> str:
        return f"jisho:{keyword.lower().strip()}"

    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        cached_at = cache_entry.get("cached_at")
        if not cached_at:
            return False
        return datetime.fromisoformat(cached_at) + self.cache_ttl > datetime.utcnow()

    async def search_word(
        self, keyword: str, use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        cache_key = self._get_cache_key(keyword)

        if use_cache and cache_key in self.cache:
            if self._is_cache_valid(self.cache[cache_key]):
                logger.debug(f"Cache hit for: {keyword}")
                return self.cache[cache_key]["data"]

        try:
            session = await self.get_session()
            encoded_keyword = quote(keyword)
            url = f"{self.BASE_URL}?keyword={encoded_keyword}"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()

                    if data.get("data"):
                        cache_entry = {
                            "data": data,
                            "cached_at": datetime.utcnow().isoformat(),
                            "keyword": keyword,
                        }
                        self.cache[cache_key] = cache_entry
                        logger.info(
                            f"Found word: {data['data'][0].get('slug', 'unknown')}"
                        )
                        return data
                    else:
                        logger.warning(f"No results for: {keyword}")
                        return None
                else:
                    logger.error(f"Jisho API error: {response.status}")
                    return None

        except Exception as e:
            logger.error(f"Error searching word '{keyword}': {str(e)}")
            return None

    async def search_suggestions(self, prefix: str, limit: int = 5) -> List[str]:
        if len(prefix) < 2:
            return []

        try:
            session = await self.get_session()
            encoded_prefix = quote(prefix)
            url = f"{self.BASE_URL}?keyword={encoded_prefix}"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    suggestions = []

                    for item in data.get("data", [])[:limit]:
                        japanese = item.get("japanese", [{}])[0]
                        word = japanese.get("word") or japanese.get("reading", "")
                        if word:
                            suggestions.append(word)

                    return list(set(suggestions))
                return []
        except Exception:
            return []

    def parse_jisho_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not data or "data" not in data:
            return []

        parsed_words = []

        for item in data["data"]:
            slug = item.get("slug", "")
            is_common = item.get("is_common", False)
            jlpt = item.get("jlpt", [])

            japanese_forms = []
            for jp in item.get("japanese", []):
                word = jp.get("word", "")
                reading = jp.get("reading", "")
                japanese_forms.append(
                    {
                        "word": word,
                        "reading": reading,
                        "has_kanji": bool(word)
                        and any("\u4e00" <= char <= "\u9fff" for char in word),
                    }
                )

            senses = []
            for sense in item.get("senses", []):
                english_defs = sense.get("english_definitions", [])
                parts_of_speech = sense.get("parts_of_speech", [])
                tags = sense.get("tags", [])
                links = sense.get("links", [])

                senses.append(
                    {
                        "english_definitions": english_defs,
                        "parts_of_speech": parts_of_speech,
                        "tags": tags,
                        "links": links,
                        "example_sentences": sense.get("example_sentences", [])[:2],
                    }
                )

            all_tags = list(
                set(
                    item.get("tags", [])
                    + [tag for sense in senses for tag in sense.get("tags", [])]
                )
            )

            parsed_words.append(
                {
                    "slug": slug,
                    "is_common": is_common,
                    "jlpt": jlpt,
                    "japanese": japanese_forms,
                    "senses": senses,
                    "tags": all_tags,
                    "has_kanji": any(
                        form.get("has_kanji", False) for form in japanese_forms
                    ),
                    "has_kana_only": any(
                        form.get("word") and not form.get("has_kanji")
                        for form in japanese_forms
                    ),
                    "attribution": item.get("attribution", {}),
                }
            )

        return parsed_words

    def format_word_for_display(
        self, word_data: Dict[str, Any], show_details: bool = False
    ) -> str:
        if not word_data:
            return "❌ Слово не найдено"

        main_japanese = word_data["japanese"][0] if word_data["japanese"] else {}
        word = main_japanese.get("word", "")
        reading = main_japanese.get("reading", "")

        main_sense = word_data["senses"][0] if word_data["senses"] else {}
        english_defs = main_sense.get("english_definitions", [])
        parts_of_speech = main_sense.get("parts_of_speech", [])

        lines = []

        if word and reading:
            if word == reading:
                lines.append(f"<b>📖 {word}</b>")
            else:
                lines.append(f"<b>📖 {word}</b> ({reading})")
        elif reading:
            lines.append(f"<b>📖 {reading}</b>")

        if parts_of_speech:
            lines.append(f"<i>💬 {', '.join(parts_of_speech)}</i>")

        if english_defs:
            lines.append("")
            lines.append("<b>📚 Перевод:</b>")
            for i, definition in enumerate(english_defs[:8], 1):
                lines.append(f"{i}. {definition}")

        tags = word_data.get("tags", [])
        if tags:
            lines.append("")
            lines.append(f"<b>🏷️ Теги:</b> {', '.join(tags[:10])}")

        jlpt = word_data.get("jlpt", [])
        if jlpt:
            lines.append(f"<b>📊 Уровень JLPT:</b> {', '.join(jlpt)}")

        if word_data.get("is_common"):
            lines.append("<b>⭐ Часто используемое слово</b>")

        if show_details:
            example_sentences = main_sense.get("example_sentences", [])
            if example_sentences:
                lines.append("")
                lines.append("<b>📝 Примеры использования:</b>")
                for i, example in enumerate(example_sentences[:3], 1):
                    lines.append(f"{i}. {example}")

        return "\n".join(lines)

    def is_japanese_text(self, text: str) -> bool:
        import re

        hiragana_range = "\u3040-\u309f"
        katakana_range = "\u30a0-\u30ff"
        kanji_range = "\u4e00-\u9fff"
        pattern = f"[{hiragana_range}{katakana_range}{kanji_range}]"
        return bool(re.search(pattern, text))

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


jisho_service = JishoService()
