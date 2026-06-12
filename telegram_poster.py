#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Автопостинг новых скидок в Telegram-канал.

Постит ТОЛЬКО новые предложения (которые ещё не публиковались) — хранит
историю в telegram_state.json. Так канал не засоряется повторами.

Настройка (см. README, раздел «Telegram»):
    export TG_BOT_TOKEN="123456:ABC..."
    export TG_CHANNEL="@your_channel"   # или числовой -100... id

Запуск:
    python telegram_poster.py            # реальный постинг
    python telegram_poster.py --dry-run  # показать, что было бы отправлено
    python telegram_poster.py --limit 5  # не больше 5 постов за раз
"""

from __future__ import annotations

import argparse
import json
import os
import time

try:
    import requests
except ImportError:
    requests = None

BASE = os.path.dirname(os.path.abspath(__file__))
SITE_DATA = os.path.join(BASE, "site", "data.json")
STATE_PATH = os.path.join(BASE, "telegram_state.json")

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL = os.environ.get("TG_CHANNEL", "")


def load_posted() -> set[str]:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return set(json.load(f).get("posted", []))
    return set()


def save_posted(ids: set[str]) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"posted": sorted(ids)}, f, ensure_ascii=False, indent=2)


def load_deals() -> list[dict]:
    if not os.path.exists(SITE_DATA):
        raise SystemExit("Нет site/data.json — сначала запустите: python run.py")
    with open(SITE_DATA, "r", encoding="utf-8") as f:
        return json.load(f).get("deals", [])


def esc(s: str) -> str:
    """Экранирование под HTML-разметку Telegram."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_post(d: dict) -> str:
    lines = []
    head = f"🔥 <b>{esc(d['title'])}</b>"
    if d.get("discount"):
        head += f"  <b>{esc(d['discount'])}</b>"
    lines.append(head)
    lines.append("")
    if d.get("description"):
        lines.append(esc(d["description"]))
    if d.get("new_price") is not None:
        price = f"💰 {int(d['new_price'])} ₸"
        if d.get("old_price") is not None:
            price += f" <s>{int(d['old_price'])} ₸</s>"
        lines.append(price)
    meta = f"📍 {esc(d['city'])} · 🏷 {esc(d['category'])} · 🛍 {esc(d['source'])}"
    lines.append(meta)
    if d.get("days_left") is not None and d["days_left"] >= 0:
        lines.append(f"⏳ Осталось дней: {d['days_left']}")
    lines.append("")
    lines.append(f'<a href="{esc(d["url"])}">Перейти к предложению →</a>')
    return "\n".join(lines)


def send(text: str) -> bool:
    if requests is None:
        raise SystemExit("Установите requests: pip install requests")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": CHANNEL,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "false",
    }, timeout=20)
    if resp.status_code != 200:
        print("  Ошибка Telegram:", resp.text)
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="не отправлять, только показать")
    ap.add_argument("--limit", type=int, default=10, help="макс. постов за запуск")
    args = ap.parse_args()

    if not args.dry_run and (not BOT_TOKEN or not CHANNEL):
        raise SystemExit("Задайте TG_BOT_TOKEN и TG_CHANNEL (см. README) или используйте --dry-run")

    deals = load_deals()
    posted = load_posted()
    new = [d for d in deals if d["id"] not in posted]
    # сначала самые срочные
    new.sort(key=lambda d: d.get("days_left") if d.get("days_left") is not None else 9999)
    new = new[: args.limit]

    if not new:
        print("Новых предложений для публикации нет.")
        return

    print(f"К публикации: {len(new)}")
    for d in new:
        text = format_post(d)
        if args.dry_run:
            print("-" * 40)
            print(text)
        else:
            if send(text):
                posted.add(d["id"])
                print(f"  ✓ {d['title']}")
                time.sleep(3)  # бережём лимиты Telegram (≤20 сообщений/мин в канал)

    if not args.dry_run:
        save_posted(posted)
        print("Готово. История обновлена.")


if __name__ == "__main__":
    main()
