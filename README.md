# Yandex Direct Monitor

Ежедневная сводка по рекламным кампаниям Яндекс Директ в Telegram.

## Что делает

- **Каждый день в 9:00 МСК** — сводка за вчера (показы, клики, расход, CTR по каждой кампании)
- **По понедельникам в 9:05 МСК** — недельная сводка
- Бесплатно (GitHub Actions + Telegram Bot API)
- Без зависимостей (только стандартная библиотека Python)

## Настройка

### 1. Telegram-бот

1. Написать [@BotFather](https://t.me/BotFather) → `/newbot` → получить токен
2. Добавить бота в группу
3. Узнать `chat_id` группы:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
   Отправить любое сообщение в группу, затем в ответе найти `"chat":{"id":-123456789}`

### 2. GitHub-репозиторий

1. Создать репозиторий и запушить код
2. Settings → Secrets and variables → Actions → New repository secret:
   - `YANDEX_DIRECT_TOKEN` — OAuth-токен Яндекс Директ
   - `TELEGRAM_BOT_TOKEN` — токен бота из BotFather
   - `TELEGRAM_CHAT_ID` — ID чата/группы (с минусом для групп)

### 3. Проверка

Actions → Yandex Direct Report → Run workflow → поставить галку "Send a test notification"

## Ручной запуск

Через GitHub Actions: Run workflow → выбрать `daily` или `weekly`.

Локально:
```bash
export YANDEX_DIRECT_TOKEN=...
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
python3 check_campaigns.py
```
