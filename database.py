"""
Модуль для работы с базой данных
"""
import aiosqlite
import asyncio
from datetime import datetime
from typing import Optional, List, Dict
from config import DB_PATH


class Database:
    def __init__(self):
        self.db_path = DB_PATH
        self.initialized = False

    async def init(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_code TEXT UNIQUE NOT NULL,
                    bot_type TEXT NOT NULL,
                    amount REAL,
                    currency TEXT,
                    activated_by TEXT,
                    source_chat TEXT,
                    message_id INTEGER,
                    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'activated'
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_phone TEXT,
                    bot_type TEXT,
                    checks_count INTEGER DEFAULT 0,
                    total_amount REAL DEFAULT 0,
                    currency TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(account_phone, bot_type)
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_check_code ON checks(check_code)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_stats_account ON stats(account_phone, bot_type)
            """)
            
            await db.commit()
        self.initialized = True

    async def add_check(self, check_code: str, bot_type: str, amount: Optional[float] = None,
                       currency: Optional[str] = None, activated_by: Optional[str] = None,
                       source_chat: Optional[str] = None, message_id: Optional[int] = None):
        """Добавить активированный чек в базу"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR IGNORE INTO checks 
                    (check_code, bot_type, amount, currency, activated_by, source_chat, message_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (check_code, bot_type, amount, currency, activated_by, source_chat, message_id))
                await db.commit()
                return True
        except Exception as e:
            print(f"Ошибка при добавлении чека: {e}")
            return False

    async def check_exists(self, check_code: str) -> bool:
        """Проверить, существует ли чек в базе"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM checks WHERE check_code = ?", (check_code,)
            ) as cursor:
                return await cursor.fetchone() is not None

    async def update_stats(self, account_phone: str, bot_type: str, amount: float = 0, currency: str = ""):
        """Обновить статистику аккаунта"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO stats (account_phone, bot_type, checks_count, total_amount, currency)
                VALUES (?, ?, 0, 0, ?)
            """, (account_phone, bot_type, currency))
            await db.execute("""
                UPDATE stats SET
                    checks_count = checks_count + 1,
                    total_amount = total_amount + ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE account_phone = ? AND bot_type = ?
            """, (amount, account_phone, bot_type))
            await db.commit()

    async def get_stats(self, account_phone: Optional[str] = None) -> List[Dict]:
        """Получить статистику"""
        async with aiosqlite.connect(self.db_path) as db:
            if account_phone:
                query = "SELECT * FROM stats WHERE account_phone = ?"
                params = (account_phone,)
            else:
                query = "SELECT * FROM stats ORDER BY checks_count DESC"
                params = ()
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def get_total_stats(self) -> Dict:
        """Получить общую статистику"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT 
                    COUNT(*) as total_checks,
                    SUM(amount) as total_amount,
                    bot_type,
                    COUNT(DISTINCT activated_by) as unique_accounts
                FROM checks
                GROUP BY bot_type
            """) as cursor:
                rows = await cursor.fetchall()
                result = {}
                for row in rows:
                    result[row[2]] = {
                        "total_checks": row[0],
                        "total_amount": row[1] or 0,
                        "unique_accounts": row[3]
                    }
                return result


# Глобальный экземпляр базы данных
db = Database()

