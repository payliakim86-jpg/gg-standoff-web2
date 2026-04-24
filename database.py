# database.py
import sqlite3
import json
import random
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from config import ADMINS, SELL_PRICES, EXCHANGE_RATE, MIN_WITHDRAWAL_UAH

class Database:
    def __init__(self, db_name="bot_database.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.create_tables()
        self._add_missing_columns()
        self._cache_table_columns()

    def _cache_table_columns(self):
        self.game_stats_columns = self._get_table_columns('game_stats')

    def _get_table_columns(self, table: str) -> set:
        self.cursor.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in self.cursor.fetchall()}

    def _add_missing_columns(self):
        users_columns = {
            "last_activity": "TEXT",
            "free_cases": "INTEGER DEFAULT 0",
            "biggest_win": "INTEGER DEFAULT 0",
            "rare_special_count": "INTEGER DEFAULT 0",
            "notify_bonus": "INTEGER DEFAULT 1",
            "notify_market": "INTEGER DEFAULT 1"
        }
        for col, definition in users_columns.items():
            self._add_column_if_not_exists("users", col, definition)

        market_columns = {
            "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP"
        }
        for col, definition in market_columns.items():
            self._add_column_if_not_exists("market_listings", col, definition)

        game_stats_columns = {
            "total_bet": "INTEGER DEFAULT 0",
            "total_win": "INTEGER DEFAULT 0",
            "games_played": "INTEGER DEFAULT 0",
            "profit": "INTEGER DEFAULT 0"
        }
        for col, definition in game_stats_columns.items():
            self._add_column_if_not_exists("game_stats", col, definition)

        payments_columns = {
            "confirmed_at": "TEXT"
        }
        for col, definition in payments_columns.items():
            self._add_column_if_not_exists("payments", col, definition)

        self._ensure_last_activity_filled()

    def _add_column_if_not_exists(self, table: str, column: str, definition: str):
        try:
            self.cursor.execute(f"SELECT {column} FROM {table} LIMIT 1")
        except sqlite3.OperationalError:
            self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            self.conn.commit()
            print(f"Додано колонку {column} до таблиці {table}")

    def _ensure_last_activity_filled(self):
        try:
            self.cursor.execute("UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE last_activity IS NULL")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass

    def create_tables(self):
        # Користувачі
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 1000,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                cases_opened INTEGER DEFAULT 0,
                duels_won INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                biggest_win INTEGER DEFAULT 0,
                last_daily_bonus TEXT,
                rare_special_count INTEGER DEFAULT 0,
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
                free_cases INTEGER DEFAULT 0,
                notify_bonus INTEGER DEFAULT 1,
                notify_market INTEGER DEFAULT 1
            )
        ''')
        # Інвентар
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                skin_name TEXT,
                rarity TEXT,
                case_name TEXT,
                case_price INTEGER,
                obtained_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        # Маркет
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER,
                skin_id INTEGER UNIQUE,
                skin_name TEXT,
                rarity TEXT,
                price INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(seller_id) REFERENCES users(user_id),
                FOREIGN KEY(skin_id) REFERENCES inventory(id)
            )
        ''')
        # Дуелі
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS duels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                opponent_id INTEGER,
                bet_amount INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                accepted_at TEXT,
                winner_id INTEGER,
                FOREIGN KEY(creator_id) REFERENCES users(user_id),
                FOREIGN KEY(opponent_id) REFERENCES users(user_id)
            )
        ''')
        # Платежі
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount_uah INTEGER,
                amount_coins INTEGER,
                payment_method TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                confirmed_by INTEGER,
                confirmed_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        # Промокоди
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                reward INTEGER,
                max_uses INTEGER,
                used_count INTEGER DEFAULT 0,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS promocode_uses (
                user_id INTEGER,
                code TEXT,
                used_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, code)
            )
        ''')
        # Рідкісні випадіння
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS rare_drops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                skin_name TEXT,
                rarity TEXT,
                case_name TEXT,
                dropped_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notified BOOLEAN DEFAULT 0
            )
        ''')
        # Денна статистика
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                user_id INTEGER,
                date TEXT,
                cases_opened INTEGER DEFAULT 0,
                duels_won INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                biggest_win INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, date)
            )
        ''')
        # Модератори
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS moderators (
                user_id INTEGER PRIMARY KEY
            )
        ''')
        # Турніри
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tournaments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                start_time TEXT,
                end_time TEXT,
                prize_pool INTEGER,
                status TEXT DEFAULT 'pending'
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tournament_participants (
                tournament_id INTEGER,
                user_id INTEGER,
                points INTEGER DEFAULT 0,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(tournament_id, user_id)
            )
        ''')
        # Приватні турніри
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS private_tournaments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                name TEXT,
                entry_fee INTEGER,
                max_participants INTEGER,
                duration_hours INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                start_time TEXT,
                end_time TEXT,
                prize_pool INTEGER
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS private_tournament_participants (
                tournament_id INTEGER,
                user_id INTEGER,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                points INTEGER DEFAULT 0,
                PRIMARY KEY(tournament_id, user_id)
            )
        ''')
        # Пропозиції
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                status TEXT DEFAULT 'new',
                admin_reply TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Друзі
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS friend_requests (
                from_id INTEGER,
                to_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(from_id, to_id)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS friends (
                user_id INTEGER,
                friend_id INTEGER,
                since TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, friend_id)
            )
        ''')
        # Ігри (статистика)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_stats (
                user_id INTEGER,
                game_type TEXT,
                total_bet INTEGER DEFAULT 0,
                total_win INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                profit INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, game_type)
            )
        ''')
        # Безкоштовні кейси
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_free_cases (
                user_id INTEGER,
                case_key TEXT,
                remaining INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, case_key)
            )
        ''')
        # Виведення коштів
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                bank TEXT,
                card TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                confirmed_by INTEGER,
                confirmed_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        # Заноси
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS big_wins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                game_type TEXT,
                bet INTEGER,
                win_amount INTEGER,
                multiplier REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notified BOOLEAN DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        self.conn.commit()

    # ---------- Основні методи ----------
    def get_or_create_user(self, user_id: int, username: Optional[str]) -> dict:
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        if row:
            if username:
                self.cursor.execute("UPDATE users SET username = ?, last_activity = CURRENT_TIMESTAMP WHERE user_id = ?", (username, user_id))
                self.conn.commit()
            return dict(row)
        else:
            self.cursor.execute(
                "INSERT INTO users (user_id, username, balance, last_activity) VALUES (?, ?, 1000, CURRENT_TIMESTAMP)",
                (user_id, username)
            )
            self.conn.commit()
            self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return dict(self.cursor.fetchone())

    def user_exists(self, user_id: int) -> bool:
        self.cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone() is not None

    def get_user_balance(self, user_id: int) -> int:
        self.cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        return row['balance'] if row else 0

    def update_balance(self, user_id: int, amount: int):
        self.cursor.execute("UPDATE users SET balance = balance + ?, last_activity = CURRENT_TIMESTAMP WHERE user_id = ?", (amount, user_id))
        self.conn.commit()

    def get_user_level_info(self, user_id: int) -> dict:
        self.cursor.execute("SELECT level, xp FROM users WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        if not row:
            return {'level': 1, 'xp': 0, 'discount': 0}
        level = row['level']
        xp = row['xp']
        discount = min(level * 2, 30)
        return {'level': level, 'xp': xp, 'discount': discount}

    def add_xp(self, user_id: int, xp: int) -> tuple[bool, int, int]:
        self.cursor.execute("SELECT level, xp FROM users WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        if not row:
            return False, 1, 0
        level, current_xp = row['level'], row['xp']
        new_xp = current_xp + xp
        leveled_up = False
        while new_xp >= 100:
            level += 1
            new_xp -= 100
            leveled_up = True
        self.cursor.execute("UPDATE users SET level = ?, xp = ? WHERE user_id = ?", (level, new_xp, user_id))
        self.conn.commit()
        discount = min(level * 2, 30)
        return leveled_up, level, discount

    def get_user_inventory(self, user_id: int) -> list:
        self.cursor.execute("SELECT * FROM inventory WHERE user_id = ? ORDER BY obtained_at DESC", (user_id,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def get_skin_by_id(self, skin_id: int, user_id: int) -> Optional[dict]:
        self.cursor.execute("SELECT * FROM inventory WHERE id = ? AND user_id = ?", (skin_id, user_id))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def remove_skin_from_inventory(self, skin_id: int, user_id: int) -> bool:
        self.cursor.execute("DELETE FROM inventory WHERE id = ? AND user_id = ?", (skin_id, user_id))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def add_skin_to_inventory(self, user_id: int, skin_name: str, rarity: str, case_name: str, case_price: int, obtained_at: str = None) -> int:
        if not obtained_at:
            obtained_at = datetime.now().isoformat()
        self.cursor.execute(
            "INSERT INTO inventory (user_id, skin_name, rarity, case_name, case_price, obtained_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, skin_name, rarity, case_name, case_price, obtained_at)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def log_sale(self, user_id: int, skin_name: str, rarity: str, price: int, case_price: int):
        pass

    def get_profile_stats(self, user_id: int) -> dict:
        user = self.get_or_create_user(user_id, None)
        inv = self.get_user_inventory(user_id)
        most_expensive = None
        if inv:
            most_expensive = max(inv, key=lambda x: x['case_price'])
        transactions = {
            'purchases': {'count': 0, 'total_value': 0},
            'sales': {'count': 0, 'total_value': 0},
            'trades': {'sent': 0, 'received': 0},
            'market': {'purchases_count': 0, 'purchases_value': 0, 'sales_count': 0, 'sales_value': 0}
        }
        level_info = self.get_user_level_info(user_id)
        xp_to_next = 100 - user['xp'] if user['xp'] < 100 else 0
        return {
            'user_id': user_id,
            'username': user['username'],
            'balance': user['balance'],
            'level': user['level'],
            'xp': user['xp'],
            'discount': level_info['discount'],
            'xp_to_next': xp_to_next,
            'cases_opened': user['cases_opened'],
            'most_expensive_skin': most_expensive,
            'transactions': transactions
        }

    # ---------- Кейси ----------
    def open_multiple_cases(self, user_id: int, case_key: str, case: dict, count: int, discount: int, use_free: bool = False) -> dict:
        price_per_case = case['price']
        if use_free:
            if not self.use_free_case(user_id, case_key, count):
                return {"success": False, "message": "❌ Недостатньо безкоштовних спроб."}
        else:
            total_cost = price_per_case * count
            total_cost_discounted = int(total_cost * (100 - discount) / 100)
            if self.get_user_balance(user_id) < total_cost_discounted:
                return {"success": False, "message": "❌ Недостатньо коштів"}
            self.update_balance(user_id, -total_cost_discounted)

        results = []
        total_xp = 0
        for _ in range(count):
            skin_name, rarity = self._open_single_case(case_key)
            sell_price = int(price_per_case * SELL_PRICES.get(rarity, 0.3))
            skin_id = self.add_skin_to_inventory(user_id, skin_name, rarity, case['name'], price_per_case)
            results.append({
                'skin_name': skin_name,
                'rarity': rarity,
                'emoji': self._get_rarity_emoji(rarity),
                'sell_price': sell_price,
                'skin_id': skin_id
            })
            total_xp += 10
            self.cursor.execute("UPDATE users SET cases_opened = cases_opened + 1 WHERE user_id = ?", (user_id,))
            if rarity in ['Covert', 'Rare Special']:
                self.log_rare_drop(user_id, skin_name, rarity, case['name'])
        self.conn.commit()
        leveled_up, new_level, new_discount = self.add_xp(user_id, total_xp)
        return {
            "success": True,
            "results": results,
            "total_xp": total_xp,
            "leveled_up": leveled_up,
            "new_level": new_level if leveled_up else None,
            "new_discount": new_discount if leveled_up else None
        }

    def _open_single_case(self, case_name: str) -> tuple[str, str]:
        from main import calculate_rarity, SKINS
        rarity = calculate_rarity(case_name)
        skins_list = SKINS.get(rarity, SKINS["Consumer Grade"])
        skin_name = random.choice(skins_list)
        return skin_name, rarity

    def _get_rarity_emoji(self, rarity: str) -> str:
        from keyboards import get_rarity_emoji
        return get_rarity_emoji(rarity)

    def get_free_cases_left(self, user_id: int, case_key: str = "Standard Case") -> int:
        return self.get_user_free_cases(user_id, case_key)

    def log_rare_drop(self, user_id: int, skin_name: str, rarity: str, case_name: str):
        self.cursor.execute(
            "INSERT INTO rare_drops (user_id, skin_name, rarity, case_name) VALUES (?, ?, ?, ?)",
            (user_id, skin_name, rarity, case_name)
        )
        self.conn.commit()
        if rarity == 'Rare Special':
            self.cursor.execute("UPDATE users SET rare_special_count = rare_special_count + 1 WHERE user_id = ?", (user_id,))
            self.conn.commit()

    # ---------- Безкоштовні кейси ----------
    def get_user_free_cases(self, user_id: int, case_key: str) -> int:
        self.cursor.execute(
            "SELECT remaining FROM user_free_cases WHERE user_id = ? AND case_key = ?",
            (user_id, case_key)
        )
        row = self.cursor.fetchone()
        return row['remaining'] if row else 0

    def use_free_case(self, user_id: int, case_key: str, count: int = 1) -> bool:
        self.cursor.execute(
            "UPDATE user_free_cases SET remaining = remaining - ? WHERE user_id = ? AND case_key = ? AND remaining >= ?",
            (count, user_id, case_key, count)
        )
        self.conn.commit()
        return self.cursor.rowcount > 0

    def add_free_cases_to_all(self, case_key: str, amount: int) -> int:
        self.cursor.execute("SELECT user_id FROM users")
        users = self.cursor.fetchall()
        count = 0
        for user in users:
            user_id = user['user_id']
            self.cursor.execute('''
                INSERT INTO user_free_cases (user_id, case_key, remaining)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, case_key) DO UPDATE SET
                    remaining = remaining + ?
            ''', (user_id, case_key, amount, amount))
            count += 1
        self.conn.commit()
        return count

    # ---------- Щоденний бонус ----------
    def check_and_claim_login_bonus(self, user_id: int) -> dict:
        return {"success": False, "message": ""}

    def get_last_daily_bonus(self, user_id: int) -> Optional[str]:
        self.cursor.execute("SELECT last_daily_bonus FROM users WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        return row['last_daily_bonus'] if row else None

    def update_last_daily_bonus(self, user_id: int, iso_time: str):
        self.cursor.execute("UPDATE users SET last_daily_bonus = ? WHERE user_id = ?", (iso_time, user_id))
        self.conn.commit()

    # ---------- Денна статистика ----------
    def update_daily_stats(self, user_id: int, stat: str, value: int):
        column_map = {
            'cases': 'cases_opened',
            'games': 'games_played',
            'duels': 'duels_won',
            'biggest_win': 'biggest_win'
        }
        column = column_map.get(stat)
        if not column:
            print(f"Помилка: невідома статистика '{stat}'")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        self.cursor.execute('''
            INSERT INTO daily_stats (user_id, date, cases_opened, duels_won, games_played, biggest_win)
            VALUES (?, ?, 0, 0, 0, 0)
            ON CONFLICT(user_id, date) DO NOTHING
        ''', (user_id, today))
        self.conn.commit()
        self.cursor.execute(f"UPDATE daily_stats SET {column} = {column} + ? WHERE user_id = ? AND date = ?", (value, user_id, today))
        self.conn.commit()

    # ---------- Турніри ----------
    def get_active_tournament(self) -> Optional[dict]:
        now = datetime.now().isoformat()
        self.cursor.execute("SELECT * FROM tournaments WHERE status = 'active' AND start_time <= ? AND end_time >= ?", (now, now))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def get_pending_tournament(self) -> Optional[dict]:
        now = datetime.now().isoformat()
        self.cursor.execute("SELECT * FROM tournaments WHERE status = 'pending' AND start_time > ?", (now,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def join_tournament(self, user_id: int, tournament_id: int) -> bool:
        try:
            self.cursor.execute("INSERT INTO tournament_participants (tournament_id, user_id) VALUES (?, ?)", (tournament_id, user_id))
            self.conn.commit()
            return True
        except:
            return False

    def get_tournament_leaderboard(self, tournament_id: int, limit: int) -> list:
        self.cursor.execute('''
            SELECT tp.user_id, u.username, tp.points
            FROM tournament_participants tp
            JOIN users u ON tp.user_id = u.user_id
            WHERE tp.tournament_id = ?
            ORDER BY tp.points DESC
            LIMIT ?
        ''', (tournament_id, limit))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def check_tournaments(self):
        pass

    # ---------- Маркет ----------
    def get_market_listings(self, offset: int, limit: int) -> list:
        self.cursor.execute('''
            SELECT ml.*, i.skin_name, i.rarity
            FROM market_listings ml
            JOIN inventory i ON ml.skin_id = i.id
            ORDER BY ml.created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def list_skin_on_market(self, seller_id: int, skin_id: int, price: int) -> dict:
        self.cursor.execute("SELECT 1 FROM inventory WHERE id = ? AND user_id = ?", (skin_id, seller_id))
        if not self.cursor.fetchone():
            return {"success": False, "message": "❌ Скін не знайдено у вашому інвентарі"}
        self.cursor.execute("SELECT 1 FROM market_listings WHERE skin_id = ?", (skin_id,))
        if self.cursor.fetchone():
            return {"success": False, "message": "❌ Цей скін вже виставлено на продаж"}
        self.cursor.execute(
            "INSERT INTO market_listings (seller_id, skin_id, skin_name, rarity, price) VALUES (?, ?, (SELECT skin_name FROM inventory WHERE id = ?), (SELECT rarity FROM inventory WHERE id = ?), ?)",
            (seller_id, skin_id, skin_id, skin_id, price)
        )
        self.conn.commit()
        return {"success": True, "message": f"✅ Скін виставлено на продаж за {price} монет"}

    def buy_from_market(self, buyer_id: int, listing_id: int) -> dict:
        self.cursor.execute("SELECT * FROM market_listings WHERE id = ?", (listing_id,))
        listing = self.cursor.fetchone()
        if not listing:
            return {"success": False, "message": "❌ Лот не знайдено"}
        listing = dict(listing)
        if listing['seller_id'] == buyer_id:
            return {"success": False, "message": "❌ Не можна купити власний лот"}
        balance = self.get_user_balance(buyer_id)
        if balance < listing['price']:
            return {"success": False, "message": "❌ Недостатньо коштів"}
        self.cursor.execute("UPDATE inventory SET user_id = ? WHERE id = ?", (buyer_id, listing['skin_id']))
        self.update_balance(buyer_id, -listing['price'])
        self.update_balance(listing['seller_id'], listing['price'])
        self.cursor.execute("DELETE FROM market_listings WHERE id = ?", (listing_id,))
        self.conn.commit()
        return {"success": True, "skin_name": listing['skin_name'], "price": listing['price']}

    def cancel_market_listing(self, seller_id: int, listing_id: int) -> bool:
        self.cursor.execute("DELETE FROM market_listings WHERE id = ? AND seller_id = ?", (listing_id, seller_id))
        self.conn.commit()
        return self.cursor.rowcount > 0

    # ---------- Дуелі ----------
    def get_active_duels(self) -> list:
        self.cursor.execute("SELECT * FROM duels WHERE status = 'pending' ORDER BY created_at DESC")
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def create_duel(self, creator_id: int, bet: int) -> dict:
        balance = self.get_user_balance(creator_id)
        if balance < bet:
            return {"success": False, "message": "❌ Недостатньо коштів"}
        self.update_balance(creator_id, -bet)
        self.cursor.execute(
            "INSERT INTO duels (creator_id, bet_amount, status) VALUES (?, ?, 'pending')",
            (creator_id, bet)
        )
        self.conn.commit()
        duel_id = self.cursor.lastrowid
        return {"success": True, "duel_id": duel_id}

    def accept_duel(self, duel_id: int, opponent_id: int) -> dict:
        self.cursor.execute("SELECT * FROM duels WHERE id = ? AND status = 'pending'", (duel_id,))
        duel = self.cursor.fetchone()
        if not duel:
            return {"success": False, "message": "❌ Дуель не знайдена або вже прийнята"}
        duel = dict(duel)
        if duel['creator_id'] == opponent_id:
            return {"success": False, "message": "❌ Не можна прийняти власну дуель"}
        balance = self.get_user_balance(opponent_id)
        if balance < duel['bet_amount']:
            return {"success": False, "message": "❌ Недостатньо коштів"}
        self.update_balance(opponent_id, -duel['bet_amount'])
        self.cursor.execute(
            "UPDATE duels SET opponent_id = ?, status = 'accepted', accepted_at = CURRENT_TIMESTAMP WHERE id = ?",
            (opponent_id, duel_id)
        )
        self.conn.commit()
        return {"success": True}

    def fight_duel(self, duel_id: int) -> dict:
        self.cursor.execute("SELECT * FROM duels WHERE id = ? AND status = 'accepted'", (duel_id,))
        duel = self.cursor.fetchone()
        if not duel:
            return {"success": False, "message": "❌ Дуель не знайдена"}
        duel = dict(duel)
        winner_id = random.choice([duel['creator_id'], duel['opponent_id']])
        total_bank = duel['bet_amount'] * 2
        self.update_balance(winner_id, total_bank)
        self.cursor.execute(
            "UPDATE duels SET status = 'completed', winner_id = ? WHERE id = ?",
            (winner_id, duel_id)
        )
        self.conn.commit()
        winner_name = self.get_or_create_user(winner_id, None)['username'] or str(winner_id)
        return {"success": True, "winner_id": winner_id, "winner_name": winner_name, "total_bank": total_bank}

    # ---------- Трейди ----------
    def trade_skin(self, from_id: int, to_id: int, skin_id: int) -> dict:
        self.cursor.execute("SELECT 1 FROM inventory WHERE id = ? AND user_id = ?", (skin_id, from_id))
        if not self.cursor.fetchone():
            return {"success": False, "message": "❌ Скін не знайдено у вашому інвентарі"}
        self.cursor.execute("UPDATE inventory SET user_id = ? WHERE id = ?", (to_id, skin_id))
        self.conn.commit()
        return {"success": True, "message": f"✅ Скін передано користувачу {to_id}"}

    # ---------- Модератори ----------
    def is_moderator(self, user_id: int) -> bool:
        self.cursor.execute("SELECT 1 FROM moderators WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone() is not None

    def add_moderator(self, user_id: int):
        self.cursor.execute("INSERT OR IGNORE INTO moderators (user_id) VALUES (?)", (user_id,))
        self.conn.commit()

    def remove_moderator(self, user_id: int) -> bool:
        self.cursor.execute("DELETE FROM moderators WHERE user_id = ?", (user_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_moderators(self) -> list:
        self.cursor.execute('''
            SELECT m.user_id, u.username
            FROM moderators m
            LEFT JOIN users u ON m.user_id = u.user_id
        ''')
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    # ---------- Статистика ----------
    def get_total_users_count(self) -> int:
        self.cursor.execute("SELECT COUNT(*) FROM users")
        return self.cursor.fetchone()[0]

    def get_total_skins_count(self) -> int:
        self.cursor.execute("SELECT COUNT(*) FROM inventory")
        return self.cursor.fetchone()[0]

    def get_skins_rarity_stats(self) -> dict:
        self.cursor.execute("SELECT rarity, COUNT(*) as cnt FROM inventory GROUP BY rarity")
        rows = self.cursor.fetchall()
        return {row['rarity']: row['cnt'] for row in rows}

    def get_all_users(self) -> list:
        self.cursor.execute("SELECT user_id, username, balance FROM users ORDER BY user_id")
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def get_top_balance(self, limit: int) -> list:
        self.cursor.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def get_top_rare_special(self, limit: int) -> list:
        self.cursor.execute("SELECT user_id, username, rare_special_count FROM users WHERE rare_special_count > 0 ORDER BY rare_special_count DESC LIMIT ?", (limit,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def get_top_daily(self, column: str, limit: int) -> list:
        today = datetime.now().strftime("%Y-%m-%d")
        self.cursor.execute(f'''
            SELECT ds.user_id, u.username, ds.{column}
            FROM daily_stats ds
            JOIN users u ON ds.user_id = u.user_id
            WHERE ds.date = ?
            ORDER BY ds.{column} DESC
            LIMIT ?
        ''', (today, limit))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def get_top_alltime(self, column: str, limit: int) -> list:
        self.cursor.execute(f"SELECT user_id, username, {column} FROM users ORDER BY {column} DESC LIMIT ?", (limit,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    # ---------- Платежі ----------
    def create_payment(self, user_id: int, amount_uah: int, method: str) -> dict:
        amount_coins = amount_uah * EXCHANGE_RATE
        self.cursor.execute(
            "INSERT INTO payments (user_id, amount_uah, amount_coins, payment_method) VALUES (?, ?, ?, ?)",
            (user_id, amount_uah, amount_coins, method)
        )
        self.conn.commit()
        payment_id = self.cursor.lastrowid
        return {"success": True, "payment_id": payment_id, "amount_coins": amount_coins}

    def get_pending_payments(self) -> list:
        self.cursor.execute("SELECT * FROM payments WHERE status = 'pending' ORDER BY created_at DESC")
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def get_payment_by_id(self, payment_id: int) -> Optional[dict]:
        self.cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def confirm_payment(self, payment_id: int, admin_id: int) -> dict:
        self.cursor.execute("SELECT * FROM payments WHERE id = ? AND status = 'pending'", (payment_id,))
        payment = self.cursor.fetchone()
        if not payment:
            return {"success": False, "message": "❌ Платіж не знайдено або вже оброблено"}
        payment = dict(payment)
        self.update_balance(payment['user_id'], payment['amount_coins'])
        self.cursor.execute(
            "UPDATE payments SET status = 'completed', confirmed_by = ?, confirmed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (admin_id, payment_id)
        )
        self.conn.commit()
        return {"success": True, "message": f"✅ Платіж #{payment_id} підтверджено"}

    def cancel_payment(self, payment_id: int, admin_id: int) -> dict:
        self.cursor.execute(
            "UPDATE payments SET status = 'cancelled', confirmed_by = ?, confirmed_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending'",
            (admin_id, payment_id)
        )
        self.conn.commit()
        if self.cursor.rowcount:
            return {"success": True, "message": f"❌ Платіж #{payment_id} скасовано"}
        return {"success": False, "message": "❌ Платіж не знайдено"}

    def get_user_payments(self, user_id: int, limit: int) -> list:
        self.cursor.execute("SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    # ---------- Промокоди ----------
    def create_promocode(self, code: str, reward: int, max_uses: int, created_by: int) -> bool:
        try:
            self.cursor.execute(
                "INSERT INTO promocodes (code, reward, max_uses, created_by) VALUES (?, ?, ?, ?)",
                (code, reward, max_uses, created_by)
            )
            self.conn.commit()
            return True
        except:
            return False

    def use_promocode(self, user_id: int, code: str) -> dict:
        self.cursor.execute("SELECT * FROM promocodes WHERE code = ?", (code,))
        promo = self.cursor.fetchone()
        if not promo:
            return {"success": False, "message": "❌ Промокод не знайдено"}
        promo = dict(promo)
        if promo['used_count'] >= promo['max_uses']:
            return {"success": False, "message": "❌ Промокод вже використано максимальну кількість разів"}
        self.cursor.execute("SELECT 1 FROM promocode_uses WHERE user_id = ? AND code = ?", (user_id, code))
        if self.cursor.fetchone():
            return {"success": False, "message": "❌ Ви вже використовували цей промокод"}
        self.update_balance(user_id, promo['reward'])
        self.cursor.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE code = ?", (code,))
        self.cursor.execute("INSERT INTO promocode_uses (user_id, code) VALUES (?, ?)", (user_id, code))
        self.conn.commit()
        return {"success": True, "message": f"✅ Промокод активовано! Отримано {promo['reward']} монет"}

    def get_all_promocodes(self) -> list:
        self.cursor.execute("SELECT * FROM promocodes ORDER BY created_at DESC")
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    # ---------- Рідкісні випадіння ----------
    def get_unnotified_rare_drops(self) -> list:
        self.cursor.execute("SELECT * FROM rare_drops WHERE notified = 0")
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def mark_rare_drop_notified(self, drop_id: int):
        self.cursor.execute("UPDATE rare_drops SET notified = 1 WHERE id = ?", (drop_id,))
        self.conn.commit()

    # ---------- Ігри ----------
    def record_game_result(self, user_id: int, game_type: str, bet: int, win: int):
        cols = self.game_stats_columns
        bet_cols = [col for col in ['bet', 'total_bet', 'bet_amount'] if col in cols]
        win_cols = [col for col in ['win', 'total_win', 'win_amount'] if col in cols]
        games_col = 'games_played' if 'games_played' in cols else None
        profit_col = 'profit' if 'profit' in cols else None

        self.cursor.execute(
            "SELECT 1 FROM game_stats WHERE user_id = ? AND game_type = ?",
            (user_id, game_type)
        )
        exists = self.cursor.fetchone()

        if exists:
            set_clauses = []
            params = []
            for col in bet_cols:
                set_clauses.append(f"{col} = {col} + ?")
                params.append(bet)
            for col in win_cols:
                set_clauses.append(f"{col} = {col} + ?")
                params.append(win)
            if games_col:
                set_clauses.append(f"{games_col} = {games_col} + 1")
            if profit_col:
                set_clauses.append(f"{profit_col} = {profit_col} + ?")
                params.append(win - bet)
            if not set_clauses:
                return
            params.extend([user_id, game_type])
            sql = f"UPDATE game_stats SET {', '.join(set_clauses)} WHERE user_id = ? AND game_type = ?"
            self.cursor.execute(sql, params)
        else:
            insert_cols = ['user_id', 'game_type']
            values = [user_id, game_type]
            for col in bet_cols:
                insert_cols.append(col)
                values.append(bet)
            for col in win_cols:
                insert_cols.append(col)
                values.append(win)
            if games_col:
                insert_cols.append(games_col)
                values.append(1)
            if profit_col:
                insert_cols.append(profit_col)
                values.append(win - bet)
            if not insert_cols:
                return
            placeholders = ', '.join(['?' for _ in values])
            sql = f"INSERT INTO game_stats ({', '.join(insert_cols)}) VALUES ({placeholders})"
            self.cursor.execute(sql, values)
        self.conn.commit()

    def get_game_stats(self, user_id: int) -> dict:
        self.cursor.execute("SELECT * FROM game_stats WHERE user_id = ?", (user_id,))
        rows = self.cursor.fetchall()
        stats = {"total_games": 0, "total_profit": 0, "by_game": {}}
        for row in rows:
            r = dict(row)
            bet_col = next((c for c in ['total_bet', 'bet', 'bet_amount'] if c in r), None)
            win_col = next((c for c in ['total_win', 'win', 'win_amount'] if c in r), None)
            games_col = 'games_played' if 'games_played' in r else None
            profit_col = 'profit' if 'profit' in r else None

            total_bet = r[bet_col] if bet_col else 0
            total_win = r[win_col] if win_col else 0
            games_played = r[games_col] if games_col else 0
            profit = r[profit_col] if profit_col else (total_win - total_bet)

            stats["by_game"][r['game_type']] = {
                "games": games_played,
                "total_bet": total_bet,
                "total_win": total_win,
                "profit": profit
            }
            stats["total_games"] += games_played
            stats["total_profit"] += profit
        return stats

    # ---------- Заноси ----------
    def log_big_win(self, user_id: int, game_type: str, bet: int, win_amount: int) -> int:
        multiplier = win_amount / bet if bet > 0 else 0
        self.cursor.execute('''
            INSERT INTO big_wins (user_id, game_type, bet, win_amount, multiplier)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, game_type, bet, win_amount, multiplier))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_unnotified_big_wins(self) -> list:
        self.cursor.execute('''
            SELECT w.*, u.username 
            FROM big_wins w
            LEFT JOIN users u ON w.user_id = u.user_id
            WHERE w.notified = 0
            ORDER BY w.created_at DESC
        ''')
        return [dict(row) for row in self.cursor.fetchall()]

    def mark_big_win_notified(self, win_id: int):
        self.cursor.execute("UPDATE big_wins SET notified = 1 WHERE id = ?", (win_id,))
        self.conn.commit()

    def get_top_big_wins(self, limit: int = 10) -> list:
        self.cursor.execute('''
            SELECT w.*, u.username 
            FROM big_wins w
            JOIN users u ON w.user_id = u.user_id
            ORDER BY w.win_amount DESC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in self.cursor.fetchall()]

    def get_user_big_wins(self, user_id: int, limit: int = 5) -> list:
        self.cursor.execute('''
            SELECT * FROM big_wins 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, limit))
        return [dict(row) for row in self.cursor.fetchall()]

    # ---------- Соціальне ----------
    def add_suggestion(self, user_id: int, message: str):
        self.cursor.execute("INSERT INTO suggestions (user_id, message) VALUES (?, ?)", (user_id, message))
        self.conn.commit()

    def get_suggestions_by_user(self, user_id: int) -> list:
        self.cursor.execute("SELECT * FROM suggestions WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def get_all_suggestions(self, limit: int = 50) -> list:
        self.cursor.execute('''
            SELECT s.*, u.username 
            FROM suggestions s
            LEFT JOIN users u ON s.user_id = u.user_id
            ORDER BY s.created_at DESC
            LIMIT ?
        ''', (limit,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def get_suggestion_by_id(self, sid: int) -> Optional[dict]:
        self.cursor.execute("SELECT * FROM suggestions WHERE id = ?", (sid,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def update_suggestion_status(self, sid: int, status: str, admin_reply: str = None):
        if admin_reply:
            self.cursor.execute("UPDATE suggestions SET status = ?, admin_reply = ? WHERE id = ?", (status, admin_reply, sid))
        else:
            self.cursor.execute("UPDATE suggestions SET status = ? WHERE id = ?", (status, sid))
        self.conn.commit()

    def send_friend_request(self, from_id: int, to_id: int) -> bool:
        if from_id == to_id:
            return False
        self.cursor.execute("SELECT 1 FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)", (from_id, to_id, to_id, from_id))
        if self.cursor.fetchone():
            return False
        self.cursor.execute("SELECT 1 FROM friend_requests WHERE from_id = ? AND to_id = ?", (from_id, to_id))
        if self.cursor.fetchone():
            return False
        self.cursor.execute("INSERT INTO friend_requests (from_id, to_id) VALUES (?, ?)", (from_id, to_id))
        self.conn.commit()
        return True

    def accept_friend_request(self, user_id: int, from_id: int) -> bool:
        self.cursor.execute("DELETE FROM friend_requests WHERE from_id = ? AND to_id = ?", (from_id, user_id))
        if self.cursor.rowcount == 0:
            return False
        self.cursor.execute("INSERT INTO friends (user_id, friend_id) VALUES (?, ?), (?, ?)", (user_id, from_id, from_id, user_id))
        self.conn.commit()
        return True

    def get_friends(self, user_id: int) -> list:
        self.cursor.execute('''
            SELECT u.user_id, u.username, u.balance
            FROM friends f
            JOIN users u ON f.friend_id = u.user_id
            WHERE f.user_id = ?
        ''', (user_id,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    # ---------- Приватні турніри ----------
    def create_private_tournament(self, creator_id: int, name: str, fee: int, max_part: int, duration: int) -> int:
        start_time = datetime.now().isoformat()
        end_time = (datetime.now() + timedelta(hours=duration)).isoformat()
        self.cursor.execute('''
            INSERT INTO private_tournaments (creator_id, name, entry_fee, max_participants, duration_hours, start_time, end_time, prize_pool)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        ''', (creator_id, name, fee, max_part, duration, start_time, end_time))
        self.conn.commit()
        return self.cursor.lastrowid

    def join_private_tournament(self, tournament_id: int, user_id: int) -> bool:
        self.cursor.execute("SELECT COUNT(*) FROM private_tournament_participants WHERE tournament_id = ?", (tournament_id,))
        count = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT max_participants FROM private_tournaments WHERE id = ?", (tournament_id,))
        max_part = self.cursor.fetchone()[0]
        if count >= max_part:
            return False
        self.cursor.execute("SELECT entry_fee FROM private_tournaments WHERE id = ?", (tournament_id,))
        fee = self.cursor.fetchone()[0]
        balance = self.get_user_balance(user_id)
        if balance < fee:
            return False
        self.update_balance(user_id, -fee)
        self.cursor.execute("UPDATE private_tournaments SET prize_pool = prize_pool + ? WHERE id = ?", (fee, tournament_id))
        self.cursor.execute("INSERT INTO private_tournament_participants (tournament_id, user_id) VALUES (?, ?)", (tournament_id, user_id))
        self.conn.commit()
        return True

    # ---------- Адмін-статистика ----------
    def get_admin_stats(self) -> dict:
        stats = {}
        stats['total_users'] = self.get_total_users_count()
        stats['total_skins'] = self.get_total_skins_count()
        self.cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'completed'")
        stats['total_payments'] = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT SUM(amount_coins) FROM payments WHERE status = 'completed'")
        stats['total_payments_sum'] = self.cursor.fetchone()[0] or 0
        self.cursor.execute("SELECT COUNT(*) FROM game_stats")
        stats['total_games'] = self.cursor.fetchone()[0]
        one_day_ago = (datetime.now() - timedelta(days=1)).isoformat()
        self.cursor.execute("SELECT COUNT(*) FROM users WHERE last_activity > ?", (one_day_ago,))
        stats['active_24h'] = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM payments")
        total_payments = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'completed'")
        completed = self.cursor.fetchone()[0]
        stats['payment_conversion'] = (completed / total_payments * 100) if total_payments else 0
        self.cursor.execute("SELECT game_type, SUM(games_played) as cnt FROM game_stats GROUP BY game_type ORDER BY cnt DESC")
        rows = self.cursor.fetchall()
        stats['popular_games'] = {row['game_type']: row['cnt'] for row in rows}
        self.cursor.execute("SELECT COUNT(*) FROM big_wins")
        stats['big_wins_count'] = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT MAX(win_amount) FROM big_wins")
        stats['biggest_win_ever'] = self.cursor.fetchone()[0] or 0
        return stats

    # ---------- Скидання прогресу ----------
    def reset_user_progress(self, user_id: int) -> bool:
        try:
            self.cursor.execute("DELETE FROM inventory WHERE user_id = ?", (user_id,))
            self.cursor.execute("DELETE FROM market_listings WHERE seller_id = ?", (user_id,))
            self.cursor.execute("DELETE FROM duels WHERE creator_id = ? OR opponent_id = ?", (user_id, user_id))
            self.cursor.execute("DELETE FROM tournament_participants WHERE user_id = ?", (user_id,))
            self.cursor.execute("DELETE FROM private_tournament_participants WHERE user_id = ?", (user_id,))
            self.cursor.execute("DELETE FROM game_stats WHERE user_id = ?", (user_id,))
            self.cursor.execute("DELETE FROM daily_stats WHERE user_id = ?", (user_id,))
            self.cursor.execute("DELETE FROM suggestions WHERE user_id = ?", (user_id,))
            self.cursor.execute("DELETE FROM friends WHERE user_id = ? OR friend_id = ?", (user_id, user_id))
            self.cursor.execute("DELETE FROM friend_requests WHERE from_id = ? OR to_id = ?", (user_id, user_id))
            self.cursor.execute("DELETE FROM promocode_uses WHERE user_id = ?", (user_id,))
            self.cursor.execute("DELETE FROM rare_drops WHERE user_id = ?", (user_id,))
            self.cursor.execute("DELETE FROM user_free_cases WHERE user_id = ?", (user_id,))
            self.cursor.execute("DELETE FROM big_wins WHERE user_id = ?", (user_id,))
            self.cursor.execute('''
                UPDATE users SET
                    balance = 1000,
                    level = 1,
                    xp = 0,
                    cases_opened = 0,
                    duels_won = 0,
                    games_played = 0,
                    biggest_win = 0,
                    rare_special_count = 0,
                    free_cases = 0,
                    notify_bonus = 1,
                    notify_market = 1,
                    last_activity = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Помилка при скиданні прогресу {user_id}: {e}")
            return False

    # ---------- Продаж всього інвентаря ----------
    def sell_all_inventory(self, user_id: int) -> dict:
        inv = self.get_user_inventory(user_id)
        if not inv:
            return {"success": False, "message": "🎒 Інвентар порожній.", "count": 0, "total": 0}

        total = 0
        count = 0
        for item in inv:
            price = int(item['case_price'] * SELL_PRICES.get(item['rarity'], 0.3))
            total += price
            count += 1
            self.cursor.execute("DELETE FROM inventory WHERE id = ?", (item['id'],))
            self.log_sale(user_id, item['skin_name'], item['rarity'], price, item['case_price'])

        self.update_balance(user_id, total)
        self.conn.commit()
        return {"success": True, "message": f"✅ Продано {count} скінів за {total} монет.", "count": count, "total": total}

    # ---------- Виведення коштів ----------
    def create_withdrawal(self, user_id: int, amount: int, bank: str, card: str) -> int:
        self.cursor.execute(
            "INSERT INTO withdrawals (user_id, amount, bank, card) VALUES (?, ?, ?, ?)",
            (user_id, amount, bank, card)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def get_pending_withdrawals(self) -> list:
        self.cursor.execute("SELECT * FROM withdrawals WHERE status = 'pending' ORDER BY created_at DESC")
        return [dict(row) for row in self.cursor.fetchall()]

    def get_withdrawal_by_id(self, wid: int) -> Optional[dict]:
        self.cursor.execute("SELECT * FROM withdrawals WHERE id = ?", (wid,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def confirm_withdrawal(self, wid: int, admin_id: int) -> dict:
        self.cursor.execute("SELECT * FROM withdrawals WHERE id = ? AND status = 'pending'", (wid,))
        w = self.cursor.fetchone()
        if not w:
            return {"success": False, "message": "❌ Заявку не знайдено або вже оброблено"}
        w = dict(w)
        self.update_balance(w['user_id'], -w['amount'])
        self.cursor.execute(
            "UPDATE withdrawals SET status = 'completed', confirmed_by = ?, confirmed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (admin_id, wid)
        )
        self.conn.commit()
        return {"success": True, "message": f"✅ Виведення #{wid} підтверджено"}

    def cancel_withdrawal(self, wid: int, admin_id: int) -> dict:
        self.cursor.execute(
            "UPDATE withdrawals SET status = 'cancelled', confirmed_by = ?, confirmed_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending'",
            (admin_id, wid)
        )
        self.conn.commit()
        if self.cursor.rowcount:
            return {"success": True, "message": f"❌ Виведення #{wid} скасовано"}
        return {"success": False, "message": "❌ Заявку не знайдено"}

    # ---------- НОВІ МЕТОДИ ДЛЯ СПОВІЩЕНЬ ----------
    def toggle_notification(self, user_id: int, type_: str) -> bool:
        if type_ not in ('bonus', 'market'):
            return False
        col = f"notify_{type_}"
        self.cursor.execute(f"UPDATE users SET {col} = 1 - {col} WHERE user_id = ?", (user_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_notification_settings(self, user_id: int) -> dict:
        self.cursor.execute("SELECT notify_bonus, notify_market FROM users WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        if row:
            return {'bonus': bool(row['notify_bonus']), 'market': bool(row['notify_market'])}
        return {'bonus': True, 'market': True}

    def get_users_for_reminder(self) -> List[int]:
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=24)).isoformat()
        self.cursor.execute("""
            SELECT user_id FROM users
            WHERE notify_bonus = 1
              AND (last_daily_bonus IS NULL OR last_daily_bonus < ?)
        """, (cutoff,))
        rows = self.cursor.fetchall()
        return [row['user_id'] for row in rows]

    def get_users_with_market_notifications(self) -> List[int]:
        self.cursor.execute("SELECT user_id FROM users WHERE notify_market = 1")
        rows = self.cursor.fetchall()
        return [row['user_id'] for row in rows]

    # ---------- Закриття ----------
    def close(self):
        self.conn.close()

db = Database()