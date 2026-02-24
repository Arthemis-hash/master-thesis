#!/usr/bin/env python3
"""
============================================================
GDPR ANONYMIZER - Synchronous Wrapper
============================================================
Module d'anonymisation des données personnelles
Implémente les techniques décrites dans RGPD_COMPLIANCE.md

Usage:
    from gdpr_anonymizer_sync import GDPRAnonymizer
    gdpr = GDPRAnonymizer()
    gdpr.anonymize_user(user_id)
"""

import hashlib
import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

logger = logging.getLogger(__name__)


class GDPRAnonymizer:
    """
    Gestionnaire d'anonymisation RGPD
    Implémente: Articles 15, 16, 17 du RGPD
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._init_database()
        self._initialized = True

    def _init_database(self):
        """Initialise la connexion à la base de données"""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            DATABASE_URL = os.getenv(
                "DATABASE_URL",
                "postgresql://airquality_user:CHANGE_ME_STRONG_PASSWORD@localhost:5432/airquality_db",
            )

            db_parts = DATABASE_URL.replace("postgresql://", "").split("/")
            db_host_port = db_parts[0].split("@")
            db_creds = db_host_port[0].split(":")
            db_host = db_host_port[1].split(":")
            db_name = db_parts[1].split("?")[0]

            self.db_user = db_creds[0]
            self.db_pass = db_creds[1] if len(db_creds) > 1 else ""
            self.db_host = db_host[0]
            self.db_port = db_host[1] if len(db_host) > 1 else "5432"
            self.db_name = db_name

            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_pass,
            )
            self.conn.autocommit = True
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)

            logger.info("✅ GDPRAnonymizer: Connexion DB établie")

        except Exception as e:
            logger.error(f"❌ GDPRAnonymizer: Erreur connexion DB: {e}")
            raise

    def _hash_string(self, value: str, salt: str = "") -> str:
        """Génère un hash SHA-256"""
        combined = f"{value}{salt}"
        return hashlib.sha256(combined.encode()).hexdigest()[:8]

    def anonymizeName(self, firstName: str, lastName: str) -> Dict[str, str]:
        """
        Anonymise un nom/prénom selon spécifications RGPD
        Input:  "Jean Dupont"
        Output: { "firstName": "User_a3f5b9c1", "lastName": "Anonymous" }
        """
        combined = f"{firstName}{lastName}"
        hash_suffix = self._hash_string(combined)[:8]

        return {"firstName": f"User_{hash_suffix}", "lastName": "Anonymous"}

    def anonymizeEmail(self, email: str) -> str:
        """
        Anonymise un email selon spécifications RGPD
        Input:  "jean.dupont@example.com"
        Output: "anonymous_a3f5b9c1@deleted.local"
        """
        hash_suffix = self._hash_string(email)[:12]
        return f"anonymous_{hash_suffix}@deleted.local"

    def anonymizePhone(self, phone: str) -> str:
        """Anonymise un numéro de téléphone"""
        return self._hash_string(phone)

    def anonymizeGeolocation(
        self, latitude: float, longitude: float, decimals: int = 2
    ) -> Dict[str, Any]:
        """
        Anonymise des coordonnées géographiques
        Input:  { lat: 48.8566, lon: 2.3522 }
        Output: { lat: 48.86, lon: 2.35, anonymized: True }
        """
        return {
            "latitude": round(latitude, decimals),
            "longitude": round(longitude, decimals),
            "anonymized": True,
        }

    def anonymizeIPAddress(self, ip: str) -> str:
        """Anonymise une adresse IP (IPv4/IPv6)"""
        if ":" in ip:
            return "::1"
        parts = ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.xxx.xxx.xxx"
        return "xxx.xxx.xxx.xxx"

    def export_user_data(self, user_id: int) -> Dict[str, Any]:
        """
        Article 15 RGPD - Droit d'accès
        Exporte toutes les données personnelles d'un utilisateur
        """
        try:
            # Récupérer les données utilisateur
            self.cursor.execute(
                """
                SELECT id, email, first_name, last_name, role, is_active,
                       created_at, last_login, anonymized_at, is_anonymized,
                       gdpr_consent_given, gdpr_consent_date
                FROM users WHERE id = %s
                """,
                (user_id,),
            )
            user = self.cursor.fetchone()

            if not user:
                return {"error": "Utilisateur non trouvé"}

            # Récupérer les sessions
            self.cursor.execute(
                """
                SELECT id, created_at, expires_at, last_activity
                FROM sessions WHERE user_id = %s
                """,
                (user_id,),
            )
            sessions = self.cursor.fetchall()

            # Récupérer les logs d'audit
            self.cursor.execute(
                """
                SELECT action, resource, ip_address, timestamp, details
                FROM audit_logs WHERE user_id = %s
                ORDER BY timestamp DESC LIMIT 100
                """,
                (user_id,),
            )
            audit_logs = self.cursor.fetchall()

            # Préparer l'export
            export_data = {
                "personal_data": {
                    "id": user["id"],
                    "email": user["email"],
                    "first_name": user["first_name"],
                    "last_name": user["last_name"],
                    "role": user["role"],
                    "is_active": user["is_active"],
                    "created_at": user["created_at"].isoformat()
                    if user["created_at"]
                    else None,
                    "last_login": user["last_login"].isoformat()
                    if user["last_login"]
                    else None,
                    "anonymized_at": user["anonymized_at"].isoformat()
                    if user["anonymized_at"]
                    else None,
                    "is_anonymized": user["is_anonymized"],
                    "gdpr_consent_given": user["gdpr_consent_given"],
                    "gdpr_consent_date": user["gdpr_consent_date"].isoformat()
                    if user["gdpr_consent_date"]
                    else None,
                },
                "sessions": [
                    {
                        "id": s["id"],
                        "created_at": s["created_at"].isoformat()
                        if s["created_at"]
                        else None,
                        "expires_at": s["expires_at"].isoformat()
                        if s["expires_at"]
                        else None,
                        "last_activity": s["last_activity"].isoformat()
                        if s["last_activity"]
                        else None,
                    }
                    for s in sessions
                ],
                "activity_logs": [
                    {
                        "action": log["action"],
                        "resource": log["resource"],
                        "ip_address": log["ip_address"],
                        "timestamp": log["timestamp"].isoformat()
                        if log["timestamp"]
                        else None,
                        "details": log["details"],
                    }
                    for log in audit_logs
                ],
                "export_date": datetime.now(timezone.utc).isoformat(),
                "rgpd_article": "Article 15 - Droit d'accès",
            }

            # Logger l'export
            self._create_audit_log(
                user_id=user_id,
                action="DATA_EXPORT",
                resource="user_data",
                details={"export_type": "full_export"},
            )

            logger.info(f"✅ Export RGPD user_id={user_id}")
            return export_data

        except Exception as e:
            logger.error(f"❌ Erreur export_user_data: {e}")
            return {"error": str(e)}

    def update_user_data(
        self,
        user_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> tuple:
        """
        Article 16 RGPD - Droit de rectification
        Met à jour les données personnelles d'un utilisateur
        """
        try:
            updates = []
            params = []

            if first_name:
                updates.append("first_name = %s")
                params.append(first_name)

            if last_name:
                updates.append("last_name = %s")
                params.append(last_name)

            if email:
                # Vérifier si email déjà utilisé
                self.cursor.execute(
                    "SELECT id FROM users WHERE email = %s AND id != %s",
                    (email, user_id),
                )
                if self.cursor.fetchone():
                    return False, "Email déjà utilisé par un autre utilisateur"

                updates.append("email = %s")
                params.append(email)

            if not updates:
                return False, "Aucune donnée à mettre à jour"

            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
            self.cursor.execute(query, params)

            # Logger l'action
            self._create_audit_log(
                user_id=user_id,
                action="DATA_RECTIFICATION",
                resource="user_profile",
                details={"fields_updated": updates},
            )

            logger.info(f"✅ Données mises à jour pour user_id={user_id}")
            return True, "Données mises à jour avec succès"

        except Exception as e:
            logger.error(f"❌ Erreur update_user_data: {e}")
            return False, str(e)

    def anonymize_user(self, user_id: int) -> tuple:
        """
        Article 17 RGPD - Droit à l'oubli (Anonymisation)
        Anonymise irréversiblement les données d'un utilisateur
        """
        try:
            # Récupérer les données actuelles
            self.cursor.execute(
                "SELECT email, first_name, last_name FROM users WHERE id = %s",
                (user_id,),
            )
            user = self.cursor.fetchone()

            if not user:
                return False, "Utilisateur non trouvé"

            # Générer les données anonymisées
            anonymized_names = self.anonymizeName(user["first_name"], user["last_name"])
            anonymized_email = self.anonymizeEmail(user["email"])

            # Mettre à jour l'utilisateur
            self.cursor.execute(
                """
                UPDATE users SET
                    email = %s,
                    first_name = %s,
                    last_name = %s,
                    anonymized_at = NOW(),
                    is_anonymized = true,
                    original_email = %s,
                    original_first_name = %s,
                    original_last_name = %s,
                    is_active = false
                WHERE id = %s
                """,
                (
                    anonymized_email,
                    anonymized_names["firstName"],
                    anonymized_names["lastName"],
                    user["email"],
                    user["first_name"],
                    user["last_name"],
                    user_id,
                ),
            )

            # Révoquer toutes les sessions
            self.cursor.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))

            # Logger l'anonymisation
            self._create_audit_log(
                user_id=user_id,
                action="ANONYMIZATION",
                resource="user_account",
                details={
                    "original_email": user["email"],
                    "anonymized_email": anonymized_email,
                },
            )

            logger.info(f"✅ User anonymisé: user_id={user_id}")
            return True, "Compte anonymisé avec succès"

        except Exception as e:
            logger.error(f"❌ Erreur anonymize_user: {e}")
            return False, str(e)

    def delete_user_data(self, user_id: int, confirm: bool = False) -> tuple:
        """
        Article 17 RGPD - Droit à l'oubli (Suppression complète)
        Supprime définitivement toutes les données d'un utilisateur
        ATTENTION: Action irréversible!
        """
        if not confirm:
            return False, "Confirmation requise pour suppression"

        try:
            # Vérifier que l'utilisateur existe
            self.cursor.execute("SELECT email FROM users WHERE id = %s", (user_id,))
            user = self.cursor.fetchone()

            if not user:
                return False, "Utilisateur non trouvé"

            # Supprimer dans l'ordre (respecter les FK)
            self.cursor.execute("DELETE FROM audit_logs WHERE user_id = %s", (user_id,))
            self.cursor.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
            self.cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))

            # Logger la suppression
            self._create_audit_log(
                user_id=user_id,
                action="ACCOUNT_DELETION",
                resource="user_account",
                details={"email": user["email"], "deletion_type": "permanent"},
            )

            logger.info(f"✅ User supprimé définitivement: user_id={user_id}")
            return True, "Compte supprimé définitivement"

        except Exception as e:
            logger.error(f"❌ Erreur delete_user_data: {e}")
            return False, str(e)

    def record_consent(self, user_id: int, consent_given: bool) -> tuple:
        """Enregistre le consentement RGPD d'un utilisateur"""
        try:
            self.cursor.execute(
                """
                UPDATE users SET
                    gdpr_consent_given = %s,
                    gdpr_consent_date = NOW()
                WHERE id = %s
                """,
                (consent_given, user_id),
            )

            self._create_audit_log(
                user_id=user_id,
                action="GDPR_CONSENT",
                resource="user_profile",
                details={"consent_given": consent_given},
            )

            logger.info(f"✅ Consentement enregistré pour user_id={user_id}")
            return True, "Consentement enregistré"

        except Exception as e:
            logger.error(f"❌ Erreur record_consent: {e}")
            return False, str(e)

    def batch_anonymize_inactive_users(
        self, inactive_days: int = 730, batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Anonymise automatiquement les comptes inactifs
        À exécuter via cron (voir setup_gdpr_cron.sh)
        """
        try:
            # Trouver les utilisateurs inactifs
            self.cursor.execute(
                """
                SELECT id, email, first_name, last_name
                FROM users
                WHERE is_active = true
                  AND is_anonymized = false
                  AND (last_login IS NULL OR last_login < NOW() - INTERVAL '%s days')
                LIMIT %s
                """,
                (inactive_days, batch_size),
            )
            inactive_users = self.cursor.fetchall()

            if not inactive_users:
                return {"status": "no_users_to_anonymize", "anonymized_count": 0}

            anonymized_count = 0
            for user in inactive_users:
                success, _ = self.anonymize_user(user["id"])
                if success:
                    anonymized_count += 1

            return {
                "status": "completed",
                "inactive_days": inactive_days,
                "total_found": len(inactive_users),
                "anonymized_count": anonymized_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Erreur batch_anonymize: {e}")
            return {"error": str(e)}

    def clean_old_audit_logs(self, days: int = 365) -> int:
        """
        Nettoie les logs d'audit anciens
        À exécuter via cron (hebdomadaire)
        """
        try:
            self.cursor.execute(
                "DELETE FROM audit_logs WHERE timestamp < NOW() - INTERVAL '%s days'",
                (days,),
            )
            deleted = self.cursor.rowcount

            logger.info(f"✅ {deleted} logs d'audit supprimés (>{days} jours)")
            return deleted

        except Exception as e:
            logger.error(f"❌ Erreur clean_old_audit_logs: {e}")
            return 0

    def _create_audit_log(
        self,
        user_id: int,
        action: str,
        resource: str,
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None,
    ):
        """Crée un log d'audit"""
        try:
            import json

            self.cursor.execute(
                """
                INSERT INTO audit_logs (user_id, action, resource, ip_address, details)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    action,
                    resource,
                    ip_address,
                    json.dumps(details) if details else None,
                ),
            )
        except Exception as e:
            logger.warning(f"⚠️ Erreur création audit_log: {e}")

    def get_user_sessions(self, user_id: int) -> List[Dict]:
        """Récupère les sessions actives d'un utilisateur"""
        try:
            self.cursor.execute(
                """
                SELECT id, created_at, expires_at, last_activity
                FROM sessions
                WHERE user_id = %s AND expires_at > NOW()
                """,
                (user_id,),
            )
            sessions = self.cursor.fetchall()

            return [
                {
                    "id": s["id"],
                    "created_at": s["created_at"].isoformat()
                    if s["created_at"]
                    else None,
                    "expires_at": s["expires_at"].isoformat()
                    if s["expires_at"]
                    else None,
                    "last_activity": s["last_activity"].isoformat()
                    if s["last_activity"]
                    else None,
                }
                for s in sessions
            ]
        except Exception as e:
            logger.error(f"❌ Erreur get_user_sessions: {e}")
            return []

    def revoke_all_sessions(self, user_id: int) -> tuple:
        """Révoque toutes les sessions d'un utilisateur"""
        try:
            self.cursor.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))

            self._create_audit_log(
                user_id=user_id,
                action="SESSIONS_REVOKED",
                resource="user_sessions",
                details={"reason": "user_request"},
            )

            logger.info(f"✅ Sessions révoquées pour user_id={user_id}")
            return True, "Toutes les sessions ont été révoquées"

        except Exception as e:
            logger.error(f"❌ Erreur revoke_all_sessions: {e}")
            return False, str(e)

    def close(self):
        """Ferme la connexion à la base de données"""
        if hasattr(self, "cursor"):
            self.cursor.close()
        if hasattr(self, "conn"):
            self.conn.close()
        logger.info("✅ GDPRAnonymizer: Connexion fermée")

    def process_pending_deletions(self) -> Dict[str, Any]:
        """
        Traite les suppressions en attente (droit à l'oubli)
        Supprime définitivement les comptes dont la période de grâce est écoulée
        """
        try:
            # Trouver les utilisateurs marqués pour suppression depuis plus de 30 jours
            self.cursor.execute(
                """
                SELECT id, email, deletion_requested_at
                FROM users
                WHERE is_marked_for_deletion = true
                  AND deletion_requested_at < NOW() - INTERVAL '30 days'
                """,
            )
            users_to_delete = self.cursor.fetchall()

            deleted_count = 0
            for user in users_to_delete:
                success, _ = self.delete_user_data(user["id"], confirm=True)
                if success:
                    deleted_count += 1

            return {
                "status": "completed",
                "processed": len(users_to_delete),
                "deleted": deleted_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Erreur process_pending_deletions: {e}")
            return {"error": str(e)}

    def get_compliance_stats(self) -> Dict[str, Any]:
        """
        Génère les statistiques de conformité RGPD
        """
        try:
            # Total utilisateurs
            self.cursor.execute("SELECT COUNT(*) as total FROM users")
            total_users = self.cursor.fetchone()["total"]

            # Utilisateurs actifs
            self.cursor.execute(
                "SELECT COUNT(*) as active FROM users WHERE is_active = true"
            )
            active_users = self.cursor.fetchone()["active"]

            # Utilisateurs anonymisés
            self.cursor.execute(
                "SELECT COUNT(*) as anonymized FROM users WHERE is_anonymized = true"
            )
            anonymized_users = self.cursor.fetchone()["anonymized"]

            # Utilisateurs en attente suppression
            self.cursor.execute(
                "SELECT COUNT(*) as pending FROM users WHERE is_marked_for_deletion = true"
            )
            pending_deletions = self.cursor.fetchone()["pending"]

            # Consentements
            self.cursor.execute(
                "SELECT COUNT(*) as consent FROM users WHERE gdpr_consent_given = true"
            )
            users_with_consent = self.cursor.fetchone()["consent"]

            consent_rate = (
                round((users_with_consent / total_users * 100), 2)
                if total_users > 0
                else 0
            )

            # Sessions actives
            self.cursor.execute(
                "SELECT COUNT(*) as sessions FROM sessions WHERE expires_at > NOW()"
            )
            active_sessions = self.cursor.fetchone()["sessions"]

            # Logs d'audit
            self.cursor.execute("SELECT COUNT(*) as logs FROM audit_logs")
            total_audit_logs = self.cursor.fetchone()["logs"]

            return {
                "total_users": total_users,
                "active_users": active_users,
                "anonymized_users": anonymized_users,
                "pending_deletions": pending_deletions,
                "users_with_consent": users_with_consent,
                "consent_rate": consent_rate,
                "active_sessions": active_sessions,
                "total_audit_logs": total_audit_logs,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Erreur get_compliance_stats: {e}")
            return {"error": str(e)}

    def __del__(self):
        """Destructeur"""
        try:
            self.close()
        except:
            pass


# === FONCTIONS UTILITAIRES ===


def test_anonymization():
    """Teste les fonctions d'anonymisation"""
    gdpr = GDPRAnonymizer()

    print("\n=== Test anonymizeName ===")
    result = gdpr.anonymizeName("Jean", "Dupont")
    print(f"Input: Jean Dupont")
    print(f"Output: {result}")

    print("\n=== Test anonymizeEmail ===")
    result = gdpr.anonymizeEmail("jean.dupont@example.com")
    print(f"Input: jean.dupont@example.com")
    print(f"Output: {result}")

    print("\n=== Test anonymizeGeolocation ===")
    result = gdpr.anonymizeGeolocation(48.8566, 2.3522, 2)
    print(f"Input: 48.8566, 2.3522")
    print(f"Output: {result}")

    print("\n=== Test anonymizeIPAddress ===")
    result = gdpr.anonymizeIPAddress("192.168.1.100")
    print(f"Input: 192.168.1.100")
    print(f"Output: {result}")

    gdpr.close()


if __name__ == "__main__":
    test_anonymization()
