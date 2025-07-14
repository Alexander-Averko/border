# database.py
import aiosqlite
from typing import List, Tuple, Optional, Dict

DB_NAME = "bot_data.db"

class Database:
    def __init__(self, db_name: str):
        self.db_name = db_name

    async def initialize(self):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    is_authorized INTEGER NOT NULL DEFAULT 0
                );
            """)
            # Поле last_pos переименовано в notified_pos для ясности
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cars (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    regnum TEXT NOT NULL UNIQUE,
                    notified_pos INTEGER,
                    last_status INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                );
            """)
            await db.commit()

    async def is_user_authorized(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT is_authorized FROM users WHERE user_id = ?", (user_id,))
            result = await cursor.fetchone()
            return result[0] == 1 if result else False

    async def authorize_user(self, user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await db.execute("UPDATE users SET is_authorized = 1 WHERE user_id = ?", (user_id,))
            await db.commit()

    async def add_car(self, user_id: int, car_number: str):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT OR IGNORE INTO cars (user_id, regnum) VALUES (?, ?)", (user_id, car_number))
            await db.commit()

    async def get_user_cars(self, user_id: int) -> List[str]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT regnum FROM cars WHERE user_id = ?", (user_id,))
            return [row[0] for row in await cursor.fetchall()]

    async def delete_all_cars(self, user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("DELETE FROM cars WHERE user_id = ?", (user_id,))
            await db.commit()
            
    async def get_car_state(self, car_number: str) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT notified_pos, last_status FROM cars WHERE regnum = ?", (car_number,))
            row = await cursor.fetchone()
            return {"notified_pos": row[0], "last_status": row[1]} if row else None

    async def update_car_state(self, car_number: str, pos: Optional[int], status: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE cars SET notified_pos = ?, last_status = ? WHERE regnum = ?", (pos, status, car_number))
            await db.commit()
            
    async def update_car_status_only(self, car_number: str, status: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE cars SET last_status = ? WHERE regnum = ?", (status, car_number))
            await db.commit()

    async def remove_car(self, car_number: str):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("DELETE FROM cars WHERE regnum = ?", (car_number,))
            await db.commit()

    async def get_all_tracked_cars(self) -> List[Tuple[int, str]]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT user_id, regnum FROM cars")
            return await cursor.fetchall()

db = Database(DB_NAME)