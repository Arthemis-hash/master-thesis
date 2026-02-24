#!/usr/bin/env python3
"""
Service d'authentification sécurisé
Implémente: Access Token (15min) + Refresh Token (7 jours) + Rotation
"""

import bcrypt
import jwt
import secrets
import string
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)


class AuthService:
    """Service d'authentification avec JWT + Refresh Tokens + Redis"""

    def __init__(self, use_redis: bool = True):
        from config.security_config import get_security_config

        self.config = get_security_config()
        self.use_redis = use_redis
        self._redis = None

        if self.use_redis:
            try:
                from redis_session import RedisSessionManager

                self._redis = RedisSessionManager()
            except Exception as e:
                logger.error(f"Erreur connexion Redis: {e}")
                raise

    def hash_password(self, password: str) -> str:
        """Hash password avec bcrypt cost factor 12"""
        return bcrypt.hashpw(
            password.encode(), bcrypt.gensalt(rounds=self.config.BCRYPT_ROUNDS)
        ).decode()

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Vérifie password contre hash"""
        try:
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        except Exception:
            return False

    def generate_access_token(
        self, user_id: int, email: str, role: str, session_id: str
    ) -> Tuple[str, datetime]:
        """Génère access token JWT (15 min par défaut)"""
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self.config.ACCESS_TOKEN_EXPIRE_MINUTES
        )

        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "session_id": session_id,
            "type": "access",
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
        }

        token = jwt.encode(
            payload, self.config.JWT_SECRET, algorithm=self.config.JWT_ALGORITHM
        )
        return token, expires_at

    def generate_refresh_token(self, user_id: int) -> Tuple[str, datetime]:
        """Génère refresh token aléatoire sécurisé (7 jours par défaut)"""
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self.config.REFRESH_TOKEN_EXPIRE_DAYS
        )

        token = secrets.token_urlsafe(64)

        return token, expires_at

    def verify_access_token(self, token: str) -> Optional[Dict]:
        """Vérifie et décode access token"""
        try:
            payload = jwt.decode(
                token, self.config.JWT_SECRET, algorithms=[self.config.JWT_ALGORITHM]
            )
            if payload.get("type") != "access":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("⏰ Access token expiré")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"❌ Token invalide: {e}")
            return None

    def verify_refresh_token(self, token: str) -> Optional[Dict]:
        """Vérifie refresh token dans Redis"""
        if not self._redis:
            return None

        try:
            key = f"refresh_token:{token}"
            data = self._redis.redis_client.get(key)

            if not data:
                return None

            token_data = json.loads(data)

            expires_at = datetime.fromisoformat(token_data["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                self._redis.redis_client.delete(key)
                return None

            return token_data
        except Exception as e:
            logger.error(f"Erreur vérification refresh token: {e}")
            return None

    def create_session(
        self,
        user_id: int,
        email: str,
        role: str,
        first_name: str = "",
        last_name: str = "",
    ) -> Dict[str, str]:
        """Crée une session complète: session_id + access token + refresh token"""
        session_id = secrets.token_urlsafe(32)

        access_token, access_expires = self.generate_access_token(
            user_id, email, role, session_id
        )
        refresh_token, refresh_expires = self.generate_refresh_token(user_id)

        if self._redis:
            # Stocker refresh token dans Redis
            refresh_key = f"refresh_token:{refresh_token}"
            refresh_data = json.dumps(
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "email": email,
                    "role": role,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": refresh_expires.isoformat(),
                }
            )
            ttl_seconds = self.config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
            self._redis.redis_client.setex(refresh_key, ttl_seconds, refresh_data)

            # Stocker session avec access token
            session_key = f"session:{session_id}"
            session_data = json.dumps(
                {
                    "user_id": user_id,
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": role,
                    "access_token": access_token,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_activity": datetime.now(timezone.utc).isoformat(),
                }
            )
            session_ttl = self.config.SESSION_TTL_SECONDS
            self._redis.redis_client.setex(session_key, session_ttl, session_data)

        return {
            "session_id": session_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "access_expires_at": access_expires.isoformat(),
            "refresh_expires_at": refresh_expires.isoformat(),
        }

    def refresh_access_token(
        self, refresh_token: str
    ) -> Optional[Tuple[str, datetime]]:
        """Rafraîchit l'access token avec rotation du refresh token"""
        token_data = self.verify_refresh_token(refresh_token)

        if not token_data:
            return None

        self._revoke_refresh_token(refresh_token)

        session_id = token_data["session_id"]
        new_access_token, new_expires = self.generate_access_token(
            token_data["user_id"], token_data["email"], token_data["role"], session_id
        )

        new_refresh_token, _ = self.generate_refresh_token(token_data["user_id"])

        if self._redis:
            # Stocker nouveau refresh token
            refresh_key = f"refresh_token:{new_refresh_token}"
            refresh_data = json.dumps(
                {
                    "user_id": token_data["user_id"],
                    "session_id": session_id,
                    "email": token_data["email"],
                    "role": token_data["role"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": (
                        datetime.now(timezone.utc)
                        + timedelta(days=self.config.REFRESH_TOKEN_EXPIRE_DAYS)
                    ).isoformat(),
                }
            )
            ttl_seconds = self.config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
            self._redis.redis_client.setex(refresh_key, ttl_seconds, refresh_data)

            # Mettre à jour session avec nouveau access token
            session_key = f"session:{session_id}"
            session_data = self._redis.redis_client.get(session_key)
            if session_data:
                session = json.loads(session_data)
                session["access_token"] = new_access_token
                session["last_activity"] = datetime.now(timezone.utc).isoformat()
                self._redis.redis_client.setex(
                    session_key, self.config.SESSION_TTL_SECONDS, json.dumps(session)
                )

        logger.info(f"🔄 Tokens rafraîchis et rotés pour {token_data['email']}")
        return new_access_token, new_expires

    def _revoke_refresh_token(self, token: str):
        """Révoque un refresh token"""
        if self._redis:
            key = f"refresh_token:{token}"
            self._redis.redis_client.delete(key)

    def revoke_session(self, session_id: str):
        """Révoque une session complète (logout)"""
        if self._redis:
            self._redis.redis_client.delete(f"session:{session_id}")
            logger.info(f"🚪 Session révoquée: {session_id[:16]}...")

    def verify_session(self, session_id: str, access_token: str) -> Optional[Dict]:
        """Vérifie que la session est valide"""
        if not self._redis:
            return None

        try:
            session_key = f"session:{session_id}"
            data = self._redis.redis_client.get(session_key)

            if not data:
                return None

            session = json.loads(data)

            if session.get("access_token") != access_token:
                logger.warning("Token ne correspond pas à la session")
                return None

            session["last_activity"] = datetime.now(timezone.utc).isoformat()
            self._redis.redis_client.setex(
                session_key, self.config.SESSION_TTL_SECONDS, json.dumps(session)
            )

            return session
        except Exception as e:
            logger.error(f"Erreur vérification session: {e}")
            return None
