#!/usr/bin/env python3
"""
============================================================
WRAPPER SYNCHRONE POUR AUTH_DB (ASYNC → SYNC)
============================================================
Permet d'utiliser les fonctions async de auth_db
dans du code synchrone comme auth_manager et Streamlit
============================================================
"""

import asyncio
from typing import Optional, Dict, List
from datetime import datetime
import threading

from auth_db import AuthDB as AuthDBAsync, JWTConfig
from prisma.models import User, Session


# Event loop global pour éviter de créer/fermer à chaque appel
_loop = None
_loop_lock = threading.Lock()


def get_event_loop():
    """Récupère ou crée l'event loop réutilisable"""
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            # Ne pas set_event_loop pour éviter conflits avec Streamlit
        return _loop


def run_async(coro):
    """
    Execute une coroutine dans l'event loop réutilisable
    N'utilise PAS asyncio.run() car ça ferme le loop
    """
    loop = get_event_loop()

    # Si on est déjà dans un event loop (cas Streamlit parfois)
    try:
        if asyncio.get_running_loop():
            # Créer une nouvelle task dans le loop courant
            return asyncio.create_task(coro)
    except RuntimeError:
        # Pas de loop en cours, utiliser notre loop
        pass

    # Exécuter dans notre loop sans le fermer
    if not loop.is_running():
        return loop.run_until_complete(coro)
    else:
        # Si le loop tourne déjà (thread différent), créer future
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()


class AuthDB:
    """Wrapper synchrone pour AuthDB async"""

    def __init__(self):
        self.async_db = AuthDBAsync()
        JWTConfig.from_env()

    def initialize(self):
        """Version synchrone de initialize"""
        return run_async(self.async_db.initialize())

    # ============================================================
    # GESTION UTILISATEURS
    # ============================================================

    def create_user(
        self,
        email: str,
        password_hash: str,
        first_name: str,
        last_name: str,
        role: str = 'user'
    ) -> Optional[int]:
        """
        Version synchrone de create_user
        Retourne l'ID du user créé ou None
        """
        user = run_async(self.async_db.create_user(email, password_hash, first_name, last_name, role))
        return user.id if user else None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Version synchrone de get_user_by_email"""
        user = run_async(self.async_db.get_user_by_email(email))
        if not user:
            return None

        return {
            'id': user.id,
            'email': user.email,
            'password_hash': user.passwordHash,
            'first_name': user.firstName,
            'last_name': user.lastName,
            'role': user.role,
            'is_active': user.isActive,
            'last_login': user.lastLogin,
            'created_at': user.createdAt
        }

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Version synchrone de get_user_by_id"""
        user = run_async(self.async_db.get_user_by_id(user_id))
        if not user:
            return None

        return {
            'id': user.id,
            'email': user.email,
            'password_hash': user.passwordHash,
            'first_name': user.firstName,
            'last_name': user.lastName,
            'role': user.role,
            'is_active': user.isActive,
            'last_login': user.lastLogin,
            'created_at': user.createdAt
        }

    def update_last_login(self, user_id: int):
        """Version synchrone de update_last_login"""
        return run_async(self.async_db.update_last_login(user_id))

    def verify_password(self, email: str, password: str) -> Optional[Dict]:
        """Version synchrone de verify_password"""
        user = run_async(self.async_db.verify_password(email, password))
        if not user:
            return None

        return {
            'id': user.id,
            'email': user.email,
            'password_hash': user.passwordHash,
            'first_name': user.firstName,
            'last_name': user.lastName,
            'role': user.role,
            'is_active': user.isActive
        }

    # ============================================================
    # GESTION JWT & SESSIONS
    # ============================================================

    def create_jwt_token(self, user: Dict) -> str:
        """
        Génère JWT token - cette méthode est déjà synchrone dans auth_db
        Mais on doit créer un objet User-like pour le passer
        """
        # Créer un objet simple qui a les attributs nécessaires
        class UserLike:
            def __init__(self, user_dict):
                self.id = user_dict['id']
                self.email = user_dict['email']
                self.role = user_dict['role']

        user_obj = UserLike(user)
        return self.async_db.create_jwt_token(user_obj)

    def decode_jwt_token(self, token: str) -> Optional[Dict]:
        """Décode JWT token - méthode déjà synchrone"""
        return self.async_db.decode_jwt_token(token)

    def create_session(
        self,
        user_id: int,
        jwt_token: str,
        expires_at: datetime
    ) -> bool:
        """Version synchrone de create_session"""
        session = run_async(self.async_db.create_session(user_id, jwt_token))
        return session is not None

    def get_session(self, jwt_token: str) -> Optional[Dict]:
        """Version synchrone de get_session"""
        return run_async(self.async_db.get_session(jwt_token))

    def update_session_activity(self, jwt_token: str):
        """Version synchrone de update_session_activity"""
        return run_async(self.async_db.update_session_activity(jwt_token))

    def delete_session(self, jwt_token: str):
        """Version synchrone de delete_session"""
        return run_async(self.async_db.delete_session(jwt_token))

    # ============================================================
    # NETTOYAGE SESSIONS
    # ============================================================

    def delete_expired_sessions(self) -> int:
        """Version synchrone de delete_expired_sessions"""
        return run_async(self.async_db.delete_expired_sessions())

    def delete_inactive_sessions(self, inactive_minutes: int = 35) -> int:
        """Version synchrone de delete_inactive_sessions"""
        return run_async(self.async_db.delete_inactive_sessions(inactive_minutes))

    def delete_user_old_sessions(
        self,
        user_id: int,
        keep_token: Optional[str] = None
    ) -> int:
        """Version synchrone de delete_user_old_sessions"""
        return run_async(self.async_db.delete_user_old_sessions(user_id, keep_token))

    # ============================================================
    # AUTHENTIFICATION COMPLÈTE
    # ============================================================

    def authenticate(self, email: str, password: str) -> Optional[Dict]:
        """Version synchrone de authenticate"""
        return run_async(self.async_db.authenticate(email, password))

    def validate_token(self, jwt_token: str) -> Optional[Dict]:
        """Version synchrone de validate_token"""
        return run_async(self.async_db.validate_token(jwt_token))

    def logout(self, jwt_token: str):
        """Version synchrone de logout"""
        return run_async(self.async_db.logout(jwt_token))

    # ============================================================
    # GESTION UTILISATEURS (ADMIN)
    # ============================================================

    def list_all_users(self) -> List[Dict]:
        """Version synchrone de list_all_users"""
        users = run_async(self.async_db.list_all_users())
        return [
            {
                'id': user.id,
                'email': user.email,
                'first_name': user.firstName,
                'last_name': user.lastName,
                'role': user.role,
                'is_active': user.isActive,
                'last_login': user.lastLogin,
                'created_at': user.createdAt
            }
            for user in users
        ]

    def deactivate_user(self, user_id: int):
        """Version synchrone de deactivate_user"""
        return run_async(self.async_db.deactivate_user(user_id))

    def activate_user(self, user_id: int):
        """Version synchrone de activate_user"""
        return run_async(self.async_db.activate_user(user_id))

    def change_password(self, user_id: int, new_password: str):
        """Version synchrone de change_password"""
        return run_async(self.async_db.change_password(user_id, new_password))


# ============================================================
# EXPORT
# ============================================================

__all__ = ['AuthDB', 'JWTConfig']
