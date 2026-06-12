#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Главный запуск парсера.

Что делает:
  1. Опрашивает все источники из parser/sources/ALL_SOURCES
  2. Складывает предложения в хранилище (data/deals.json) с дедупликацией
  3. Экспортирует активные предложения в site/data.json для витрины

Запуск:
    python run.py
"""

from __future__ import annotations

import os

from parser.sources import ALL_SOURCES
from parser.store import DealStore

BASE = os.path.dirname(os.path.abspath(__file__))
STORE_PATH = os.path.join(BASE, "data", "deals.json")
SITE_DATA = os.path.join(BASE, "site", "data.json")


def main() -> None:
    print("Запуск парсера скидок Казахстана...")
    store = DealStore(STORE_PATH)
    store.load()

    total_new = 0
    for source in ALL_SOURCES:
        deals = source.safe_fetch()
        total_new += store.add_many(deals)

    store.save()
    store.export_site_data(SITE_DATA)

    active = store.active_deals()
    print("-" * 48)
    print(f"Всего в базе: {len(store.all_deals())}")
    print(f"Активных предложений: {len(active)}")
    print(f"Новых за этот запуск: {total_new}")
    print(f"Данные для сайта: {SITE_DATA}")

    # Короткая сводка по категориям
    by_cat: dict[str, int] = {}
    for d in active:
        by_cat[d.category] = by_cat.get(d.category, 0) + 1
    print("По категориям:", ", ".join(f"{k}: {v}" for k, v in sorted(by_cat.items())))


if __name__ == "__main__":
    main()
