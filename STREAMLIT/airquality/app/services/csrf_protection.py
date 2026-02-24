#!/usr/bin/env python3
"""
Protection CSRF pour Streamlit
Génère et valide des tokens anti-CSRF pour les actions sensibles
"""

import secrets
import hashlib
import hmac
import time
from typing import Optional, Tuple
from datetime import datetime, timezone

from config.security_config import get_security_config


class CSRFProtection:
    """Gestionnaire de protection CSRF pour Streamlit"""

    def __init__(self):
        self.config = get_security_config()
        self.token_validity_seconds = 3600  # 1 heure

    def generate_token(self, user_id: int, action: str) -> str:
        """
        Génère un token CSRF pour une action spécifique

        Args:
            user_id: ID de l'utilisateur
            action: Nom de l'action (ex: 'password_change', 'user_create')

        Returns:
            Token CSRF sécurisé
        """
        # Créer un nonce aléatoire
        nonce = secrets.token_urlsafe(32)

        # Créer le payload
        payload = f"{user_id}:{action}:{nonce}:{int(time.time())}"

        # Créer la signature HMAC
        signature = hmac.new(
            self.config.JWT_SECRET.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

        # Token final
        token = f"{payload}:{signature}"

        return token

    def validate_token(
        self, token: str, user_id: int, action: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Valide un token CSRF

        Args:
            token: Token à valider
            user_id: ID de l'utilisateur attendu
            action: Action attendue

        Returns:
            (is_valid, error_message)
        """
        try:
            parts = token.split(":")

            if len(parts) != 5:
                return False, "Token invalide (format incorrect)"

            token_user_id, token_action, nonce, timestamp, signature = parts

            # Vérifier l'action
            if token_action != action:
                return False, "Action incorrecte"

            # Vérifier l'utilisateur
            if int(token_user_id) != user_id:
                return False, "Utilisateur incorrect"

            # Vérifier l'expiration
            token_time = int(timestamp)
            current_time = int(time.time())

            if current_time - token_time > self.token_validity_seconds:
                return False, "Token expiré"

            if token_time > current_time + 60:  # Pas dans le futur (> 1 min)
                return False, "Token invalide (temporellement)"

            # Vérifier la signature
            expected_payload = f"{token_user_id}:{token_action}:{nonce}:{timestamp}"
            expected_signature = hmac.new(
                self.config.JWT_SECRET.encode(),
                expected_payload.encode(),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                return False, "Signature invalide"

            return True, None

        except (ValueError, IndexError) as e:
            return False, f"Token invalide: {str(e)}"

    def generate_form_token(self, user_id: int) -> str:
        """Génère un token pour un formulaire"""
        return self.generate_token(user_id, "form_submit")

    def generate_action_token(self, user_id: int, action_name: str) -> str:
        """Génère un token pour une action utilisateur"""
        return self.generate_token(user_id, action_name)

    def validate_form_token(
        self, token: str, user_id: int
    ) -> Tuple[bool, Optional[str]]:
        """Valide un token de formulaire"""
        return self.validate_token(token, user_id, "form_submit")


class StreamlitCSRF:
    """Intégration CSRF pour Streamlit"""

    def __init__(self):
        self.csrf = CSRFProtection()

    def get_or_create_token(self, user_id: int, action: str = "form") -> str:
        """
        Récupère ou crée un token CSRF dans la session Streamlit

        Args:
            user_id: ID de l'utilisateur
            action: Type d'action

        Returns:
            Token CSRF
        """
        import streamlit as st

        token_key = f"csrf_token_{action}"

        # Récupérer ou générer
        if token_key not in st.session_state:
            st.session_state[token_key] = self.csrf.generate_token(user_id, action)

        return st.session_state[token_key]

    def validate(
        self, token: str, user_id: int, action: str = "form"
    ) -> Tuple[bool, Optional[str]]:
        """
        Valide un token CSRF depuis Streamlit

        Args:
            token: Token à valider
            user_id: ID de l'utilisateur
            action: Type d'action

        Returns:
            (is_valid, error_message)
        """
        return self.csrf.validate_token(token, user_id, action)

    def validate_form(self, token: str, user_id: int) -> Tuple[bool, Optional[str]]:
        """Valide un token de formulaire"""
        return self.csrf.validate_form_token(token, user_id)

    def clear_token(self, action: str = "form"):
        """Supprime le token de la session"""
        import streamlit as st

        token_key = f"csrf_token_{action}"
        if token_key in st.session_state:
            del st.session_state[token_key]


# Instance globale
_csrf_instance: Optional[CSRFProtection] = None


def get_csrf_protection() -> CSRFProtection:
    """Récupère l'instance de protection CSRF"""
    global _csrf_instance
    if _csrf_instance is None:
        try:
            _csrf_instance = CSRFProtection()
        except Exception:
            return None
    return _csrf_instance


def get_streamlit_csrf() -> StreamlitCSRF:
    """Récupère l'instance Streamlit CSRF"""
    return StreamlitCSRF()
