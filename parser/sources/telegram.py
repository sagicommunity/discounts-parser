# -*- coding: utf-8 -*-
"""Реальный источник: публичные Telegram-каналы о скидках (через t.me/s/).

Главное преимущество: веб-версия канала t.me/s/<имя> отдаётся обычной
HTML-страницей. Не нужен ни Telegram-аккаунт, ни API-ключ, ни логин —
читается откуда угодно, без блокировок.

Что делает:
  1. Скачивает страницу t.me/s/<канал> (последние посты).
  2. Разбирает каждый пост: текст, дата, ссылка, id.
  3. Эвристикой вытаскивает скидку, цену, город, срок акции.
  4. Отсеивает посты, не похожие на скидку (новости, лонгриды).
  5. Категория и теги проставляются автоматически (как в остальном проекте).

Тест только этого источника:
    python -m parser.sources.telegram
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime
from typing import List, Optional

from .base import BaseSource
from ..models import Deal, CITIES

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


# Каналы для мониторинга: (username без @, человекочитаемое имя источника)
CHANNELS = [
    ("morepodeshevle", "Ещё Подешевле"),
    ("podeshevlekz", "Казахстан Подешевле"),
    ("bsaver_a", "Budget Saver"),
]

# Сколько последних постов брать с каждого канала
PER_CHANNEL = 25

# Сильные признаки настоящей скидки/акции. Пост проходит, только если есть
# хотя бы один из них (или удалось вытащить цену/скидку). Так отсеиваются
# статьи и новости («как снизить платежи по кредитам» и т.п.).
DEAL_MARKERS = [
    "скидк", "акци", "промокод", "бесплатн", "распродаж", "кешбэк", "кэшбэк",
    "подарок", "1+1", "2+1", "2=", "3=2", "sale", "%", "дарим",
    "за 1 тенге", "за 1 тг", "в подарок",
]

# Шаблон цены в тексте (для дополнительной проверки «это точно оффер»)
_PRICE_RE = re.compile(r"\d[\d\s]{1,}\s*(?:тг|₸|тенге)", re.IGNORECASE)

# Заголовки-вопросы в стиле статьи/совета (не оффер сам по себе)
_ARTICLE_RE = re.compile(
    r"^\s*(как |почему |зачем |реально ли|правда ли|сколько |стоит ли|"
    r"что делать|что выбрать|знали ли|а вы знали|где взять|где найти|лайфхак)",
    re.IGNORECASE)

# Сильные признаки конкретного оффера (оставляем пост даже если заголовок-вопрос)
_STRONG_OFFER = ["промокод", "бесплатн", "в подарок", "купон",
                 "за 1 тенге", "за 1 тг", "1+1", "2+1", "2=1"]


def _is_article(title: str, text: str) -> bool:
    """True, если пост похож на статью/совет, а не на конкретный оффер."""
    if not _ARTICLE_RE.match(title):
        return False
    low = text.lower()
    return not any(m in low for m in _STRONG_OFFER)

# Месяцы для разбора срока «до 5 июня»
_MONTHS = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "мая": 5, "май": 5, "июн": 6,
    "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}


def _extract_discount(text: str) -> Optional[str]:
    """Находит размер скидки: 50%, до 70%, 1+1, 2=1."""
    for pat in [r"1\s*\+\s*1", r"2\s*\+\s*1", r"2\s*=\s*1", r"3\s*=\s*2"]:
        if re.search(pat, text):
            return re.search(pat, text).group(0).replace(" ", "")
    m = re.search(r"(?:до\s*)?-?\s*(\d{1,2})\s*%", text)
    if m:
        return f"-{m.group(1)}%"
    return None


def _extract_prices(text: str):
    """Пытается найти (старая, новая) цену по шаблону «за X ... вместо Y»."""
    t = text.replace("\xa0", " ")
    m = re.search(r"за\s*([\d\s]{2,})\s*(?:тг|₸|тенге).{0,20}?вместо\s*([\d\s]{2,})",
                  t, re.IGNORECASE)
    if m:
        new = _to_num(m.group(1))
        old = _to_num(m.group(2))
        if new and old:
            return old, new
    # «999 тг вместо 2490 тг»
    m = re.search(r"([\d\s]{2,})\s*(?:тг|₸).{0,20}?вместо\s*([\d\s]{2,})", t, re.IGNORECASE)
    if m:
        new = _to_num(m.group(1)); old = _to_num(m.group(2))
        if new and old:
            return old, new
    return None, None


def _to_num(s: str) -> Optional[float]:
    digits = re.sub(r"[^\d]", "", s or "")
    return float(digits) if digits else None


def _extract_city(text: str) -> str:
    low = text.lower()
    for city in CITIES:
        if city == "Вся страна":
            continue
        if city.lower() in low:
            return city
    # частые алиасы
    if "нур-султан" in low or "нурсултан" in low:
        return "Астана"
    return "Вся страна"


def _extract_ends_at(text: str, posted: date) -> Optional[str]:
    """Срок акции: «до 5 июня», «только сегодня», «до 31.05»."""
    low = text.lower()
    if "только сегодня" in low or "сегодня последн" in low:
        return posted.isoformat()
    # до 5 июня
    m = re.search(r"до\s+(\d{1,2})\s+([а-я]{3,})", low)
    if m:
        day = int(m.group(1))
        mon = _MONTHS.get(m.group(2)[:3])
        if mon and 1 <= day <= 31:
            year = posted.year + (1 if mon < posted.month - 1 else 0)
            try:
                return date(year, mon, day).isoformat()
            except ValueError:
                pass
    # до 31.05 / до 31.05.2026
    m = re.search(r"до\s+(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?", low)
    if m:
        day, mon = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else posted.year
        if year < 100:
            year += 2000
        try:
            return date(year, mon, day).isoformat()
        except ValueError:
            pass
    return None


def _make_title(text: str) -> str:
    """Берёт первую содержательную строку поста как заголовок."""
    for line in text.split("\n"):
        line = line.strip().strip("*•▪️ ").strip()
        # пропускаем строки-ссылки и слишком короткие
        if len(line) >= 6 and not line.startswith("http"):
            return line[:120]
    return (text.strip()[:120] or "Предложение из Telegram")


def _looks_like_deal(text: str) -> bool:
    low = text.lower()
    if any(marker in low for marker in DEAL_MARKERS):
        return True
    # либо в тексте есть конкретная цена в тенге
    return bool(_PRICE_RE.search(low))


class TelegramChannelSource(BaseSource):
    name = "Telegram"
    default_type = "Акция"

    HEADERS = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        "Accept-Language": "ru-RU,ru;q=0.9,kk;q=0.8",
    }

    def __init__(self, channels=None, **kw):
        super().__init__(**kw)
        self.channels = channels or CHANNELS

    def _fetch_channel(self, username: str, channel_title: str) -> List[Deal]:
        if requests is None:
            raise RuntimeError("Установите requests: pip install requests")
        if BeautifulSoup is None:
            raise RuntimeError("Установите bs4: pip install beautifulsoup4")

        url = f"https://t.me/s/{username}"
        resp = requests.get(url, headers=self.HEADERS, timeout=self.timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # .tgme_widget_message несёт атрибут data-post с id поста
        messages = soup.select(".tgme_widget_message")

        deals: List[Deal] = []
        seen = set()
        for msg in messages[-PER_CHANNEL:]:
            text_el = msg.select_one(".tgme_widget_message_text")
            if not text_el:
                continue
            text = text_el.get_text("\n", strip=True)
            if not text or not _looks_like_deal(text):
                continue

            # id и ссылка на пост (data-post на самом элементе или вложенном)
            data_post = msg.get("data-post")
            if not data_post:
                holder = msg.select_one("[data-post]")
                data_post = holder.get("data-post") if holder else None
            if not data_post or data_post in seen:
                continue
            seen.add(data_post)
            post_url = f"https://t.me/{data_post}"

            # дата поста
            time_el = msg.select_one("time[datetime]")
            posted = date.today()
            if time_el and time_el.get("datetime"):
                try:
                    posted = datetime.fromisoformat(
                        time_el["datetime"].replace("Z", "+00:00")).date()
                except ValueError:
                    pass

            title = _make_title(text)
            old, new = _extract_prices(text)
            discount = _extract_discount(text)
            # если % не указан, но есть обе цены — посчитаем скидку сами
            if not discount and old and new and new < old:
                discount = f"-{round((old - new) / old * 100)}%"
            # отсев статей-вопросов без конкретного оффера
            if _is_article(title, text) and not (discount or new):
                continue
            deals.append(Deal(
                title=title,
                source=f"{channel_title} (Telegram)",
                url=post_url,
                city=_extract_city(text),
                deal_type=self.default_type,
                description=text[:280],
                discount=discount,
                old_price=old,
                new_price=new,
                starts_at=posted.isoformat(),
                ends_at=_extract_ends_at(text, posted),
            ))
        return deals

    def fetch(self) -> List[Deal]:
        all_deals: List[Deal] = []
        for i, (username, channel_title) in enumerate(self.channels):
            if i:
                time.sleep(self.throttle)
            try:
                got = self._fetch_channel(username, channel_title)
                print(f"    [TG] @{username}: предложений {len(got)}")
                all_deals.extend(got)
            except Exception as exc:  # noqa: BLE001
                print(f"    [TG] @{username} ошибка: {exc}")
        return all_deals


# Тест: python -m parser.sources.telegram
if __name__ == "__main__":
    src = TelegramChannelSource()
    print("Тест парсера Telegram-каналов...")
    found = src.fetch()
    print(f"\nВсего предложений: {len(found)}\n")
    for d in found[:20]:
        price = f"{int(d.new_price)}₸" if d.new_price else ""
        print(f"  [{d.city}] {d.discount or '—':>6} {price:>9}  "
              f"{d.title[:60]}  ({d.category})")
