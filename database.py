# database.py
import aiosqlite
import datetime
import time
from typing import Optional, List, Dict, Any

DB_PATH = "bot_data.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")

        # ===== USERS =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                total_deposit INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                last_active TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # ===== KEYS =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_code TEXT NOT NULL,
                password TEXT,
                type TEXT NOT NULL,               -- free_1h, free_3h, shop_1h, shop_12h, shop_1d, shop_1m
                duration_hours INTEGER NOT NULL,
                status TEXT DEFAULT 'available', -- available, sold, expired
                sold_to INTEGER,
                sold_at TEXT,
                expires_at TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # ===== TRANSACTIONS =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,              -- deposit, buy, admin_add, admin_sub
                amount INTEGER NOT NULL,
                description TEXT,
                key_id INTEGER,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # ===== DAILY LIMITS =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_limits (
                user_id INTEGER,
                date TEXT,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, date)
            )
        """)

        # ===== COOLDOWNS =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id INTEGER,
                key_type TEXT,                   -- 1h, 3h
                until_ts REAL,
                PRIMARY KEY (user_id, key_type)
            )
        """)

        # ===== SETTINGS =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_active', '1')")
        await db.commit()


# ==================== USER ====================
async def get_or_create_user(user_id: int) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                await db.execute(
                    "UPDATE users SET last_active = datetime('now', 'localtime') WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()
                return dict(row)

        await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()
        return {
            "user_id": user_id,
            "balance": 0,
            "total_deposit": 0
        }


async def update_balance(user_id: int, amount: int, tx_type: str, description: str = "", key_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if amount > 0 and tx_type == "deposit":
            await db.execute(
                "UPDATE users SET balance = balance + ?, total_deposit = total_deposit + ? WHERE user_id = ?",
                (amount, amount, user_id)
            )
        else:
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )

        await db.execute(
            "INSERT INTO transactions (user_id, type, amount, description, key_id) VALUES (?, ?, ?, ?, ?)",
            (user_id, tx_type, amount, description, key_id)
        )
        await db.commit()


async def get_user_history(user_id: int, limit: int = 12) -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT type, amount, description, created_at FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                sign = "+" if r["amount"] > 0 else ""
                result.append(f"{r['created_at'][5:16]} | {r['type']} {sign}{r['amount']:,}đ | {r['description'] or ''}")
            return result


# ==================== KEYS ====================
async def add_keys(key_list: List[Dict], key_type: str, duration_hours: int) -> int:
    """
    key_list = [{"key_code": "...", "password": "..."}, ...]
    """
    async with aiosqlite.connect(DB_PATH) as db:
        data = [
            (item["key_code"], item.get("password"), key_type, duration_hours)
            for item in key_list
        ]
        await db.executemany(
            "INSERT INTO keys (key_code, password, type, duration_hours) VALUES (?, ?, ?, ?)",
            data
        )
        await db.commit()
        return len(data)


async def get_available_key(key_type: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM keys WHERE type = ? AND status = 'available' ORDER BY id ASC LIMIT 1",
            (key_type,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def sell_key(key_id: int, user_id: int, duration_hours: int):
    expires_at = (datetime.datetime.now() + datetime.timedelta(hours=duration_hours)).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE keys 
               SET status = 'sold', sold_to = ?, sold_at = datetime('now', 'localtime'), expires_at = ?
               WHERE id = ?""",
            (user_id, expires_at, key_id)
        )
        await db.commit()


async def count_keys_by_type() -> Dict[str, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT type, COUNT(*) as cnt FROM keys WHERE status = 'available' GROUP BY type"
        ) as cursor:
            rows = await cursor.fetchall()
            return {r[0]: r[1] for r in rows}


# ==================== LIMITS & COOLDOWN ====================
async def check_daily_limit(user_id: int, max_limit: int = 3) -> tuple[bool, int]:
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count FROM daily_limits WHERE user_id = ? AND date = ?",
            (user_id, today)
        ) as cursor:
            row = await cursor.fetchone()
            current = row[0] if row else 0
            remaining = max(0, max_limit - current)
            return remaining > 0, remaining


async def add_daily_usage(user_id: int):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO daily_limits (user_id, date, count) VALUES (?, ?, 1)
               ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1""",
            (user_id, today)
        )
        await db.commit()


async def check_cooldown(user_id: int, key_type: str) -> tuple[bool, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT until_ts FROM cooldowns WHERE user_id = ? AND key_type = ?",
            (user_id, key_type)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return True, ""
            rem = int(row[0] - time.time())
            if rem <= 0:
                return True, ""
            return False, f"{rem // 3600}h {(rem % 3600) // 60}p"


async def set_cooldown(user_id: int, key_type: str, seconds: int):
    until = time.time() + seconds
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO cooldowns (user_id, key_type, until_ts) VALUES (?, ?, ?)
               ON CONFLICT(user_id, key_type) DO UPDATE SET until_ts = ?""",
            (user_id, key_type, until, until)
        )
        await db.commit()


# ==================== SETTINGS ====================
async def is_bot_active() -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = 'bot_active'") as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0] == "1")


async def set_bot_active(active: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE settings SET value = ? WHERE key = 'bot_active'",
            ("1" if active else "0",)
        )
        await db.commit()


# ==================== ADMIN STATS ====================
async def get_admin_stats() -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total_users = (await c.fetchone())[0]

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        async with db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'deposit' AND date(created_at) = ?",
            (today,)
        ) as c:
            deposit_today = (await c.fetchone())[0]

        month = datetime.datetime.now().strftime("%Y-%m")
        async with db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'deposit' AND strftime('%Y-%m', created_at) = ?",
            (month,)
        ) as c:
            deposit_month = (await c.fetchone())[0]

        keys_count = await count_keys_by_type()

        return {
            "total_users": total_users,
            "deposit_today": deposit_today,
            "deposit_month": deposit_month,
            "keys": keys_count
        }