"""
Модуль для логирования
"""
from datetime import datetime
from colorama import init, Fore, Style
from config import LOG_CHAT_ID
from account_manager import account_manager

init(autoreset=True)


class Logger:
    @staticmethod
    def info(message: str):
        """Информационное сообщение"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{Fore.CYAN}[{timestamp}]{Style.RESET_ALL} {message}")
    
    @staticmethod
    def success(message: str):
        """Сообщение об успехе"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{Fore.GREEN}[{timestamp}] ✅{Style.RESET_ALL} {message}")
    
    @staticmethod
    def warning(message: str):
        """Предупреждение"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{Fore.YELLOW}[{timestamp}] ⚠️{Style.RESET_ALL} {message}")
    
    @staticmethod
    def error(message: str):
        """Ошибка"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{Fore.RED}[{timestamp}] ❌{Style.RESET_ALL} {message}")
    
    @staticmethod
    async def log_to_telegram(message: str, client=None):
        """Отправить лог в Telegram"""
        if not LOG_CHAT_ID:
            return
        
        if not client:
            clients = account_manager.get_all_clients()
            if not clients:
                return
            client = list(clients.values())[0]
        
        try:
            await client.send_message(LOG_CHAT_ID, message)
        except:
            pass
    
    @staticmethod
    async def log_activated_check(bot_type: str, check_code: str, amount: float,
                                  currency: str, account_info: str, source_chat: str):
        """Логировать активированный чек"""
        message = (
            f"💰 Чек активирован!\n\n"
            f"Бот: {bot_type.upper()}\n"
            f"Код: {check_code[:20]}...\n"
            f"Сумма: {amount} {currency}\n"
            f"Аккаунт: {account_info}\n"
            f"Источник: {source_chat}"
        )
        
        Logger.success(f"Чек активирован: {bot_type} - {amount} {currency}")
        
        if LOG_CHAT_ID:
            await Logger.log_to_telegram(message)


# Глобальный логгер
logger = Logger()


