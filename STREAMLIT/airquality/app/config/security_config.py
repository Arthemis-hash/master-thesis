#!/usr/bin/env python3
"""
Configuration centrale de sécurité
Validation des variables d'environnement au démarrage
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv

# Charger le fichier .env
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)


class SecurityConfig:
    """Configuration de sécurité validée au démarrage"""

    _instance: Optional["SecurityConfig"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._validate_all()
        self._initialized = True

    def _validate_all(self):
        """Valide toutes les variables de sécurité au démarrage"""
        errors = []

        # JWT Secret
        jwt_secret = os.getenv("JWT_SECRET")
        if not jwt_secret:
            errors.append("JWT_SECRET non défini dans les variables d'environnement")
        elif len(jwt_secret) < 32:
            errors.append("JWT_SECRET doit faire au moins 32 caractères")
        elif (
            "votre_jwt_secret" in jwt_secret.lower()
            or "a_generer" in jwt_secret.lower()
        ):
            errors.append(
                'JWT_SECRET n\'a pas été personnalisé! Générez avec: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )

        # Database URL
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            errors.append("DATABASE_URL non défini")

        # Redis (optionnel mais recommandé)
        redis_host = os.getenv("REDIS_HOST", "localhost")

        if errors:
            for error in errors:
                logger.critical(f"🔒 SECURITY ERROR: {error}")
            raise RuntimeError(
                f"Configuration de sécurité invalide: {', '.join(errors)}"
            )

        logger.info("✅ Configuration de sécurité validée")

    # JWT Configuration
    @property
    def JWT_SECRET(self) -> str:
        return os.getenv("JWT_SECRET", "")

    @property
    def JWT_ALGORITHM(self) -> str:
        return os.getenv("JWT_ALGORITHM", "HS256")

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

    @property
    def REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:
        return int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # Session Configuration
    @property
    def SESSION_TTL_SECONDS(self) -> int:
        return int(os.getenv("SESSION_TTL_SECONDS", "3600"))

    # Rate Limiting
    @property
    def RATE_LIMIT_LOGIN_ATTEMPTS(self) -> int:
        return int(os.getenv("RATE_LIMIT_LOGIN_ATTEMPTS", "5"))

    @property
    def RATE_LIMIT_WINDOW_SECONDS(self) -> int:
        return int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "900"))

    @property
    def RATE_LIMIT_REGISTER_ATTEMPTS(self) -> int:
        return int(os.getenv("RATE_LIMIT_REGISTER_ATTEMPTS", "3"))

    # Bcrypt
    @property
    def BCRYPT_ROUNDS(self) -> int:
        return int(os.getenv("BCRYPT_ROUNDS", "12"))

    # Redis
    @property
    def REDIS_HOST(self) -> str:
        return os.getenv("REDIS_HOST", "localhost")

    @property
    def REDIS_PORT(self) -> int:
        return int(os.getenv("REDIS_PORT", "6379"))

    @property
    def REDIS_PASSWORD(self) -> Optional[str]:
        pwd = os.getenv("REDIS_PASSWORD")
        return pwd if pwd and pwd.strip() else None

    @property
    def REDIS_DB(self) -> int:
        return int(os.getenv("REDIS_DB", "0"))

    # Database
    @property
    def DATABASE_URL(self) -> str:
        return os.getenv("DATABASE_URL", "")

    # API Keys (ne pas logger ces valeurs!)
    @property
    def GOOGLE_API_KEY(self) -> Optional[str]:
        return os.getenv("GEOCODING_API_KEY")

    @property
    def STREET_VIEW_API_KEY(self) -> Optional[str]:
        return os.getenv("STREET_VIEW_API_KEY")

    # Email
    @property
    def SMTP_HOST(self) -> Optional[str]:
        return os.getenv("SMTP_HOST")

    @property
    def SMTP_USER(self) -> Optional[str]:
        return os.getenv("SMTP_USER")

    @property
    def SMTP_PASSWORD(self) -> Optional[str]:
        return os.getenv("SMTP_PASSWORD")

    @property
    def SMTP_FROM_EMAIL(self) -> Optional[str]:
        return os.getenv("SMTP_FROM_EMAIL")


def get_security_config() -> SecurityConfig:
    """Récupère l'instance de configuration"""
    return SecurityConfig()


# Validation au import
try:
    _config = get_security_config()
except RuntimeError as e:
    logger.critical(f"⚠️ ÉCHEC VALIDATION SÉCURITÉ: {e}")
