#!/usr/bin/env python3
"""
Service de logging de sécurité structuré
Journalise les événements d'authentification en format JSON
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class SecurityLogger:
    """Logger structuré pour les événements de sécurité"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._setup_logger()
        self._initialized = True

    def _setup_logger(self):
        """Configure le logger de sécurité"""
        self.logger = logging.getLogger("security")
        self.logger.setLevel(logging.INFO)

        # Créer le répertoire de logs s'il n'existe pas
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)

        # Handler pour fichier JSON
        log_file = log_dir / "security.json"

        # Vérifier si le handler existe déjà
        if not any(isinstance(h, logging.FileHandler) for h in self.logger.handlers):
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)

            # Format JSON
            formatter = logging.Formatter("%(message)s")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        # Handler console en développement
        if os.getenv("APP_ENV", "development") == "development":
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            self.logger.addHandler(console_handler)

    def _log(self, event_type: str, success: bool, **kwargs):
        """Log un événement de sécurité"""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "success": success,
            **kwargs,
        }

        # Ajouter IP si disponible
        if "ip_address" not in event:
            event["ip_address"] = os.getenv("REMOTE_ADDR", "unknown")

        self.logger.info(json.dumps(event))

        # Logger aussi sur le logger principal pour debugging
        status = "✅" if success else "❌"
        self.logger.debug(f"{status} {event_type}: {json.dumps(event)}")

    def login_success(
        self, email: str, user_id: int, role: str, ip_address: str = None
    ):
        """Log une connexion réussie"""
        self._log(
            "LOGIN_SUCCESS",
            True,
            email=email,
            user_id=user_id,
            role=role,
            ip_address=ip_address,
        )

    def login_failed(self, email: str, reason: str, ip_address: str = None):
        """Log une connexion échouée"""
        self._log(
            "LOGIN_FAILED", False, email=email, reason=reason, ip_address=ip_address
        )

    def logout(self, email: str, user_id: int, ip_address: str = None):
        """Log une déconnexion"""
        self._log("LOGOUT", True, email=email, user_id=user_id, ip_address=ip_address)

    def password_change(
        self, email: str, user_id: int, success: bool, ip_address: str = None
    ):
        """Log un changement de mot de passe"""
        self._log(
            "PASSWORD_CHANGE",
            success,
            email=email,
            user_id=user_id,
            ip_address=ip_address,
        )

    def password_reset_request(self, email: str, ip_address: str = None):
        """Log une demande de reset mot de passe"""
        self._log("PASSWORD_RESET_REQUEST", True, email=email, ip_address=ip_address)

    def registration(
        self, email: str, user_id: int, success: bool, ip_address: str = None
    ):
        """Log une inscription"""
        self._log(
            "REGISTRATION", success, email=email, user_id=user_id, ip_address=ip_address
        )

    def rate_limit_exceeded(
        self, identifier: str, event_type: str, ip_address: str = None
    ):
        """Log un dépassement de rate limit"""
        self._log(
            "RATE_LIMIT_EXCEEDED",
            False,
            identifier=identifier,
            event_type=event_type,
            ip_address=ip_address,
        )

    def suspicious_activity(
        self, description: str, email: str = None, ip_address: str = None, **details
    ):
        """Log une activité suspecte"""
        self._log(
            "SUSPICIOUS_ACTIVITY",
            False,
            description=description,
            email=email,
            ip_address=ip_address,
            **details,
        )

    def token_refresh(
        self, email: str, user_id: int, success: bool, ip_address: str = None
    ):
        """Log un rafraîchissement de token"""
        self._log(
            "TOKEN_REFRESH",
            success,
            email=email,
            user_id=user_id,
            ip_address=ip_address,
        )

    def session_expired(self, email: str, user_id: int, ip_address: str = None):
        """Log une expiration de session"""
        self._log(
            "SESSION_EXPIRED",
            False,
            email=email,
            user_id=user_id,
            ip_address=ip_address,
        )


# Instance globale
_security_logger: Optional[SecurityLogger] = None


def get_security_logger() -> SecurityLogger:
    """Récupère l'instance du logger de sécurité"""
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger()
    return _security_logger
