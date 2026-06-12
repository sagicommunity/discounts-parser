#!/bin/bash
# Одна команда: собрать скидки из Telegram-каналов и опубликовать сайт.
# Запуск вручную:  bash update.sh
# Или повесить в автозапуск (см. README → Автоматизация).

# Пути к node/npx/python для запуска и из cron/launchd (там урезанный PATH)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.npm-global/bin:$PATH"

PROJECT="/Users/sagi/Claude/Projects/Парсер скидок, акций, бонусов, распродаж"
LOG="$PROJECT/update.log"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') старт обновления ===" >> "$LOG"

cd "$PROJECT" || { echo "нет папки проекта" >> "$LOG"; exit 1; }

# 1) Собрать скидки и обновить данные сайта
python3 run.py >> "$LOG" 2>&1 || { echo "ошибка парсера" >> "$LOG"; exit 1; }

# 2) Опубликовать сайт на Vercel (проект уже привязан, без вопросов)
cd "$PROJECT/site" || exit 1
npx --yes vercel --prod --yes >> "$LOG" 2>&1

echo "=== готово ===" >> "$LOG"
echo "Обновление завершено. Журнал: $LOG"
