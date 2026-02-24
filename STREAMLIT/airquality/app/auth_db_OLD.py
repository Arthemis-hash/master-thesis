#!/usr/bin/env python3
"""
Base de données authentification - Users & Sessions
Structure optimisée avec bcrypt et JWT
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class AuthDB:
    """Gestion DB authentification (users + sessions)"""
    
    def __init__(self, db_path: str = 'auth.db'):
        self.db_path = db_path
        self._initialize_tables()
        self._create_test_account()
        logger.info(f"✅ AuthDB initialisée: {db_path}")
    
    def _initialize_tables(self):
        """Crée tables users et sessions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Table sessions JWT
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                jwt_token TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL,
                last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Index pour performances
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_token ON sessions(jwt_token)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_user ON sessions(user_id)')
        
        conn.commit()
        conn.close()
    
    def _create_test_account(self):
        """Crée compte test si inexistant"""
        import bcrypt
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM users WHERE email = ?", ('test@test.com',))
        if not cursor.fetchone():
            password_hash = bcrypt.hashpw('test'.encode(), bcrypt.gensalt()).decode()
            cursor.execute('''
                INSERT INTO users (email, password_hash, first_name, last_name, role) 
                VALUES (?, ?, ?, ?, ?)
            ''', ('test@test.com', password_hash, 'Test', 'User', 'admin'))
            conn.commit()
            logger.info("✅ Compte test créé: test@test.com / test")
        
        conn.close()
    
    def get_connection(self):
        """Connexion DB"""
        return sqlite3.connect(self.db_path)
    
    def create_user(self, email: str, password_hash: str, first_name: str, last_name: str, role: str = 'user') -> Optional[int]:
        """Crée nouvel utilisateur"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (email, password_hash, first_name, last_name, role) 
                VALUES (?, ?, ?, ?, ?)
            ''', (email, password_hash, first_name, last_name, role))
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return user_id
        except sqlite3.IntegrityError:
            logger.warning(f"❌ Email déjà existant: {email}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Récupère user par email"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, email, password_hash, first_name, last_name, role, created_at, last_login, is_active
            FROM users WHERE email = ?
        ''', (email,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0], 'email': row[1], 'password_hash': row[2],
                'first_name': row[3], 'last_name': row[4], 'role': row[5],
                'created_at': row[6], 'last_login': row[7], 'is_active': row[8]
            }
        return None
    
    def update_last_login(self, user_id: int):
        """Met à jour dernière connexion"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET last_login = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (user_id,))
        conn.commit()
        conn.close()
    
    def create_session(self, user_id: int, jwt_token: str, expires_at: datetime) -> bool:
        """Crée session JWT"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sessions (user_id, jwt_token, expires_at) 
                VALUES (?, ?, ?)
            ''', (user_id, jwt_token, expires_at.isoformat()))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Erreur création session: {e}")
            return False
    
    def get_session(self, jwt_token: str) -> Optional[Dict]:
        """Récupère session par token"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.id, s.user_id, s.expires_at, s.last_activity,
                   u.email, u.first_name, u.last_name, u.role
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.jwt_token = ?
        ''', (jwt_token,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0], 'user_id': row[1], 'expires_at': row[2],
                'last_activity': row[3], 'email': row[4], 'first_name': row[5],
                'last_name': row[6], 'role': row[7]
            }
        return None
    
    def update_session_activity(self, jwt_token: str):
        """Met à jour activité session"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE sessions SET last_activity = CURRENT_TIMESTAMP 
            WHERE jwt_token = ?
        ''', (jwt_token,))
        conn.commit()
        conn.close()
    
    def delete_session(self, jwt_token: str):
        """Supprime session (déconnexion)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM sessions WHERE jwt_token = ?', (jwt_token,))
        conn.commit()
        conn.close()
    
    def delete_expired_sessions(self):
        """Nettoie sessions expirées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM sessions 
            WHERE datetime(expires_at) < datetime('now')
        ''')
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted > 0:
            logger.info(f"🧹 {deleted} sessions expirées supprimées")
    
    def delete_user_old_sessions(self, user_id: int, keep_token: str = None):
        """Supprime anciennes sessions d'un user (garde optionnellement une)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if keep_token:
            cursor.execute('''
                DELETE FROM sessions 
                WHERE user_id = ? AND jwt_token != ?
            ''', (user_id, keep_token))
        else:
            cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logger.info(f"🧹 {deleted} anciennes sessions supprimées (user {user_id})")
    
    def delete_inactive_sessions(self, inactive_minutes: int = 35):
        """Supprime sessions sans activité depuis X minutes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            DELETE FROM sessions 
            WHERE datetime(last_activity) < datetime('now', '-{inactive_minutes} minutes')
        ''')
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logger.info(f"🧹 {deleted} sessions inactives supprimées")