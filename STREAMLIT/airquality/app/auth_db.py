#!/usr/bin/env python3
"""
============================================================
BASE DE DONNÉES AUTHENTIFICATION - Users & Sessions
============================================================
Architecture Prisma + PostgreSQL
- Gestion async avec Prisma
- Support bcrypt et JWT
- Sessions sécurisées avec expiration
============================================================
"""

import logging
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from prisma import Prisma
from prisma.models import User, Session

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION JWT
# ============================================================

class JWTConfig:
    """Configuration JWT centralisée"""
    SECRET_KEY: str = "your-super-secret-jwt-key-change-in-production"
    ALGORITHM: str = "HS256"
    EXPIRATION_HOURS: int = 24

    @classmethod
    def from_env(cls):
        """Charge config depuis variables d'environnement"""
        import os
        cls.SECRET_KEY = os.getenv('JWT_SECRET_KEY', cls.SECRET_KEY)
        cls.ALGORITHM = os.getenv('JWT_ALGORITHM', cls.ALGORITHM)
        cls.EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', cls.EXPIRATION_HOURS))


# ============================================================
# CLIENT PRISMA SINGLETON
# ============================================================

class AuthDatabaseClient:
    """Client Prisma pour authentification"""

    _instance: Optional[Prisma] = None
    _is_connected: bool = False

    @classmethod
    async def get_client(cls) -> Prisma:
        """Récupère ou crée le client Prisma"""
        if cls._instance is None:
            cls._instance = Prisma()

        if not cls._is_connected:
            await cls._instance.connect()
            cls._is_connected = True
            logger.info("✅ Auth Prisma client connected")

        return cls._instance

    @classmethod
    async def disconnect(cls):
        """Ferme la connexion"""
        if cls._instance and cls._is_connected:
            await cls._instance.disconnect()
            cls._is_connected = False
            logger.info("🔌 Auth Prisma client disconnected")


# ============================================================
# GESTIONNAIRE AUTHENTIFICATION
# ============================================================

class AuthDB:
    """Gestion authentification utilisateurs"""

    def __init__(self):
        self.db: Optional[Prisma] = None
        JWTConfig.from_env()

    async def _ensure_connected(self):
        """Assure connexion active"""
        if not self.db:
            self.db = await AuthDatabaseClient.get_client()

    async def initialize(self):
        """Initialisation + création compte test"""
        await self._ensure_connected()
        await self._create_test_account()
        logger.info("✅ AuthDB initialisée")

    async def _create_test_account(self):
        """Crée compte test si inexistant"""
        await self._ensure_connected()

        existing = await self.db.user.find_unique(
            where={'email': 'test@test.com'}
        )

        if not existing:
            password_hash = bcrypt.hashpw('test'.encode(), bcrypt.gensalt()).decode()

            await self.db.user.create(
                data={
                    'email': 'test@test.com',
                    'passwordHash': password_hash,
                    'firstName': 'Test',
                    'lastName': 'User',
                    'role': 'admin'
                }
            )
            logger.info("✅ Compte test créé: test@test.com / test")

    # ============================================================
    # GESTION UTILISATEURS
    # ============================================================

    async def create_user(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        role: str = 'user'
    ) -> Optional[User]:
        """
        Crée nouvel utilisateur avec mot de passe hashé
        """
        await self._ensure_connected()

        # Vérifier si email existe déjà
        existing = await self.db.user.find_unique(where={'email': email})
        if existing:
            logger.warning(f"❌ Email déjà existant: {email}")
            return None

        # Hash password avec bcrypt
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        try:
            user = await self.db.user.create(
                data={
                    'email': email,
                    'passwordHash': password_hash,
                    'firstName': first_name,
                    'lastName': last_name,
                    'role': role
                }
            )
            logger.info(f"✅ Utilisateur créé: {email}")
            return user

        except Exception as e:
            logger.error(f"❌ Erreur création utilisateur: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Récupère user par email"""
        await self._ensure_connected()

        return await self.db.user.find_unique(where={'email': email})

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Récupère user par ID"""
        await self._ensure_connected()

        return await self.db.user.find_unique(where={'id': user_id})

    async def update_last_login(self, user_id: int):
        """Met à jour dernière connexion"""
        await self._ensure_connected()

        await self.db.user.update(
            where={'id': user_id},
            data={'lastLogin': datetime.now(timezone.utc)}
        )

    async def verify_password(self, email: str, password: str) -> Optional[User]:
        """
        Vérifie mot de passe et retourne user si valide
        """
        user = await self.get_user_by_email(email)

        if not user:
            logger.warning(f"❌ User introuvable: {email}")
            return None

        if not user.isActive:
            logger.warning(f"❌ Compte désactivé: {email}")
            return None

        # Vérifier password avec bcrypt
        if bcrypt.checkpw(password.encode(), user.passwordHash.encode()):
            await self.update_last_login(user.id)
            logger.info(f"✅ Authentification réussie: {email}")
            return user
        else:
            logger.warning(f"❌ Mot de passe incorrect: {email}")
            return None

    # ============================================================
    # GESTION JWT & SESSIONS
    # ============================================================

    def create_jwt_token(self, user: User) -> str:
        """
        Génère JWT token pour un utilisateur
        """
        payload = {
            'user_id': user.id,
            'email': user.email,
            'role': user.role,
            'exp': datetime.utcnow() + timedelta(hours=JWTConfig.EXPIRATION_HOURS),
            'iat': datetime.utcnow()
        }

        token = jwt.encode(
            payload,
            JWTConfig.SECRET_KEY,
            algorithm=JWTConfig.ALGORITHM
        )

        return token

    def decode_jwt_token(self, token: str) -> Optional[Dict]:
        """
        Décode et valide un JWT token
        """
        try:
            payload = jwt.decode(
                token,
                JWTConfig.SECRET_KEY,
                algorithms=[JWTConfig.ALGORITHM]
            )
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("⚠️ Token expiré")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"⚠️ Token invalide: {e}")
            return None

    async def create_session(
        self,
        user_id: int,
        jwt_token: str
    ) -> Optional[Session]:
        """
        Crée session JWT en DB
        """
        await self._ensure_connected()

        expires_at = datetime.now(timezone.utc) + timedelta(hours=JWTConfig.EXPIRATION_HOURS)

        try:
            session = await self.db.session.create(
                data={
                    'userId': user_id,
                    'jwtToken': jwt_token,
                    'expiresAt': expires_at
                }
            )
            logger.info(f"✅ Session créée pour user {user_id}")
            return session

        except Exception as e:
            logger.error(f"❌ Erreur création session: {e}")
            return None

    async def get_session(self, jwt_token: str) -> Optional[Dict]:
        """
        Récupère session par token avec info user
        """
        await self._ensure_connected()

        session = await self.db.session.find_unique(
            where={'jwtToken': jwt_token},
            include={'user': True}
        )

        if not session:
            return None

        # Vérifier expiration
        if session.expiresAt < datetime.now(timezone.utc):
            logger.warning("⚠️ Session expirée")
            await self.delete_session(jwt_token)
            return None

        # Mettre à jour activité
        await self.update_session_activity(jwt_token)

        return {
            'id': session.id,
            'user_id': session.userId,
            'expires_at': session.expiresAt,
            'last_activity': session.lastActivity,
            'user': {
                'id': session.user.id,
                'email': session.user.email,
                'first_name': session.user.firstName,
                'last_name': session.user.lastName,
                'role': session.user.role
            }
        }

    async def update_session_activity(self, jwt_token: str):
        """Met à jour dernière activité session"""
        await self._ensure_connected()

        await self.db.session.update(
            where={'jwtToken': jwt_token},
            data={'lastActivity': datetime.now(timezone.utc)}
        )

    async def delete_session(self, jwt_token: str):
        """Supprime session (déconnexion)"""
        await self._ensure_connected()

        try:
            await self.db.session.delete(where={'jwtToken': jwt_token})
            logger.info("✅ Session supprimée")
        except Exception as e:
            logger.warning(f"⚠️ Session non trouvée: {e}")

    # ============================================================
    # NETTOYAGE SESSIONS
    # ============================================================

    async def delete_expired_sessions(self):
        """Nettoie sessions expirées"""
        await self._ensure_connected()

        result = await self.db.session.delete_many(
            where={'expiresAt': {'lt': datetime.now(timezone.utc)}}
        )

        if result > 0:
            logger.info(f"🧹 {result} sessions expirées supprimées")

        return result

    async def delete_inactive_sessions(self, inactive_minutes: int = 35):
        """Supprime sessions sans activité depuis X minutes"""
        await self._ensure_connected()

        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=inactive_minutes)

        result = await self.db.session.delete_many(
            where={'lastActivity': {'lt': cutoff_time}}
        )

        if result > 0:
            logger.info(f"🧹 {result} sessions inactives supprimées")

        return result

    async def delete_user_old_sessions(
        self,
        user_id: int,
        keep_token: Optional[str] = None
    ):
        """Supprime anciennes sessions d'un user (garde optionnellement une)"""
        await self._ensure_connected()

        where_clause = {'userId': user_id}

        if keep_token:
            where_clause['jwtToken'] = {'not': keep_token}

        result = await self.db.session.delete_many(where=where_clause)

        if result > 0:
            logger.info(f"🧹 {result} sessions supprimées pour user {user_id}")

        return result

    # ============================================================
    # AUTHENTIFICATION COMPLÈTE
    # ============================================================

    async def authenticate(self, email: str, password: str) -> Optional[Dict]:
        """
        Processus complet d'authentification
        Retourne token + user info si succès
        """
        # Vérifier credentials
        user = await self.verify_password(email, password)
        if not user:
            return None

        # Générer JWT
        jwt_token = self.create_jwt_token(user)

        # Créer session en DB
        session = await self.create_session(user.id, jwt_token)
        if not session:
            return None

        # Supprimer anciennes sessions de ce user
        await self.delete_user_old_sessions(user.id, keep_token=jwt_token)

        return {
            'token': jwt_token,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.firstName,
                'last_name': user.lastName,
                'role': user.role
            },
            'expires_at': session.expiresAt
        }

    async def validate_token(self, jwt_token: str) -> Optional[Dict]:
        """
        Valide un JWT token et retourne user info si valide
        """
        # Décoder JWT
        payload = self.decode_jwt_token(jwt_token)
        if not payload:
            return None

        # Vérifier session en DB
        session_info = await self.get_session(jwt_token)
        if not session_info:
            return None

        return session_info

    async def logout(self, jwt_token: str):
        """Déconnexion - supprime session"""
        await self.delete_session(jwt_token)

    # ============================================================
    # GESTION UTILISATEURS (ADMIN)
    # ============================================================

    async def list_all_users(self) -> List[User]:
        """Liste tous les utilisateurs"""
        await self._ensure_connected()

        return await self.db.user.find_many(
            order={'createdAt': 'desc'}
        )

    async def deactivate_user(self, user_id: int):
        """Désactive un utilisateur"""
        await self._ensure_connected()

        await self.db.user.update(
            where={'id': user_id},
            data={'isActive': False}
        )

        # Supprimer toutes les sessions de cet utilisateur
        await self.delete_user_old_sessions(user_id)

        logger.info(f"✅ Utilisateur {user_id} désactivé")

    async def activate_user(self, user_id: int):
        """Réactive un utilisateur"""
        await self._ensure_connected()

        await self.db.user.update(
            where={'id': user_id},
            data={'isActive': True}
        )

        logger.info(f"✅ Utilisateur {user_id} activé")

    async def change_password(self, user_id: int, new_password: str):
        """Change le mot de passe d'un utilisateur"""
        await self._ensure_connected()

        password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

        await self.db.user.update(
            where={'id': user_id},
            data={'passwordHash': password_hash}
        )

        # Supprimer toutes les sessions (force reconnexion)
        await self.delete_user_old_sessions(user_id)

        logger.info(f"✅ Mot de passe changé pour user {user_id}")


# ============================================================
# EXPORT
# ============================================================

__all__ = ['AuthDB', 'JWTConfig']
