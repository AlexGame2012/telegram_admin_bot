import sqlite3
import re
from datetime import datetime, timedelta
import json

class BotLogic:
    def __init__(self):
        self.conn = sqlite3.connect('./scr/bot.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                welcome_enabled INTEGER DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER,
                chat_id INTEGER,
                username TEXT,
                first_name TEXT,
                warns INTEGER DEFAULT 0,
                is_muted INTEGER DEFAULT 0,
                mute_until TEXT,
                is_banned INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                reporter_id INTEGER,
                reported_id INTEGER,
                reason TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def parse_time(self, time_str):
        time_str = time_str.lower().strip()
        
        if time_str in ['permanent', 'навсегда', 'perm', 'forever']:
            return 315360000  
        
        patterns = {
            r'(\d+)\s*m(?:in)?': 60,        
            r'(\d+)\s*h(?:our)?': 3600,       
            r'(\d+)\s*d(?:ay)?': 86400,     
            r'(\d+)\s*w(?:eek)?': 604800,     
        }
        
        for pattern, multiplier in patterns.items():
            match = re.match(pattern, time_str)
            if match:
                return int(match.group(1)) * multiplier
        
        return None
    
    def format_time(self, seconds):
        if seconds >= 31536000: 
            return "навсегда"
        
        periods = [
            ('день', 86400),
            ('час', 3600),
            ('минут', 60)
        ]
        
        for name, sec in periods:
            if seconds >= sec:
                value = seconds // sec
                return f"{value} {name}"
        
        return f"{seconds} секунд"
    
    def add_chat(self, chat_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO chats (chat_id) VALUES (?)",
                (chat_id,)
            )
            self.conn.commit()
            return True
        except:
            return False
    
    def get_chat(self, chat_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,))
        return cursor.fetchone()
    
    def toggle_welcome(self, chat_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE chats SET welcome_enabled = NOT welcome_enabled WHERE chat_id = ?",
            (chat_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0
    
    def add_user(self, user_id, chat_id, username, first_name):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, chat_id, username, first_name, warns, is_muted, is_banned) 
            VALUES (?, ?, ?, ?, COALESCE((SELECT warns FROM users WHERE user_id=? AND chat_id=?), 0), 
            COALESCE((SELECT is_muted FROM users WHERE user_id=? AND chat_id=?), 0),
            COALESCE((SELECT is_banned FROM users WHERE user_id=? AND chat_id=?), 0))
        ''', (user_id, chat_id, username, first_name, user_id, chat_id, user_id, chat_id, user_id, chat_id))
        self.conn.commit()
    
    def get_user(self, user_id, chat_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        return cursor.fetchone()
    
    def add_warn(self, user_id, chat_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET warns = warns + 1 WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        self.conn.commit()
        cursor.execute(
            "SELECT warns FROM users WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        result = cursor.fetchone()
        return result[0] if result else 0
    
    def remove_warn(self, user_id, chat_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET warns = GREATEST(warns - 1, 0) WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        self.conn.commit()
        cursor.execute(
            "SELECT warns FROM users WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        result = cursor.fetchone()
        return result[0] if result else 0
    
    def reset_warns(self, user_id, chat_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET warns = 0 WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        self.conn.commit()
        return True
    
    def mute_user(self, user_id, chat_id, duration_seconds):
        mute_until = (datetime.now() + timedelta(seconds=duration_seconds)).isoformat()
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET is_muted = 1, mute_until = ? WHERE user_id = ? AND chat_id = ?",
            (mute_until, user_id, chat_id)
        )
        self.conn.commit()
        return True
    
    def unmute_user(self, user_id, chat_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET is_muted = 0, mute_until = NULL WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        self.conn.commit()
        return True
    
    def is_muted(self, user_id, chat_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT is_muted, mute_until FROM users WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        result = cursor.fetchone()
        if result and result[0] == 1:
            if result[1]:  # Если есть время окончания
                mute_until = datetime.fromisoformat(result[1])
                if mute_until > datetime.now():
                    return True
                else:
                    self.unmute_user(user_id, chat_id)
                    return False
            return True
        return False
    
    def ban_user(self, user_id, chat_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET is_banned = 1 WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        self.conn.commit()
        return True
    
    def unban_user(self, user_id, chat_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET is_banned = 0 WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        self.conn.commit()
        return True
    
    def add_report(self, chat_id, reporter_id, reported_id, reason):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO reports (chat_id, reporter_id, reported_id, reason)
            VALUES (?, ?, ?, ?)
        ''', (chat_id, reporter_id, reported_id, reason))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_pending_reports(self, chat_id=None):
        cursor = self.conn.cursor()
        if chat_id:
            cursor.execute(
                "SELECT * FROM reports WHERE status = 'pending' AND chat_id = ? ORDER BY created_at",
                (chat_id,)
            )
        else:
            cursor.execute("SELECT * FROM reports WHERE status = 'pending' ORDER BY created_at")
        return cursor.fetchall()
    
    def mark_report_resolved(self, report_id):
        cursor = self.conn.cursor()
        cursor.execute(
            (report_id,)
        )
        self.conn.commit()
        return True
    
    def close(self):

        self.conn.close()
