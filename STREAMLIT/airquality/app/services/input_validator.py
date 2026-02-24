#!/usr/bin/env python3
"""
Service de validation des entrées utilisateur
Protège contre les injections et entrées malveillantes
"""

import re
import html
from typing import Optional, Tuple, List
from datetime import datetime


class InputValidator:
    """Validateur d'entrées sécurisé"""

    # PatternsRegex
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    PASSWORD_PATTERN = re.compile(
        r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
    )

    # Caractères dangereux pour SQL (à éviter)
    SQL_DANGEROUS_CHARS = re.compile(
        r"('|(\\'|\\'')|--|;|\/\*|\*\/|xp_|sp_|EXEC|EXECUTE|UNION|SELECT|INSERT|UPDATE|DELETE|DROP|--)"
    )

    # Tags HTML dangereux
    DANGEROUS_HTML_TAGS = re.compile(
        r"<script|<iframe|<object|<embed|<applet|<meta|<link|<body|<html", re.IGNORECASE
    )

    @classmethod
    def validate_email(cls, email: str) -> Tuple[bool, Optional[str]]:
        """
        Valide une adresse email
        Returns: (is_valid, error_message)
        """
        if not email:
            return False, "L'email est requis"

        email = email.strip().lower()

        if len(email) > 254:
            return False, "Email trop long (max 254 caractères)"

        if not cls.EMAIL_PATTERN.match(email):
            return False, "Format d'email invalide"

        return True, None

    @classmethod
    def validate_password(cls, password: str) -> Tuple[bool, Optional[str]]:
        """
        Valide un mot de passe
        Returns: (is_valid, error_message)
        """
        if not password:
            return False, "Le mot de passe est requis"

        if len(password) < 8:
            return False, "Le mot de passe doit contenir au moins 8 caractères"

        if len(password) > 128:
            return False, "Le mot de passe est trop long (max 128 caractères)"

        # Pas de vérification stricte du format pour éviter de frustrer les utilisateurs
        # Mais on log si faible complexité
        return True, None

    @classmethod
    def validate_password_strength(
        cls, password: str
    ) -> Tuple[bool, Optional[str], int]:
        """
        Valide la force d'un mot de passe avec score
        Returns: (is_valid, error_message, strength_score 0-4)
        """
        if not password:
            return False, "Le mot de passe est requis", 0

        score = 0

        if len(password) >= 8:
            score += 1
        if len(password) >= 12:
            score += 1
        if re.search(r"[a-z]", password):
            score += 1
        if re.search(r"[A-Z]", password):
            score += 1
        if re.search(r"\d", password):
            score += 1
        if re.search(r"[@$!%*?&]", password):
            score += 1

        score = min(score, 4)

        if len(password) < 8:
            return False, "Le mot de passe doit contenir au moins 8 caractères", score

        return True, None, score

    @classmethod
    def validate_name(
        cls, name: str, field_name: str = "Nom"
    ) -> Tuple[bool, Optional[str]]:
        """
        Valide un nom ou prénom
        Returns: (is_valid, error_message)
        """
        if not name:
            return False, f"{field_name} est requis"

        name = name.strip()

        if len(name) < 2:
            return False, f"{field_name} trop court (min 2 caractères)"

        if len(name) > 50:
            return False, f"{field_name} trop long (max 50 caractères)"

        # Vérifier que des caractères valides
        if not re.match(r"^[a-zA-ZÀ-ÿ\s\-']+$", name):
            return False, f"{field_name} contient des caractères invalides"

        return True, None

    @classmethod
    def sanitize_sql_input(cls, user_input: str) -> str:
        """
        Nettoie une entrée pour prévenir les injections SQL
        ATTENTION: Cette méthode ne remplace pas l'utilisation de requêtes paramétrées!
        """
        if not user_input:
            return ""

        # Échapper les caractères spéciaux
        sanitized = user_input.replace("'", "''")
        sanitized = sanitized.replace(";", "")
        sanitized = sanitized.replace("--", "")
        sanitized = sanitized.replace("/*", "")
        sanitized = sanitized.replace("*/", "")

        return sanitized

    @classmethod
    def sanitize_html(cls, user_input: str) -> str:
        """
        Nettoie le HTML pour prévenir les attaques XSS
        Utilise html.escape() pour encoder les caractères spéciaux
        """
        if not user_input:
            return ""

        return html.escape(user_input)

    @classmethod
    def validate_html_safe(cls, user_input: str) -> Tuple[bool, Optional[str]]:
        """
        Valide que l'entrée ne contient pas de HTML dangereux
        Returns: (is_safe, error_message)
        """
        if not user_input:
            return True, None

        if cls.DANGEROUS_HTML_TAGS.search(user_input):
            return False, "Contenu HTML non autorisé"

        return True, None

    @classmethod
    def validate_address(cls, address: str) -> Tuple[bool, Optional[str]]:
        """
        Valide une adresse
        Returns: (is_valid, error_message)
        """
        if not address:
            return False, "L'adresse est requise"

        address = address.strip()

        if len(address) < 3:
            return False, "Adresse trop courte"

        if len(address) > 200:
            return False, "Adresse trop longue"

        return True, None

    @classmethod
    def validate_coordinates(cls, lat: float, lon: float) -> Tuple[bool, Optional[str]]:
        """
        Valide des coordonnées géographiques
        Returns: (is_valid, error_message)
        """
        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError):
            return False, "Coordonnées invalides"

        if not (-90 <= lat <= 90):
            return False, "Latitude invalide (doit être entre -90 et 90)"

        if not (-180 <= lon <= 180):
            return False, "Longitude invalide (doit être entre -180 et 180)"

        return True, None

    @classmethod
    def validate_date_range(
        cls, start_date: str, end_date: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Valide une plage de dates
        Returns: (is_valid, error_message)
        """
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
        except ValueError:
            return False, "Format de date invalide"

        if start > end:
            return False, "La date de début doit être antérieure à la date de fin"

        # Limiter à 1 an de données
        if (end - start).days > 365:
            return False, "La période ne peut pas dépasser 1 an"

        return True, None

    @classmethod
    def contains_sql_injection(cls, user_input: str) -> bool:
        """
        Détecte une tentative d'injection SQL potentielle
        Returns: True si injection détectée
        """
        if not user_input:
            return False

        return bool(cls.SQL_DANGEROUS_CHARS.search(user_input, re.IGNORECASE))

    @classmethod
    def validate_api_key(cls, api_key: str) -> Tuple[bool, Optional[str]]:
        """
        Valide une clé API
        Returns: (is_valid, error_message)
        """
        if not api_key:
            return False, "Clé API requise"

        # Les clés API ne doivent pas contenir d'espaces ou caractères spéciaux dangereux
        if " " in api_key or "<" in api_key or ">" in api_key:
            return False, "Clé API invalide"

        return True, None


def sanitize_user_input(user_input: str) -> str:
    """Fonction utilitaire pour sanitizer les entrées utilisateur"""
    return InputValidator.sanitize_html(user_input)


def validate_user_registration(
    email: str, password: str, first_name: str, last_name: str
) -> Tuple[bool, List[str]]:
    """
    Valide toutes les données d'inscription
    Returns: (is_valid, list_of_errors)
    """
    errors = []

    # Valider email
    valid, error = InputValidator.validate_email(email)
    if not valid:
        errors.append(error)

    # Valider mot de passe
    valid, error = InputValidator.validate_password(password)
    if not valid:
        errors.append(error)

    # Valider prénom
    valid, error = InputValidator.validate_name(first_name, "Prénom")
    if not valid:
        errors.append(error)

    # Valider nom
    valid, error = InputValidator.validate_name(last_name, "Nom")
    if not valid:
        errors.append(error)

    # Vérifier injection SQL potentielle
    for field, value in [("email", email), ("prénom", first_name), ("nom", last_name)]:
        if InputValidator.contains_sql_injection(value):
            errors.append(f"Caractères suspects détectés dans {field}")

    return len(errors) == 0, errors
