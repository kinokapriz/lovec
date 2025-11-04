"""
Модуль для обработки и активации чеков
"""
import re
import asyncio
import random
import time
from collections import defaultdict
from typing import List, Optional, Tuple
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from config import (
    CHECK_PATTERNS, CHECK_TIMEOUT, MAX_CONCURRENT_CHECKS,
    CREATE_CHECK_AFTER_ACTIVATION, CHECK_DISTRIBUTION_CHAT_ID, CHECK_DISTRIBUTION_CHAT_USERNAME,
    CHECK_AMOUNT, CHECK_CURRENCY, CHECK_ACTIVATION_DELAY, MAX_HISTORY_CHECK, USE_OPTIMISTIC_ACTIVATION,
    CHECK_ACTIVATION_RETRY_DELAY, MAX_RETRY_ATTEMPTS, MIN_DELAY_BETWEEN_BOT_MESSAGES,
    MAX_DELAY_BETWEEN_BOT_MESSAGES, RATE_LIMIT_PER_ACCOUNT, USE_HUMAN_LIKE_DELAYS
)
from database import db


class CheckProcessor:
    def __init__(self):
        self.active_tasks = set()
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)
        # Компилируем регулярные выражения заранее для ускорения
        self.compiled_patterns = {
            "cryptobot": [re.compile(p, re.IGNORECASE) for p in CHECK_PATTERNS["cryptobot"]],
            "xrocket": [re.compile(p, re.IGNORECASE) for p in CHECK_PATTERNS["xrocket"]]
        }
        # Компилируем паттерны для извлечения суммы
        self.amount_patterns = [
            re.compile(r"(\d+(?:\.\d+)?)\s*(?:usd|usdt|руб|rub)", re.IGNORECASE),
            re.compile(r"(?:получено|received|получили|got)\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
            re.compile(r"(\d+(?:\.\d+)?)\s*(?:\$|₽)", re.IGNORECASE),
        ]
        self.number_pattern = re.compile(r"\d+\.?\d*")
        
        # Защита от блокировки - отслеживание скорости отправки сообщений
        self.account_message_times = defaultdict(list)  # account_info -> список времени отправки сообщений
        self.account_semaphores = defaultdict(lambda: asyncio.Semaphore(1))  # Семафор для каждого аккаунта

    def extract_checks(self, text: str) -> List[Tuple[str, str]]:
        """
        Извлечь чеки из текста (оптимизировано для максимальной скорости)
        Возвращает список кортежей (check_code, bot_type)
        """
        checks = []
        
        # Быстрая проверка наличия ключевых слов
        if "start=" not in text and "/start" not in text.lower():
            return checks
        
        # Очистка текста от лишних символов (минимальная обработка)
        text_clean = text.replace("\\", "").replace("\n", " ").replace("\r", " ")
        
        # Поиск чеков CryptoBot (быстрый поиск с предкомпилированными паттернами)
        for pattern in self.compiled_patterns["cryptobot"]:
            matches = pattern.finditer(text_clean)
            for match in matches:
                url = match.group(0)
                
                # Быстрое извлечение кода чека
                if "start=" in url:
                    # Разделяем по start= и берем первую часть после знака =
                    parts = url.split("start=", 1)
                    if len(parts) > 1:
                        check_code = parts[1].split("&")[0].split()[0].split("\n")[0].strip()
                        if check_code.startswith("c") and len(check_code) >= 8:
                            checks.append((check_code, "cryptobot"))
                elif "/start" in url.lower():
                    # Обработка /start команды
                    parts = url.lower().split("/start", 1)
                    if len(parts) > 1:
                        check_code = parts[1].strip().split()[0].strip()
                        if check_code.startswith("c") and len(check_code) >= 8:
                            checks.append((check_code, "cryptobot"))
                elif url.startswith("c") and len(url) >= 8:
                    # Прямой код чека
                    check_code = url.strip()
                    if len(check_code) >= 8 and check_code.replace("_", "").replace("-", "").isalnum():
                        checks.append((check_code, "cryptobot"))
        
        # Поиск чеков Xrocket (быстрый поиск с предкомпилированными паттернами)
        for pattern in self.compiled_patterns["xrocket"]:
            matches = pattern.finditer(text_clean)
            for match in matches:
                url = match.group(0)
                if "start=" in url:
                    parts = url.split("start=", 1)
                    if len(parts) > 1:
                        check_code = parts[1].split("&")[0].split()[0].split("\n")[0].strip()
                        if len(check_code) >= 8:
                            checks.append((check_code, "xrocket"))
                elif "/start" in url.lower():
                    parts = url.lower().split("/start", 1)
                    if len(parts) > 1:
                        check_code = parts[1].strip().split()[0].strip()
                        if len(check_code) >= 8:
                            checks.append((check_code, "xrocket"))
        
        # Удаление дубликатов (быстрое)
        seen = set()
        unique_checks = []
        for check in checks:
            if check not in seen:
                seen.add(check)
                unique_checks.append(check)
        
        return unique_checks

    async def _check_bot_response(self, client: Client, bot_username: str) -> Optional[dict]:
        """
        Проверить ответ бота (быстрая проверка)
        Возвращает данные об активации или None если не найдено
        """
        async for message in client.get_chat_history(bot_username, limit=MAX_HISTORY_CHECK):
            # Минимальная проверка - только ключевые моменты
            if not message.from_user or not message.from_user.is_bot:
                continue
            
            text = message.text or ""
            if not text:
                continue
            
            text_lower = text.lower()
            
            # Быстрая проверка успешной активации (приоритет - самые частые случаи первыми)
            if "активирован" in text_lower or "activated" in text_lower or "получено" in text_lower:
                # Извлекаем сумму и валюту (быстро, без лишних проверок)
                amount = self._extract_amount(text)
                currency = self._extract_currency(text)
                return {
                    "success": True,
                    "amount": amount,
                    "currency": currency,
                    "text": text
                }
            elif "уже" in text_lower or "already" in text_lower:
                return {"success": False, "error": "already_activated"}
            elif "капча" in text_lower or "captcha" in text_lower:
                return {"success": False, "error": "captcha_required"}
            # Если нашли сообщение от бота, но нет нужных ключевых слов - выходим
            break
        
        return None  # Не найдено ответа

    async def _wait_for_rate_limit(self, account_info: str):
        """
        Ожидание для соблюдения лимита скорости (защита от блокировки)
        """
        if not RATE_LIMIT_PER_ACCOUNT:
            return
        
        async with self.account_semaphores[account_info]:
            current_time = time.time()
            
            # Очистка старых записей (старше 1 минуты)
            self.account_message_times[account_info] = [
                t for t in self.account_message_times[account_info]
                if current_time - t < 60
            ]
            
            # Если превышен лимит - ждем
            if len(self.account_message_times[account_info]) >= RATE_LIMIT_PER_ACCOUNT:
                oldest_time = min(self.account_message_times[account_info])
                wait_time = 60 - (current_time - oldest_time) + 0.1
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    # Обновляем время
                    current_time = time.time()
                    self.account_message_times[account_info] = [
                        t for t in self.account_message_times[account_info]
                        if current_time - t < 60
                    ]
            
            # Добавляем случайную задержку для имитации человеческого поведения
            if USE_HUMAN_LIKE_DELAYS:
                delay = random.uniform(MIN_DELAY_BETWEEN_BOT_MESSAGES, MAX_DELAY_BETWEEN_BOT_MESSAGES)
                await asyncio.sleep(delay)
            
            # Записываем время отправки сообщения
            self.account_message_times[account_info].append(time.time())

    async def activate_check(self, client: Client, check_code: str, bot_type: str,
                           bot_username: str, account_info: str) -> Tuple[bool, Optional[dict]]:
        """
        Активировать чек через бота (максимально агрессивная оптимизация для скорости)
        Использует быструю проверку + повторную проверку если бот не успел ответить
        Защита от блокировки: лимиты скорости и случайные задержки
        Возвращает (успех, данные о чеке)
        """
        async with self.semaphore:
            try:
                # Защита от блокировки - соблюдение лимита скорости
                await self._wait_for_rate_limit(account_info)
                
                # Отправляем команду боту (с обработкой FloodWait)
                try:
                    if USE_OPTIMISTIC_ACTIVATION:
                        # Оптимистичная активация: отправляем и сразу проверяем параллельно (максимальная скорость)
                        send_task = asyncio.create_task(
                            client.send_message(
                                bot_username,
                                f"/start {check_code}",
                                disable_notification=True
                            )
                        )
                        
                        # Минимальная задержка (параллельно с отправкой)
                        await asyncio.sleep(CHECK_ACTIVATION_DELAY)
                        await send_task  # Убеждаемся что отправлено
                    else:
                        # Стандартная активация
                        await client.send_message(
                            bot_username,
                            f"/start {check_code}",
                            disable_notification=True
                        )
                        await asyncio.sleep(CHECK_ACTIVATION_DELAY)
                except FloodWait as e:
                    # Если получили FloodWait - ждем и возвращаем ошибку
                    await asyncio.sleep(e.value)
                    return False, {"error": "flood_wait", "wait_time": e.value}
                
                # Быстрая проверка ответа бота (первая попытка)
                result = await self._check_bot_response(client, bot_username)
                
                if result:
                    if result.get("success"):
                        return True, {
                            "amount": result.get("amount"),
                            "currency": result.get("currency"),
                            "text": result.get("text")
                        }
                    else:
                        return False, {"error": result.get("error", "unknown_error")}
                
                # Если бот не успел ответить за минимальное время - повторная проверка
                # (это защита от пропуска активации, если бот медленный)
                for attempt in range(MAX_RETRY_ATTEMPTS):
                    await asyncio.sleep(CHECK_ACTIVATION_RETRY_DELAY)
                    result = await self._check_bot_response(client, bot_username)
                    
                    if result:
                        if result.get("success"):
                            return True, {
                                "amount": result.get("amount"),
                                "currency": result.get("currency"),
                                "text": result.get("text")
                            }
                        else:
                            return False, {"error": result.get("error", "unknown_error")}
                
                # Если после всех попыток не нашли ответ - возвращаем ошибку
                return False, {"error": "unknown_response"}
                
            except Exception as e:
                return False, {"error": str(e)}

    def _extract_amount(self, text: str) -> Optional[float]:
        """Извлечь сумму из текста (максимально быстро, с предкомпилированными паттернами)"""
        # Быстрый поиск чисел (приоритет - первый паттерн, самый частый)
        if self.amount_patterns:
            match = self.amount_patterns[0].search(text)
            if match:
                try:
                    return float(match.group(1))
                except:
                    pass
        
        # Просто поиск числа (используем скомпилированный паттерн)
        numbers = self.number_pattern.findall(text)
        if numbers:
            try:
                return float(numbers[0])
            except:
                pass
        
        return None

    def _extract_currency(self, text: str) -> str:
        """Извлечь валюту из текста (максимально быстро)"""
        # Быстрая проверка (приоритет - самые частые валюты первыми)
        if "$" in text or "usd" in text[:10].lower() or "usdt" in text[:10].lower():
            return "USD"
        elif "₽" in text or "руб" in text[:10].lower() or "rub" in text[:10].lower():
            return "RUB"
        elif "btc" in text[:10].lower():
            return "BTC"
        elif "eth" in text[:10].lower():
            return "ETH"
        return "UNKNOWN"

    async def process_message(self, client: Client, message: Message, account_info: str):
        """
        Обработать сообщение и активировать найденные чеки (максимально оптимизировано для скорости)
        """
        # Быстрое извлечение текста (приоритетные источники первыми)
        # Сначала проверяем кнопки - там чаще всего чеки (самый быстрый путь)
        text = ""
        if message.reply_markup:
            for row in message.reply_markup.inline_keyboard:
                for button in row:
                    if button.url:
                        text = button.url
                        break  # Первая ссылка - обычно это чек
                    elif button.text and ("start=" in button.text.lower() or "/start" in button.text.lower()):
                        text = button.text
                        break
                if text:
                    break
        
        # Если нет в кнопках, проверяем основной текст
        if not text:
            text = message.text or message.caption or ""
        
        # Быстрая проверка на наличие чеков (ранний выход если нет ключевых слов)
        if not text or ("start=" not in text and "/start" not in text.lower()):
            return
        
        # Извлечение чеков (быстрое извлечение для максимальной скорости)
        checks = self.extract_checks(text)
        
        if not checks:
            return
        
        # Определение бота по типу
        bot_usernames = {
            "cryptobot": "CryptoBot",
            "xrocket": "xrocket_bot"
        }
        
        # Все аккаунты ловят один и тот же чек одновременно (максимальная скорость)
        # Параллельная активация всех чеков на всех аккаунтах (без ожидания)
        for check_code, bot_type in checks:
            bot_username = bot_usernames.get(bot_type)
            if not bot_username:
                continue
            
            # Создание задачи для активации (сразу запускается, без ожидания)
            task = asyncio.create_task(
                self._activate_check_task(
                    client, check_code, bot_type, bot_username,
                    account_info, message.chat.title or str(message.chat.id)
                )
            )
            self.active_tasks.add(task)
            task.add_done_callback(self.active_tasks.discard)
            # Не ждем завершения - максимальная параллельность

    async def create_check(self, client: Client, bot_type: str, bot_username: str,
                          amount: float = None, currency: str = None) -> Optional[str]:
        """
        Создать новый чек через бота
        Возвращает ссылку на созданный чек или None
        """
        try:
            amount = amount or CHECK_AMOUNT
            currency = currency or CHECK_CURRENCY
            
            if bot_type == "cryptobot":
                # Создание чека в CryptoBot
                # Пробуем различные форматы команд
                commands = [
                    f"/createCheck {amount} {currency}",
                    f"/createcheck {amount} {currency}",
                    f"/create {amount} {currency}",
                    f"/check {amount} {currency}",
                    f"/newcheck {amount} {currency}",
                ]
                
                check_link = None
                for cmd in commands:
                    try:
                        await client.send_message(
                            bot_username,
                            cmd,
                            disable_notification=True
                        )
                        
                        # Ждем ответ от бота
                        await asyncio.sleep(2.5)
                        
                        # Получаем последние сообщения от бота
                        async for message in client.get_chat_history(bot_username, limit=5):
                            if message.from_user and message.from_user.is_bot:
                                text = message.text or ""
                                # Поиск ссылки на чек в ответе
                                check_link = self._extract_check_link_from_text(text)
                                if check_link:
                                    return check_link
                                
                                # Проверка на наличие кнопки со ссылкой
                                if message.reply_markup:
                                    for row in message.reply_markup.inline_keyboard:
                                        for button in row:
                                            if button.url:
                                                check_link = button.url
                                                if "start=" in check_link.lower():
                                                    return check_link
                        
                        # Если команда сработала (нет ошибки), выходим
                        if check_link:
                            break
                    except:
                        continue
                            
            elif bot_type == "xrocket":
                # Создание чека в Xrocket
                commands = [
                    f"/createcheck {amount} {currency}",
                    f"/create {amount} {currency}",
                    f"/check {amount} {currency}",
                    f"/newcheck {amount} {currency}",
                    f"/create_check {amount} {currency}",
                ]
                
                check_link = None
                for cmd in commands:
                    try:
                        await client.send_message(
                            bot_username,
                            cmd,
                            disable_notification=True
                        )
                        
                        await asyncio.sleep(2.5)
                        
                        async for message in client.get_chat_history(bot_username, limit=5):
                            if message.from_user and message.from_user.is_bot:
                                text = message.text or ""
                                check_link = self._extract_check_link_from_text(text)
                                if check_link:
                                    return check_link
                                
                                # Проверка на наличие кнопки со ссылкой
                                if message.reply_markup:
                                    for row in message.reply_markup.inline_keyboard:
                                        for button in row:
                                            if button.url:
                                                check_link = button.url
                                                if "start=" in check_link.lower():
                                                    return check_link
                        
                        if check_link:
                            break
                    except:
                        continue
            
            return None
            
        except Exception as e:
            print(f"Ошибка при создании чека: {e}")
            return None

    def _extract_check_link_from_text(self, text: str) -> Optional[str]:
        """Извлечь ссылку на чек из текста ответа бота"""
        if not text:
            return None
        
        # Поиск ссылок вида t.me/...?start=... (приоритет)
        patterns = [
            r"t\.me/[^\s\)\]]+\?start=[^\s\)\]]+",
            r"https?://t\.me/[^\s\)\]]+\?start=[^\s\)\]]+",
            r"t\.me/[^\s\)\]]+",
            r"https?://t\.me/[^\s\)\]]+",
            r"https?://[^\s\)\]]+",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                link = matches[0].strip().rstrip('.,!?)')
                # Проверяем, что это действительно ссылка на чек
                if "start=" in link.lower() or "t.me" in link.lower():
                    return link
        
        # Поиск кода чека (начинается с 'c' для CryptoBot)
        code_pattern = r"\bc[A-Za-z0-9_-]{10,}\b"
        code_matches = re.findall(code_pattern, text)
        if code_matches:
            code = code_matches[0]
            # Формируем ссылку
            return f"https://t.me/CryptoBot?start={code}"
        
        return None

    async def send_check_to_chat(self, client: Client, check_link: str, bot_type: str):
        """Отправить созданный чек в указанный чат"""
        try:
            chat_id = CHECK_DISTRIBUTION_CHAT_ID
            chat_username = CHECK_DISTRIBUTION_CHAT_USERNAME
            
            if not chat_id and not chat_username:
                return False
            
            # Используем username если указан
            chat = chat_username if chat_username else chat_id
            
            # Формируем сообщение
            message_text = f"💰 Новый чек от {bot_type.upper()}:\n\n{check_link}"
            
            await client.send_message(
                chat,
                message_text,
                disable_notification=False
            )
            
            return True
            
        except Exception as e:
            print(f"Ошибка при отправке чека в чат: {e}")
            return False

    async def _activate_check_task(self, client: Client, check_code: str, bot_type: str,
                                  bot_username: str, account_info: str, source_chat: str):
        """Задача для активации чека"""
        success, result = await self.activate_check(
            client, check_code, bot_type, bot_username, account_info
        )
        
        if success:
            amount = result.get("amount") if result else None
            currency = result.get("currency", "UNKNOWN") if result else "UNKNOWN"
            
            # Асинхронное сохранение в базу данных (fire-and-forget для скорости)
            asyncio.create_task(db.add_check(
                check_code=check_code,
                bot_type=bot_type,
                amount=amount,
                currency=currency,
                activated_by=account_info,
                source_chat=source_chat
            ))
            
            # Асинхронное обновление статистики (fire-and-forget для скорости)
            asyncio.create_task(db.update_stats(account_info, bot_type, amount or 0, currency))
            
            # Логирование
            print(f"✅ Чек активирован: {bot_type} - {check_code} - {amount} {currency} ({account_info})")
            
            # Асинхронное логирование
            try:
                from logger import logger
                await logger.log_activated_check(
                    bot_type, check_code, amount or 0, currency, account_info, source_chat
                )
            except:
                pass
            
            # Создание и отправка нового чека после активации
            if CREATE_CHECK_AFTER_ACTIVATION:
                asyncio.create_task(
                    self._create_and_send_check_task(client, bot_type, bot_username, account_info)
                )

    async def _create_and_send_check_task(self, client: Client, bot_type: str,
                                         bot_username: str, account_info: str):
        """Задача для создания и отправки чека"""
        try:
            # Создаем новый чек
            check_link = await self.create_check(
                client, bot_type, bot_username, CHECK_AMOUNT, CHECK_CURRENCY
            )
            
            if check_link:
                print(f"💰 Новый чек создан: {bot_type} - {check_link} ({account_info})")
                
                # Отправляем чек в указанный чат
                if CHECK_DISTRIBUTION_CHAT_ID or CHECK_DISTRIBUTION_CHAT_USERNAME:
                    sent = await self.send_check_to_chat(client, check_link, bot_type)
                    if sent:
                        print(f"📤 Чек отправлен в чат: {bot_type} ({account_info})")
                    else:
                        print(f"⚠️ Не удалось отправить чек в чат: {bot_type} ({account_info})")
            else:
                print(f"⚠️ Не удалось создать чек: {bot_type} ({account_info})")
                
        except Exception as e:
            print(f"Ошибка при создании/отправке чека: {e}")


# Глобальный экземпляр процессора
check_processor = CheckProcessor()

