#!/usr/bin/env python3
"""
Ежедневный дайджест новостей по теме Product AI / AI PM.
ПОЛНОСТЬЮ БЕСПЛАТНО: только RSS-ленты, без вызовов платных API.

Источники: Mind the Product, Lenny's Newsletter, SVPG (Marty Cagan),
Product Hunt (категория AI), Techpresso.

Переменные окружения (GitHub Secrets):
  TELEGRAM_BOT_TOKEN - токен бота из @BotFather
  TELEGRAM_CHAT_ID   - ваш chat_id
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import feedparser
import requests

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Источники с публичным RSS
FEEDS = [
    {"name": "Mind the Product", "url": "https://www.mindtheproduct.com/feed/"},
    {"name": "Lenny's Newsletter", "url": "https://www.lennysnewsletter.com/feed"},
    {"name": "SVPG (Marty Cagan)", "url": "https://www.svpg.com/feed/"},
    {"name": "Product Hunt (AI)", "url": "https://www.producthunt.com/feed?category=artificial-intelligence"},
    {"name": "Techpresso", "url": "https://dupple.com/techpresso-archives/rss.xml"},
]

# Ищем материалы за последние N дней (на случай если источник обновляется реже раза в сутки)
LOOKBACK_DAYS = 2

# Ключевые слова для дополнительной фильтрации (актуально в основном для Product Hunt,
# остальные источники и так по теме продукта/AI). Пусто = без доп. фильтрации.
KEYWORDS = None  # например: ["ai", "gpt", "llm", "agent", "product"]


def entry_datetime(entry):
    for field in ("published_parsed", "updated_parsed"):
        value = getattr(entry, field, None)
        if value:
            return datetime(*value[:6], tzinfo=timezone.utc)
    return None


def matches_keywords(entry) -> bool:
    if not KEYWORDS:
        return True
    text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
    return any(kw.lower() in text for kw in KEYWORDS)


def collect_digest() -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    lines = [f"📰 *Дайджест Product AI — {datetime.now().strftime('%d.%m.%Y')}*\n"]
    any_content = False

    for feed in FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
        except Exception as e:
            lines.append(f"\n*{feed['name']}*: ошибка загрузки ({e})")
            continue

        fresh_entries = []
        for entry in parsed.entries:
            dt = entry_datetime(entry)
            # Если дата не определена - берём материал на всякий случай (лучше показать лишнее,
            # чем пропустить свежую новость из-за отсутствия даты в RSS)
            if dt is not None and dt < cutoff:
                continue
            if not matches_keywords(entry):
                continue
            fresh_entries.append(entry)

        if not fresh_entries:
            continue

        any_content = True
        lines.append(f"\n*{feed['name']}*")
        for entry in fresh_entries[:5]:  # не более 5 материалов с одного источника
            title = entry.get("title", "Без названия").strip()
            link = entry.get("link", "")
            lines.append(f"• {title}\n  {link}")

    if not any_content:
        lines.append("\nЗа последние дни новых материалов по отслеживаемым источникам не найдено.")

    text = "\n".join(lines)

    # Не забываем про источники без RSS - напоминание с прямыми ссылками
    lines_manual = [
        "\n\n_Эти источники без RSS - проверяйте вручную:_",
        "• Reforge Blog: https://www.reforge.com/blog",
        "• McKinsey AI Blog: https://www.mckinsey.com/capabilities/quantumblack/our-insights",
        "• AI PM Conference: https://aipmconference.com",
    ]
    text += "\n".join(lines_manual)

    return text


def send_to_telegram(text: str) -> None:
    max_len = 4000
    chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)] or [text]

    for chunk in chunks:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if not resp.ok:
            # Если Markdown сломал парсинг - шлём как обычный текст
            resp2 = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "disable_web_page_preview": True},
                timeout=30,
            )
            resp2.raise_for_status()


def main() -> None:
    try:
        digest = collect_digest()
        send_to_telegram(digest)
        print("Дайджест успешно отправлен.")
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": f"⚠️ Не удалось собрать дайджест: {e}"},
                timeout=30,
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
