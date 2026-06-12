# -*- coding: utf-8 -*-
"""Хранилище скидок: дедупликация и экспорт в JSON для сайта/телеграма."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Iterable, List

from .models import Deal, CATEGORIES, CITIES, TYPES, TAGS


class DealStore:
    """Простое JSON-хранилище. Для масштабирования заменяется на SQLite/Postgres."""

    def __init__(self, path: str):
        self.path = path
        self._by_id: dict[str, Deal] = {}

    def load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for raw in data.get("deals", []):
                raw = {k: v for k, v in raw.items()
                       if k not in ("days_left", "freshness", "is_active")}
                deal = Deal(**raw)
                self._by_id[deal.id] = deal

    def add_many(self, deals: Iterable[Deal]) -> int:
        """Добавляет новые предложения, возвращает число действительно новых."""
        new_count = 0
        for deal in deals:
            if deal.id not in self._by_id:
                new_count += 1
            self._by_id[deal.id] = deal
        return new_count

    def active_deals(self) -> List[Deal]:
        return [d for d in self._by_id.values() if d.is_active()]

    def all_deals(self) -> List[Deal]:
        return list(self._by_id.values())

    def save(self) -> None:
        """Сохраняет всё хранилище (включая историю)."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "deals": [d.to_dict() for d in self._by_id.values()],
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def export_site_data(self, path: str) -> None:
        """Экспортирует ТОЛЬКО активные предложения для витрины сайта."""
        active = sorted(
            self.active_deals(),
            key=lambda d: (d.days_left() if d.days_left() is not None else 9999),
        )
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(active),
            "categories": CATEGORIES,
            "cities": CITIES,
            "types": TYPES,
            "tags": TAGS,
            "deals": [d.to_dict() for d in active],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
