#!/usr/bin/env python3
"""
Еженедельный/ежедневный дайджест новостей по теме Product AI / AI PM.
Собирает свежие материалы через Claude API (с web_search),
затем отправляет результат в Telegram.

Переменные окружения (задаются как GitHub Secrets, см. README):
  ANTHROPIC_API_KEY  - ключ Anthropic API
  TELEGRAM_BOT_TOKEN - токен бота из @BotFather
  TELEGRAM_CHAT_ID   - ваш chat_id
"""

import os
import sys
import requests

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

SOURCES = [
    "Techpresso",
    "Lenny's Newsletter",
    "McKinsey AI Blog",
    "SVPG (Marty Cagan)",
    "Mind the Product",
    "Product Hunt",
    "Reforge",
    "AI PM Conference",
]

PROMPT = f"""Ты помощник, который готовит короткий дайджест новостей для продакт-менеджера,
интересующегося темой AI in Product Management (Project Product AI).

Используя веб-поиск, найди самые свежие материалы (за последние 7 дней, если возможно)
по теме AI-продуктов и продуктового менеджмента из следующих источников:
{', '.join(SOURCES)}.

Если по какому-то источнику ничего свежего не нашлось — просто пропусти его, не выдумывай.

Формат ответа (для Telegram, используй только простое форматирование *bold* и переносы строк,
БЕЗ markdown-заголовков ###):

📰 *Дайджест Product AI — [дата]*

По каждому релевантному материалу:
*Источник*: короткая суть (1-2 предложения), без ссылок на источники в тексте, без длинных цитат.

Если у тебя есть прямая ссылка на материал из результатов поиска - добавь её отдельной строкой.

Общий объём - не больше 3000 символов (лимит Telegram-сообщения)."""


def get_digest_text() -> str:
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": PROMPT}],
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()

    # Собираем весь текст из всех text-блоков (может быть несколько, вперемешку с tool_use)
    text_parts = [
        block["text"] for block in data.get("content", []) if block.get("type") == "text"
    ]
    text = "\n".join(text_parts).strip()

    if not text:
        raise RuntimeError(f"Пустой ответ от Claude API: {data}")

    return text


def send_to_telegram(text: str) -> None:
    # Telegram ограничивает сообщение 4096 символами - режем на части, если нужно
    max_len = 4000
    chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)] or [text]

    for chunk in chunks:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "parse_mode": "Markdown",
            },
            timeout=30,
        )
        if not resp.ok:
            # Если Markdown сломал парсинг (частая проблема) - шлём как обычный текст
            resp2 = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk},
                timeout=30,
            )
            resp2.raise_for_status()


def main() -> None:
    try:
        digest = get_digest_text()
        send_to_telegram(digest)
        print("Дайджест успешно отправлен.")
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        # Уведомляем в телеграм об ошибке, чтобы не пропустить сбой молча
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": f"⚠️ Не удалось собрать дайджест: {e}",
                },
                timeout=30,
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
