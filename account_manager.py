"""
Менеджер аккаунтов для управления множественными сессиями
"""
import asyncio
import os
from typing import Dict, List, Optional
from pyrogram import Client
from pyrogram.errors import FloodWait, SessionPasswordNeeded
from config import API_ID, API_HASH, ACCOUNTS_FILE


class AccountManager:
    def __init__(self):
        self.clients: Dict[str, Client] = {}
        self.account_info: Dict[str, str] = {}  # phone -> account_info
        self.running = False

    async def load_accounts(self) -> List[str]:
        """Загрузить аккаунты из файла"""
        accounts = []
        
        if not os.path.exists(ACCOUNTS_FILE):
            print(f"⚠️ Файл {ACCOUNTS_FILE} не найден. Создайте его с аккаунтами.")
            return accounts
        
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    # Формат: api_id:api_hash:session_name:phone
                    parts = line.split(":")
                    if len(parts) >= 3:
                        accounts.append(line)
        except Exception as e:
            print(f"Ошибка при загрузке аккаунтов: {e}")
        
        return accounts

    async def create_client(self, account_line: str) -> Optional[Client]:
        """Создать клиент для аккаунта"""
        try:
            parts = account_line.split(":")
            if len(parts) < 3:
                return None
            
            api_id = int(parts[0]) if parts[0].isdigit() else API_ID
            api_hash = parts[1] if len(parts) > 1 and parts[1] else API_HASH
            session_name = parts[2]
            phone = parts[3] if len(parts) > 3 else session_name
            
            client = Client(
                name=session_name,
                api_id=api_id,
                api_hash=api_hash,
                workdir="sessions",
                no_updates=False,
                takeout=False
            )
            
            await client.start()
            
            # Получение информации об аккаунте
            me = await client.get_me()
            account_info = f"{phone} ({me.id})"
            self.account_info[phone] = account_info
            
            print(f"✅ Аккаунт подключен: {account_info}")
            return client
            
        except SessionPasswordNeeded:
            print(f"⚠️ Аккаунт {account_line} требует 2FA пароль. Пропускаем.")
            return None
        except FloodWait as e:
            print(f"⚠️ FloodWait для аккаунта {account_line}: {e.value} секунд")
            await asyncio.sleep(e.value)
            return None
        except Exception as e:
            print(f"❌ Ошибка при подключении аккаунта {account_line}: {e}")
            return None

    async def init_all_accounts(self) -> int:
        """Инициализировать все аккаунты"""
        accounts = await self.load_accounts()
        
        if not accounts:
            print("⚠️ Аккаунты не найдены!")
            return 0
        
        print(f"📱 Найдено {len(accounts)} аккаунтов. Подключаем...")
        
        # Подключаем аккаунты параллельно, но с ограничением
        semaphore = asyncio.Semaphore(10)  # Максимум 10 одновременно
        
        async def connect_account(account_line: str):
            async with semaphore:
                phone = account_line.split(":")[-1] if ":" in account_line else account_line
                client = await self.create_client(account_line)
                if client:
                    self.clients[phone] = client
                    return True
                return False
        
        tasks = [connect_account(acc) for acc in accounts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = sum(1 for r in results if r is True)
        print(f"✅ Успешно подключено {successful} из {len(accounts)} аккаунтов")
        
        return successful

    async def stop_all(self):
        """Остановить все клиенты"""
        self.running = False
        
        print("🛑 Останавливаем все аккаунты...")
        
        tasks = []
        for phone, client in self.clients.items():
            try:
                tasks.append(client.stop())
            except:
                pass
        
        await asyncio.gather(*tasks, return_exceptions=True)
        self.clients.clear()
        self.account_info.clear()
        
        print("✅ Все аккаунты остановлены")

    def get_client(self, phone: str) -> Optional[Client]:
        """Получить клиент по номеру телефона"""
        return self.clients.get(phone)

    def get_all_clients(self) -> Dict[str, Client]:
        """Получить все клиенты"""
        return self.clients.copy()

    def get_account_info(self, phone: str) -> str:
        """Получить информацию об аккаунте"""
        return self.account_info.get(phone, phone)


# Глобальный менеджер
account_manager = AccountManager()


