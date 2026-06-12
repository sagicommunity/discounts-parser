# -*- coding: utf-8 -*-
"""Базовый класс источника. Каждый сайт = свой наследник."""

from __future__ import annotations

import time
from typing import List

from ..models import Deal

try:
    import requests
except ImportError:  # парсер должен импортироваться даже без requests
    requests = None


class BaseSource:
    """Базовый источник скидок.

    Чтобы добавить новый сайт — наследуйся и реализуй fetch().
    Для сайтов на JavaScript используй Playwright/Selenium внутри fetch().
    """

    name: str = "BaseSource"
    base_url: str = ""
    # Тип предложений по умолчанию для этого источника
    default_type: str = "Акция"

    # Заголовки, имитирующие обычный браузер (часть сайтов это требует)
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,kk;q=0.8",
    }

    def __init__(self, timeout: int = 20, throttle: float = 1.0):
        self.timeout = timeout
        self.throttle = throttle  # пауза между запросами (уважение к сайту)

    # --- Утилиты сети ----------------------------------------------------

    def get(self, url: str) -> str:
        """GET-запрос с заголовками. Бросает исключение при сетевой ошибке."""
        if requests is None:
            raise RuntimeError("Установите requests: pip install requests")
        resp = requests.get(url, headers=self.HEADERS, timeout=self.timeout)
        resp.raise_for_status()
        time.sleep(self.throttle)
        return resp.text

    # --- Контракт --------------------------------------------------------

    def fetch(self) -> List[Deal]:
        """Вернуть список Deal. Переопредели в наследнике."""
        raise NotImplementedError

    def safe_fetch(self) -> List[Deal]:
        """Обёртка: ошибка одного источника не должна валить весь парсер."""
        try:
            deals = self.fetch()
            print(f"  [{self.name}] получено предложений: {len(deals)}")
            return deals
        except Exception as exc:  # noqa: BLE001
            print(f"  [{self.name}] ОШИБКА: {exc}")
            return []
