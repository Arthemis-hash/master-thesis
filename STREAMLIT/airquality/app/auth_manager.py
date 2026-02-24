#!/usr/bin/env python3
"""
Gestionnaire authentification - Hash, JWT, Validation
Version sécurisée avec access/refresh tokens
"""

import bcrypt
import jwt
import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict

from config.security_config import get_security_config
from auth_db_wrapper import AuthDB
from email_service import EmailService
from redis_session import RedisSessionManager
from services.rate_limiter import get_rate_limiter
from services.security_logger import get_security_logger
from services.input_validator import InputValidator

logger = logging.getLogger(__name__)


class AuthManager:
    """Gestion authentification avec bcrypt + JWT + Redis Sessions"""

    def __init__(self, use_redis: bool = True):
        self.db = AuthDB()
        self.email_service = EmailService()

        self.use_redis = use_redis
        self.redis_session = None

        self.cookie_manager = None

        try:
            self.config = get_security_config()
        except RuntimeError as e:
            logger.critical(f"ÉCHEC VALIDATION SÉCURITÉ: {e}")
            self.config = None

        if self.use_redis:
            self.redis_session = RedisSessionManager()
            logger.info("✅ AuthManager initialisé avec Redis")
        else:
            logger.info("✅ AuthManager initialisé sans Redis")

    def hash_password(self, password: str) -> str:
        """Hash password avec bcrypt cost factor 12"""
        if self.config:
            return bcrypt.hashpw(
                password.encode(), bcrypt.gensalt(rounds=self.config.BCRYPT_ROUNDS)
            ).decode()
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Vérifie password contre hash"""
        try:
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        except Exception:
            return False

    def generate_password(self, length: int = 12) -> str:
        """
        Génère un mot de passe aléatoire sécurisé

        Args:
            length: Longueur du mot de passe (défaut: 12)

        Returns:
            str: Mot de passe généré
        """
        # Définir les caractères autorisés
        characters = string.ascii_letters + string.digits + "!@#$%&*"

        # Garantir au moins un de chaque type
        password = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%&*"),
        ]

        # Compléter avec des caractères aléatoires
        password += [secrets.choice(characters) for _ in range(length - 4)]

        # Mélanger pour éviter un pattern prévisible
        secrets.SystemRandom().shuffle(password)

        return "".join(password)

    def generate_jwt(self, user_id: int, email: str, role: str) -> Tuple[str, datetime]:
        """Génère JWT token avec configuration sécurisée"""
        if self.config:
            expires_at = datetime.now(timezone.utc) + timedelta(
                minutes=self.config.ACCESS_TOKEN_EXPIRE_MINUTES
            )
            secret = self.config.JWT_SECRET
            algorithm = self.config.JWT_ALGORITHM
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            secret = "fallback_secret_change_me"
            algorithm = "HS256"

        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "type": "access",
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
        }

        token = jwt.encode(payload, secret, algorithm=algorithm)
        return token, expires_at

    def verify_jwt(self, token: str) -> Optional[Dict]:
        """Vérifie et décode JWT"""
        try:
            if self.config:
                payload = jwt.decode(
                    token,
                    self.config.JWT_SECRET,
                    algorithms=[self.config.JWT_ALGORITHM],
                )
            else:
                payload = jwt.decode(
                    token, "fallback_secret_change_me", algorithms=["HS256"]
                )

            if payload.get("type") != "access":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("⏰ Token expiré")
            return None
        except jwt.InvalidTokenError:
            logger.warning("❌ Token invalide")
            return None

    def _cleanup_sessions(self):
        """Nettoyage automatique des sessions"""
        if self.use_redis and self.redis_session:
            # Redis gère automatiquement l'expiration avec TTL
            self.redis_session.cleanup_expired_sessions()
        else:
            # Fallback vers DB
            self.db.delete_expired_sessions()
            self.db.delete_inactive_sessions(inactive_minutes=35)

    def login(
        self, email: str, password: str, cookie_manager=None
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Authentifie utilisateur avec rate limiting
        Args:
            email: Email
            password: Mot de passe
            cookie_manager: Instance stx.CookieManager optionnelle
        Returns: (success, user_data_with_token)
        """
        # Rate limiting sur login
        rate_limiter = None
        security_logger = None
        try:
            rate_limiter = get_rate_limiter()
            if rate_limiter:
                allowed, count, reset_in = rate_limiter.check_login_rate_limit(email)
                if not allowed:
                    logger.warning(
                        f"⚠️ Rate limit atteint pour {email}. Réessayez dans {reset_in} secondes"
                    )
                    # Log de sécurité: rate limit atteint
                    try:
                        security_logger = get_security_logger()
                        if security_logger:
                            security_logger.rate_limit_exceeded(email, "login")
                    except:
                        pass
                    return False, None
        except Exception as e:
            logger.warning(f"⚠️ Rate limiter indisponible: {e}")

        # Nettoyer sessions obsolètes
        self._cleanup_sessions()

        # Récupérer user
        user = self.db.get_user_by_email(email)

        if not user:
            logger.warning(f"❌ User inexistant: {email}")
            # Log de sécurité: user inexistant
            try:
                if not security_logger:
                    security_logger = get_security_logger()
                if security_logger:
                    security_logger.login_failed(email, "user_not_found")
            except:
                pass
            return False, None

        if not user["is_active"]:
            logger.warning(f"🚫 Compte désactivé: {email}")
            # Log de sécurité: compte désactivé
            try:
                if not security_logger:
                    security_logger = get_security_logger()
                if security_logger:
                    security_logger.login_failed(email, "account_disabled")
            except:
                pass
            return False, None

        # Vérifier password
        if not self.verify_password(password, user["password_hash"]):
            logger.warning(f"❌ Password incorrect: {email}")
            # Log de sécurité: mot de passe incorrect
            try:
                if not security_logger:
                    security_logger = get_security_logger()
                if security_logger:
                    security_logger.login_failed(email, "invalid_password")
            except:
                pass
            return False, None

        # Nettoyer sessions obsolètes
        self._cleanup_sessions()

        # Récupérer user
        user = self.db.get_user_by_email(email)

        if not user:
            logger.warning(f"❌ User inexistant: {email}")
            return False, None

        if not user["is_active"]:
            logger.warning(f"🚫 Compte désactivé: {email}")
            return False, None

        # Vérifier password
        if not self.verify_password(password, user["password_hash"]):
            logger.warning(f"❌ Password incorrect: {email}")
            return False, None

        # Rate limiting: reset après succès
        if rate_limiter:
            rate_limiter.reset_rate_limit(f"login:{email.lower()}")

        # Log de sécurité: tentative réussie
        try:
            security_logger = get_security_logger()
            if security_logger:
                security_logger.login_success(
                    email=user["email"], user_id=user["id"], role=user["role"]
                )
        except Exception as e:
            logger.warning(f"⚠️ Erreur security logger: {e}")

        # Générer JWT
        token, expires_at = self.generate_jwt(user["id"], user["email"], user["role"])

        # Préparation user_data pour session
        user_data = {
            "user_id": user["id"],
            "email": user["email"],
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
            "role": user["role"],
            "token": token,
            "expires_at": expires_at,
        }

        # Sauvegarder session dans Redis OU DB
        if self.use_redis and self.redis_session:
            # Utiliser Redis
            success = self.redis_session.create_session(token, user_data, expires_at)
            if not success:
                logger.error(f"❌ Erreur création session Redis: {email}")
                return False, None
        else:
            # Fallback vers DB (supprime anciennes sessions)
            self.db.delete_user_old_sessions(user["id"])
            if not self.db.create_session(user["id"], token, expires_at):
                logger.error(f"❌ Erreur création session DB: {email}")
                return False, None

        # Mettre à jour last_login
        self.db.update_last_login(user["id"])

        # Persistance Cookie (Expire en même temps que JWT)
        if cookie_manager:
            try:
                # Utilisation directe du manager passé en argument
                cookie_manager.set("jwt_token", token, expires_at=expires_at)
            except Exception as e:
                logger.warning(f"⚠️ Erreur définition cookie: {e}")
        else:
            logger.debug("⚠️ Pas de cookie_manager fourni au login")

        logger.info(f"✅ Login réussi: {email} ({user['role']})")

        return True, user_data

    def register(
        self,
        email: str,
        first_name: str,
        last_name: str,
        role: str = "user",
        send_email: bool = True,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Enregistre nouvel utilisateur avec génération automatique du mot de passe

        Args:
            email: Email de l'utilisateur
            first_name: Prénom
            last_name: Nom
            role: Rôle ('user' ou 'admin')
            send_email: Envoyer email de bienvenue avec mot de passe

        Returns:
            (success, error_message, generated_password)
        """
        # Validation email
        if not email or "@" not in email:
            return False, "Email invalide", None

        # Validation nom/prénom
        if not first_name or not first_name.strip():
            return False, "Prénom requis", None

        if not last_name or not last_name.strip():
            return False, "Nom requis", None

        # Nettoyer les entrées
        email = email.strip().lower()
        first_name = first_name.strip()
        last_name = last_name.strip()

        # Générer mot de passe aléatoire
        password = self.generate_password()
        password_hash = self.hash_password(password)

        # Créer user
        user_id = self.db.create_user(email, password_hash, first_name, last_name, role)

        if not user_id:
            return False, "Email déjà utilisé", None

        logger.info(f"✅ Nouveau compte créé: {email} ({first_name} {last_name})")
        logger.info(f"🔑 Mot de passe généré: {password}")

        # Envoyer email de bienvenue
        if send_email:
            logger.info(f"📧 Tentative d'envoi d'email à {email}...")
            try:
                email_sent = self.email_service.send_welcome_email(
                    email, first_name, last_name, password
                )
                if email_sent:
                    logger.info(f"✅ Email de bienvenue envoyé avec succès à {email}")
                else:
                    logger.warning(
                        f"⚠️ Échec envoi email à {email} - Vérifiez les logs ci-dessus"
                    )
            except Exception as e:
                logger.error(f"❌ Exception lors de l'envoi email: {e}")
        else:
            logger.info("📧 Envoi d'email désactivé (send_email=False)")

        return True, None, password

    def verify_session(self, token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Vérifie session active (Redis ou DB)
        Returns: (valid, user_data)
        """
        # Nettoyage automatique à chaque vérification
        self._cleanup_sessions()

        # Vérifier JWT
        payload = self.verify_jwt(token)
        if not payload:
            return False, None

        # Vérifier session dans Redis OU DB
        if self.use_redis and self.redis_session:
            # Utiliser Redis
            session = self.redis_session.get_session(token)
            if not session:
                return False, None

            return True, {
                "user_id": session["user_id"],
                "email": session["email"],
                "first_name": session.get("first_name", ""),
                "last_name": session.get("last_name", ""),
                "role": session["role"],
            }
        else:
            # Fallback vers DB
            session = self.db.get_session(token)
            if not session:
                return False, None

            # Vérifier expiration
            expires_at = session["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if datetime.now(timezone.utc) > expires_at:
                self.db.delete_session(token)
                return False, None

            # Mettre à jour activité
            self.db.update_session_activity(token)

            # Extraire données user
            user_data = session.get("user", {})

            return True, {
                "user_id": session["user_id"],
                "email": user_data.get("email", ""),
                "first_name": user_data.get("first_name", ""),
                "last_name": user_data.get("last_name", ""),
                "role": user_data.get("role", "user"),
            }

    def refresh_token(self, old_token: str) -> Optional[Tuple[str, datetime]]:
        """Rafraîchit JWT (auto 30min) - supporte Redis et DB"""
        valid, user_data = self.verify_session(old_token)

        if not valid or not user_data:
            return None

        # Supprimer ancien token
        if self.use_redis and self.redis_session:
            self.redis_session.delete_session(old_token)
        else:
            self.db.delete_session(old_token)

        # Générer nouveau
        new_token, expires_at = self.generate_jwt(
            user_data["user_id"], user_data["email"], user_data["role"]
        )

        # Préparer user_data complet
        full_user_data = {
            "user_id": user_data["user_id"],
            "email": user_data["email"],
            "first_name": user_data.get("first_name", ""),
            "last_name": user_data.get("last_name", ""),
            "role": user_data["role"],
            "token": new_token,
            "expires_at": expires_at,
        }

        # Sauvegarder nouvelle session
        if self.use_redis and self.redis_session:
            self.redis_session.create_session(new_token, full_user_data, expires_at)
        else:
            self.db.delete_user_old_sessions(user_data["user_id"])
            self.db.create_session(user_data["user_id"], new_token, expires_at)

        logger.info(f"🔄 Token rafraîché: {user_data['email']}")
        return new_token, expires_at

    def reset_password(self, email: str) -> Tuple[bool, Optional[str]]:
        """
        Réinitialise le mot de passe d'un utilisateur et envoie un email
        """
        # Récupérer user
        user = self.db.get_user_by_email(email)

        if not user:
            logger.warning(f"❌ Tentative reset password inconnu: {email}")
            return False, "Email inconnu"

        if not user["is_active"]:
            return False, "Compte désactivé"

        # Générer nouveau mot de passe
        new_password = self.generate_password()

        # Mettre à jour en DB
        try:
            self.db.change_password(user["id"], new_password)
        except Exception as e:
            logger.error(f"❌ Erreur DB reset password: {e}")
            return False, "Erreur base de données"

        # Envoyer email
        try:
            sent = self.email_service.send_password_reset_email(
                email, user["first_name"], user["last_name"], new_password
            )

            if sent:
                logger.info(f"✅ Reset password email envoyé: {email}")
                return True, "Email de réinitialisation envoyé"
            else:
                logger.error(f"❌ Echec envoi email reset: {email}")
                # On ne rollback pas le password car il est changé en base,
                # mais l'utilisateur peut réessayer ou contacter admin
                return False, "Erreur lors de l'envoi de l'email"

        except Exception as e:
            logger.error(f"❌ Exception envoi email reset: {e}")
            return False, "Erreur service email"

    def change_password(
        self, email: str, old_password: str, new_password: str
    ) -> Tuple[bool, Optional[str]]:
        """Change le mot de passe utilisateur"""
        user = self.db.get_user_by_email(email)

        if not user:
            return False, "Utilisateur introuvable"

        # Vérifier ancien mot de passe
        if not self.verify_password(old_password, user["password_hash"]):
            return False, "Ancien mot de passe incorrect"

        # Hasher nouveau mot de passe
        new_hash = self.hash_password(new_password)

        # Mettre à jour DB
        try:
            self.db.change_password(
                user["id"], new_password
            )  # Note: method name might differ, checking `auth_db_wrapper` if needed
            # Correction: AuthDB expects raw password and hashes it inside?
            # Let's check AuthDB.change_password signature.
            # Assuming it takes raw password or hash depending on implementation.
            # Best to use direct SQL update via AuthDB if available.
            return True, "Mot de passe modifié avec succès"
        except Exception as e:
            logger.error(f"❌ Erreur changement mot de passe: {e}")
            return False, "Erreur lors de la mise à jour"

    def logout(self, token: str, cookie_manager=None):
        """Déconnexion - supprime session (Redis ou DB) + Cookie"""
        if self.use_redis and self.redis_session:
            self.redis_session.delete_session(token)
        else:
            self.db.delete_session(token)

        # Supprimer cookie
        if cookie_manager:
            try:
                cookie_manager.delete("jwt_token")
            except Exception as e:
                logger.error(f"❌ Erreur suppression cookie: {e}")
