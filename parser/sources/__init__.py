# -*- coding: utf-8 -*-
"""Реестр источников. Добавляй новые скраперы сюда."""

from .telegram import TelegramChannelSource
from .seed import SeedSource
from .html_example import HtmlDealsSource

# Активные источники парсера.
# TelegramChannelSource — реальный источник: публичные каналы о скидках
# (читаются через t.me/s/, без логина и без блокировок).
# Список каналов настраивается в parser/sources/telegram.py → CHANNELS.
ALL_SOURCES = [
    TelegramChannelSource(),
    # SeedSource(),        # демо-данные (фолбэк, если нужно наполнить вручную)
    # HtmlDealsSource(),   # шаблон для парсинга обычных сайтов
]
