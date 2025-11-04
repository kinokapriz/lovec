"""
Основной модуль бота для ловли чеков
"""
import asyncio
import sys
from typing import Set
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from config import (
    CRYPTOBOT_USERNAME, XROCKET_USERNAME, MONITOR_ALL_CHATS,
    IGNORE_PRIVATE_CHATS, AUTO_JOIN_CHANNELS, LOG_CHAT_ID,
    LOG_ACTIVATED_CHECKS, LOG_STATS_INTERVAL, AUTO_WITHDRAW_ENABLED,
    WITHDRAW_MAIN_ACCOUNT, WITHDRAW_INTERVAL
)
from account_manager import account_manager
from check_processor import check_processor
from database import db
from anticaptcha import anticaptcha


class CheckGrabberBot:
    def __init__(self):
        self.processed_messages: Set[int] = set()  # Для отслеживания обработанных сообщений
        self.stats_task = None
        
    async def setup_handlers(self):
        """Настройка обработчиков для всех клиентов"""
        for phone, client in account_manager.get_all_clients().items():
            account_info = account_manager.get_account_info(phone)
            
            # Создаем замыкание для правильной работы с account_info
            def make_handler(acc_info):
                # Обработчик новых сообщений
                @client.on_message(filters.all & ~filters.me & ~filters.chat("me"))
                async def message_handler(cl: Client, msg: Message):
                    await self.handle_message(cl, msg, acc_info)
                
                # Обработчик редактированных сообщений
                @client.on_edited_message(filters.all & ~filters.me & ~filters.chat("me"))
                async def edited_message_handler(cl: Client, msg: Message):
                    await self.handle_message(cl, msg, acc_info)
            
            make_handler(account_info)
            
            # Подписка на каналы с ботами
            if AUTO_JOIN_CHANNELS:
                asyncio.create_task(self.auto_join_channels(client, phone))

    async def handle_message(self, client: Client, message: Message, account_info: str):
        """Обработка сообщения"""
        try:
            # Игнорируем свои сообщения
            if message.from_user and message.from_user.is_self:
                return
            
            # Игнорируем личные чаты с ботами, если настроено
            if IGNORE_PRIVATE_CHATS and message.chat.type == "private":
                if message.from_user and (message.from_user.username in [CRYPTOBOT_USERNAME.lower(), XROCKET_USERNAME.lower()]):
                    return
            
            # Проверка на дубликаты для этого аккаунта (оптимизировано для скорости)
            message_id = message.id
            chat_id = message.chat.id
            unique_id = f"{account_info}_{chat_id}_{message_id}"
            
            if unique_id in self.processed_messages:
                return
            
            self.processed_messages.add(unique_id)
            
            # Очистка старых ID (более эффективная очистка для экономии памяти)
            if len(self.processed_messages) > 20000:
                # Оставляем только последние 5000 записей (меньше для экономии памяти)
                self.processed_messages = set(list(self.processed_messages)[-5000:])
            
            # Параллельная обработка сообщения (не блокируем выполнение)
            # Все аккаунты будут обрабатывать одно и то же сообщение одновременно
            asyncio.create_task(
                check_processor.process_message(client, message, account_info)
            )
            
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            # Тихая обработка ошибок для скорости
            pass

    async def auto_join_channels(self, client: Client, phone: str):
        """Автоматическая подписка на каналы с ботами"""
        try:
            # Поиск каналов с упоминанием ботов
            bot_usernames = [CRYPTOBOT_USERNAME, XROCKET_USERNAME]
            
            for bot_username in bot_usernames:
                try:
                    # Проверяем, подписаны ли уже
                    try:
                        await client.get_chat(bot_username)
                    except:
                        # Если не можем получить чат, пропускаем
                        continue
                    
                    # Ищем публичные каналы/чаты
                    # Это можно расширить поиском через @username
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            pass

    async def start_logging(self):
        """Запуск системы логирования"""
        if not LOG_CHAT_ID or not LOG_ACTIVATED_CHECKS:
            return
        
        # Периодическая отправка статистики
        while account_manager.running:
            try:
                await asyncio.sleep(LOG_STATS_INTERVAL)
                
                stats = await db.get_total_stats()
                
                # Получаем первый клиент для отправки сообщения
                clients = account_manager.get_all_clients()
                if not clients:
                    continue
                
                client = list(clients.values())[0]
                
                stats_text = "📊 Статистика активации чеков:\n\n"
                for bot_type, data in stats.items():
                    stats_text += f"{bot_type.upper()}:\n"
                    stats_text += f"  Всего чеков: {data.get('total_checks', 0)}\n"
                    stats_text += f"  Общая сумма: {data.get('total_amount', 0)}\n"
                    stats_text += f"  Аккаунтов: {data.get('unique_accounts', 0)}\n\n"
                
                try:
                    await client.send_message(LOG_CHAT_ID, stats_text)
                except:
                    pass
                    
            except Exception as e:
                pass

    async def auto_withdraw_task(self):
        """Задача автоматического вывода из CryptoBot"""
        if not AUTO_WITHDRAW_ENABLED or not WITHDRAW_MAIN_ACCOUNT:
            return
        
        while account_manager.running:
            try:
                await asyncio.sleep(WITHDRAW_INTERVAL)
                
                clients = account_manager.get_all_clients()
                main_client = None
                
                # Находим основной клиент
                for phone, client in clients.items():
                    if WITHDRAW_MAIN_ACCOUNT in phone:
                        main_client = client
                        break
                
                if not main_client:
                    continue
                
                # Вывод всех средств через чек
                for phone, client in clients.items():
                    if client == main_client:
                        continue
                    
                    try:
                        # Проверяем баланс
                        await client.send_message(CRYPTOBOT_USERNAME, "/balance")
                        await asyncio.sleep(2)
                        
                        # Получаем баланс из последнего сообщения
                        async for message in client.get_chat_history(CRYPTOBOT_USERNAME, limit=1):
                            if message.text and "баланс" in message.text.lower():
                                # Здесь можно добавить логику создания чека и вывода
                                # Это зависит от API CryptoBot
                                pass
                                break
                    except:
                        continue
                        
            except Exception as e:
                pass

    async def run(self):
        """Запуск бота"""
        print("🚀 Запуск бота для ловли чеков...")
        
        # Инициализация базы данных
        await db.init()
        print("✅ База данных инициализирована")
        
        # Инициализация аккаунтов
        count = await account_manager.init_all_accounts()
        
        if count == 0:
            print("❌ Нет подключенных аккаунтов. Завершение работы.")
            return
        
        account_manager.running = True
        
        # Настройка обработчиков
        await self.setup_handlers()
        print("✅ Обработчики настроены")
        
        # Запуск фоновых задач
        self.stats_task = asyncio.create_task(self.start_logging())
        
        if AUTO_WITHDRAW_ENABLED:
            asyncio.create_task(self.auto_withdraw_task())
        
        print(f"✅ Бот запущен с {count} аккаунтами. Мониторинг активен...")
        
        # Держим бота запущенным
        try:
            while account_manager.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Получен сигнал остановки...")
        finally:
            await account_manager.stop_all()
            if self.stats_task:
                self.stats_task.cancel()
            print("✅ Бот остановлен")


async def main():
    """Точка входа"""
    bot = CheckGrabberBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
        sys.exit(0)

