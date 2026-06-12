# -*- coding: utf-8 -*-
"""Реальный источник: Wildberries.kz (публичный JSON-API, цены в тенге).

Почему WB первым: открытый API (не нужно обходить защиту — это «белый» путь),
огромный каталог по всем категориям, доставка по всему Казахстану и сильный
раздел «уход/красота».

ВАЖНО: WB блокирует серверные/дата-центровые IP. Поэтому запускать парсер нужно
с обычного компьютера (твой Mac) или с сервера в РФ/КЗ. Из облачных песочниц
API часто не отвечает — это нормально.

Быстрый тест только этого источника (покажет, что реально пришло от WB):
    python -m parser.sources.wildberries

Если увидишь товары со скидками — всё работает, можно запускать python run.py.
Если пусто/ошибка — поправим параметр DEST (см. ниже) под твой регион.
"""

from __future__ import annotations

import time
import random
from typing import List, Optional

from .base import BaseSource
from ..models import Deal

try:
    import requests
except ImportError:
    requests = None


# Регион доставки (влияет на наличие/цену). Значение по умолчанию — Алматы.
# Если результаты пустые — попробуй другой код (Астана, вся страна и т.п.).
# Узнать свой dest: открой wildberries.kz, F12 → Network → фильтр "search" →
# в запросе будет параметр dest=...
DEST = -2160049           # Алматы (примерное значение, при необходимости поменяй)
CURRENCY = "kzt"

# Поисковые запросы → категория нашего каталога. Упор на «уход/красоту»,
# плюс разнообразие по другим категориям. Добавляй/убирай по вкусу.
QUERIES = [
    ("уход за лицом", "Красота и здоровье"),
    ("крем для лица", "Красота и здоровье"),
    ("сыворотка для лица", "Красота и здоровье"),
    ("маска для лица", "Красота и здоровье"),
    ("шампунь", "Красота и здоровье"),
    ("парфюм", "Красота и здоровье"),
    ("смартфон", "Электроника"),
    ("наушники", "Электроника"),
    ("кроссовки", "Одежда и обувь"),
    ("куртка", "Одежда и обувь"),
    ("игрушки детские", "Детям"),
    ("посуда", "Дом и ремонт"),
]


def _money(value) -> Optional[float]:
    """WB отдаёт цены в копейках/тиынах (×100). Возвращает в тенге."""
    if value is None:
        return None
    try:
        return round(float(value) / 100, 2)
    except (TypeError, ValueError):
        return None


def _extract_prices(p: dict):
    """Достаёт (старая_цена, новая_цена) из товара, устойчиво к разным
    форматам ответа WB (структура у них периодически меняется)."""
    # Старый формат: priceU / salePriceU прямо в товаре
    old = _money(p.get("priceU"))
    new = _money(p.get("salePriceU"))
    if old and new:
        return old, new

    # Новый формат: цены внутри sizes[].price.{basic,product}
    sizes = p.get("sizes") or []
    for s in sizes:
        price = s.get("price") or {}
        basic = _money(price.get("basic"))
        product = _money(price.get("product"))
        if basic and product:
            return basic, product
    return old, new


class WildberriesKZSource(BaseSource):
    name = "Wildberries"
    base_url = "https://search.wb.ru/exactmatch/ru/common/v5/search"
    default_type = "Скидка"

    PER_QUERY = 8          # сколько товаров со скидкой брать на запрос
    MIN_DISCOUNT = 5       # минимальная скидка в %, чтобы попасть на витрину
    PAUSE = 1.8            # пауза между запросами, сек (защита от 429)
    RETRIES = 4            # повторов при 429 / сетевой ошибке

    HEADERS = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Origin": "https://www.wildberries.kz",
        "Referer": "https://www.wildberries.kz/",
    }

    _session = None

    def _get_session(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(self.HEADERS)
        return self._session

    def _search(self, query: str, debug: bool = False) -> list:
        if requests is None:
            raise RuntimeError("Установите requests: pip install requests")
        params = {
            "appType": 1,
            "curr": CURRENCY,
            "dest": DEST,
            "query": query,
            "resultset": "catalog",
            "sort": "popular",
            "spp": 30,
            "lang": "ru",
            "locale": "ru",
        }
        session = self._get_session()
        last_err = None
        for attempt in range(self.RETRIES):
            try:
                resp = session.get(self.base_url, params=params, timeout=self.timeout)
                if resp.status_code == 429:
                    wait = self.PAUSE * (attempt + 2) + random.uniform(0, 1)
                    if debug:
                        print(f"    [WB] 429 на '{query}', жду {wait:.1f}с и повторяю...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                products = (data.get("data") or {}).get("products") or []
                if debug:
                    print(f"    [WB] '{query}': товаров пришло {len(products)}")
                    if products:
                        s = products[0]
                        print(f"         пример полей цены: priceU={s.get('priceU')} "
                              f"salePriceU={s.get('salePriceU')} "
                              f"sizes0={ (s.get('sizes') or [{}])[0].get('price') }")
                return products
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(self.PAUSE * (attempt + 1))
        raise last_err or RuntimeError("WB: не удалось получить ответ")

    def fetch(self, debug: bool = False) -> List[Deal]:
        deals: List[Deal] = []
        for i, (query, category) in enumerate(QUERIES):
            if i:
                time.sleep(self.PAUSE)  # пауза между запросами
            try:
                products = self._search(query, debug=debug)
            except Exception as exc:  # noqa: BLE001
                print(f"    [WB] запрос '{query}' не удался: {exc}")
                continue

            taken = 0
            for p in products:
                if taken >= self.PER_QUERY:
                    break
                old, new = _extract_prices(p)
                if not old or not new or new >= old:
                    continue
                pct = round((old - new) / old * 100)
                if pct < self.MIN_DISCOUNT:
                    continue

                pid = p.get("id")
                brand = (p.get("brand") or "").strip()
                name = (p.get("name") or "").strip()
                title = f"{brand} {name}".strip() or name or "Товар WB"

                deals.append(Deal(
                    title=title[:120],
                    source=self.name,
                    url=f"https://www.wildberries.kz/catalog/{pid}/detail.aspx",
                    category=category,
                    city="Вся страна",
                    deal_type=self.default_type,
                    description=f"Скидка {pct}% на Wildberries.kz."
                                + (f" Бренд: {brand}." if brand else ""),
                    discount=f"-{pct}%",
                    old_price=old,
                    new_price=new,
                    currency="₸",
                    # WB в этом endpoint не отдаёт срок акции — оставляем пустым
                ))
                taken += 1
        return deals


# Тест только WB: python -m parser.sources.wildberries
if __name__ == "__main__":
    src = WildberriesKZSource()
    print(f"Тест Wildberries.kz (dest={DEST}, curr={CURRENCY}), "
          f"пауза {src.PAUSE}с между запросами...")
    found = src.fetch(debug=True)
    print(f"\nНайдено товаров со скидкой ≥{src.MIN_DISCOUNT}%: {len(found)}")
    for d in found[:12]:
        print(f"  {d.discount:>5}  {int(d.new_price):>8} ₸  "
              f"(было {int(d.old_price)})  {d.title[:50]}  [{d.category}]")
    if not found:
        print("Пусто. Возможные причины: WB блокирует этот IP (запусти с "
              "обычного компьютера) или нужно поменять DEST под твой регион.")
