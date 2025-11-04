"""
Конфигурация бота для ловли чеков
"""
import os
from typing import List, Dict

# API ID и API Hash от https://my.telegram.org
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# Токен основного бота (для управления)
MAIN_BOT_TOKEN = os.getenv("MAIN_BOT_TOKEN", "8522550266:AAECDZt9GDn3sFOSAE6Uf8Mt4bgO4Rlaku8")

# Путь к файлу с сессиями аккаунтов (каждая строка: api_id:api_hash:session_name:phone)
ACCOUNTS_FILE = "accounts.txt"

# Боты для мониторинга
CRYPTOBOT_USERNAME = "CryptoBot"
XROCKET_USERNAME = "xrocket_bot"

# Настройки производительности
MAX_CONCURRENT_CHECKS = 150  # Максимум одновременных активаций чеков (увеличено для скорости)
CHECK_TIMEOUT = 1.5  # Таймаут активации чека (секунды) (уменьшено для скорости)
UPDATE_CHECK_INTERVAL = 0.05  # Интервал проверки обновлений (секунды) (уменьшено)
CHECK_ACTIVATION_DELAY = 0.05  # Задержка перед первой проверкой ответа бота (секунды) (минимальная для максимальной скорости)
CHECK_ACTIVATION_RETRY_DELAY = 0.15  # Задержка перед повторной проверкой (если первая не нашла ответ)
MAX_HISTORY_CHECK = 1  # Максимум сообщений для проверки в истории (только последнее сообщение для скорости)
USE_OPTIMISTIC_ACTIVATION = True  # Оптимистичная активация - проверка параллельно с отправкой
MAX_RETRY_ATTEMPTS = 2  # Максимум попыток проверки ответа бота (быстрая + повторная)

# Защита от блокировки Telegram
MIN_DELAY_BETWEEN_BOT_MESSAGES = 0.1  # Минимальная задержка между сообщениями боту (секунды) - защита от блокировки
MAX_DELAY_BETWEEN_BOT_MESSAGES = 0.3  # Максимальная задержка между сообщениями боту (секунды) - имитация человека
RATE_LIMIT_PER_ACCOUNT = 20  # Максимум сообщений боту в минуту с одного аккаунта (защита от блокировки)
USE_HUMAN_LIKE_DELAYS = True  # Использовать случайные задержки для имитации человеческого поведения

# Настройки мониторинга
MONITOR_ALL_CHATS = True  # Мониторить все чаты
IGNORE_PRIVATE_CHATS = False  # Игнорировать личные чаты с ботами
AUTO_JOIN_CHANNELS = True  # Автоматически подписываться на каналы

# Антикапча
ANTICAPTCHA_ENABLED = True
ANTICAPTCHA_API_KEY = os.getenv("ANTICAPTCHA_API_KEY", "")  # API ключ от 2captcha или аналогичного сервиса

# Логирование
LOG_CHAT_ID = None  # ID чата для отправки логов (None - отключено)
LOG_ACTIVATED_CHECKS = True  # Логировать активированные чеки
LOG_STATS_INTERVAL = 3600  # Интервал отправки статистики (секунды)

# Автовывод из CryptoBot
AUTO_WITHDRAW_ENABLED = True
WITHDRAW_MAIN_ACCOUNT = ""  # Основной аккаунт для вывода (username или phone)
WITHDRAW_INTERVAL = 86400  # Интервал автовывода (секунды, 86400 = 1 день)

# Настройки создания и отправки чеков
CREATE_CHECK_AFTER_ACTIVATION = True  # Создавать новый чек после активации
CHECK_DISTRIBUTION_CHAT_ID = -5011055445  # ID чата для отправки созданных чеков (None - отключено)
CHECK_DISTRIBUTION_CHAT_USERNAME = None  # Username чата (например, @private_checks) - приоритетнее чем ID
CHECK_AMOUNT = 1.0  # Сумма чека для создания (по умолчанию 1.0)
CHECK_CURRENCY = "USD"  # Валюта чека (USD, RUB, BTC, ETH и т.д.)

# Паттерны для поиска чеков (оптимизированы для максимальной скорости и точности)
CHECK_PATTERNS = {
    "cryptobot": [
        # Стандартные ссылки
        r"t\.me/(?:Cryptobot|CryptoBot|CryptoCheckBot|Cryptodropbot|CRYPTOBOT)\?start=c[A-Za-z0-9_-]+",
        r"https?://t\.me/(?:Cryptobot|CryptoBot|CryptoCheckBot|Cryptodropbot|CRYPTOBOT)\?start=c[A-Za-z0-9_-]+",
        r"@(?:Cryptobot|CryptoBot|CryptoCheckBot|Cryptodropbot|CRYPTOBOT)\?start=c[A-Za-z0-9_-]+",
        # Варианты без домена
        r"/start\s+c[A-Za-z0-9_-]+",
        # Прямые коды (начинаются с 'c')
        r"\bc[A-Za-z0-9_-]{10,}\b",
    ],
    "xrocket": [
        # Стандартные ссылки
        r"t\.me/(?:xrocket_bot|xrocketbot|XRocket|XRocketBot)\?start=[A-Za-z0-9_-]+",
        r"https?://t\.me/(?:xrocket_bot|xrocketbot|XRocket|XRocketBot)\?start=[A-Za-z0-9_-]+",
        r"@(?:xrocket_bot|xrocketbot|XRocket|XRocketBot)\?start=[A-Za-z0-9_-]+",
        # Варианты без домена
        r"/start\s+[A-Za-z0-9_-]{10,}",
    ]
}

# Настройки базы данных
DB_PATH = "checks.db"  # SQLite база данных

