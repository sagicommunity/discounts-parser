# -*- coding: utf-8 -*-
"""ШАБЛОН реального скрапера на BeautifulSoup.

Это рабочий пример того, КАК подключить настоящий сайт. Большинство
казахстанских сайтов скидок рендерятся через JavaScript, поэтому для них
понадобится Playwright (см. комментарий внизу). Для статических HTML-страниц
достаточно этого класса — поправь селекторы под конкретный сайт.
"""

from __future__ import annotations

from typing import List

from .base import BaseSource
from ..models import Deal

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


class HtmlDealsSource(BaseSource):
    """Универсальный скрапер карточек со статической HTML-страницы.

    Пример настройки под конкретный сайт — поменяй CSS-селекторы:
        CARD_SELECTOR     — селектор карточки предложения
        TITLE_SELECTOR    — заголовок внутри карточки
        LINK_SELECTOR     — ссылка
        DISCOUNT_SELECTOR — размер скидки
    """

    name = "HtmlExample"
    base_url = "https://example.kz/sales"
    city = "Алматы"
    category = "Прочее"

    CARD_SELECTOR = "div.deal-card"
    TITLE_SELECTOR = ".deal-title"
    LINK_SELECTOR = "a"
    DISCOUNT_SELECTOR = ".deal-discount"
    IMAGE_SELECTOR = "img"

    def fetch(self) -> List[Deal]:
        if BeautifulSoup is None:
            raise RuntimeError("Установите bs4: pip install beautifulsoup4")

        html = self.get(self.base_url)
        soup = BeautifulSoup(html, "html.parser")
        deals: List[Deal] = []

        for card in soup.select(self.CARD_SELECTOR):
            title_el = card.select_one(self.TITLE_SELECTOR)
            link_el = card.select_one(self.LINK_SELECTOR)
            disc_el = card.select_one(self.DISCOUNT_SELECTOR)
            img_el = card.select_one(self.IMAGE_SELECTOR)
            if not title_el:
                continue

            url = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                url = href if href.startswith("http") else self.base_url.rstrip("/") + "/" + href.lstrip("/")

            deals.append(Deal(
                title=title_el.get_text(strip=True),
                source=self.name,
                url=url or self.base_url,
                category=self.category,
                city=self.city,
                deal_type=self.default_type,
                discount=disc_el.get_text(strip=True) if disc_el else None,
                image=img_el["src"] if (img_el and img_el.get("src")) else None,
            ))
        return deals


# Для сайтов на JavaScript (Chocolife, Kaspi, Magnum и т.п.) шаблон такой:
#
#   from playwright.sync_api import sync_playwright
#
#   class JsDealsSource(BaseSource):
#       def fetch(self):
#           with sync_playwright() as p:
#               browser = p.chromium.launch(headless=True)
#               page = browser.new_page(user_agent=self.HEADERS["User-Agent"])
#               page.goto(self.base_url, wait_until="networkidle")
#               cards = page.query_selector_all("div.deal-card")
#               ...  # извлекаешь данные так же, как выше
#               browser.close()
#
# Установка: pip install playwright && playwright install chromium
