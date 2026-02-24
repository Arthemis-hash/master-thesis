#!/usr/bin/env python3
"""
============================================================
INTERFACE CLI - OPÉRATIONS RGPD
============================================================
Menu interactif pour les tâches d'administration RGPD

Usage:
    python scripts/gdpr/cli.py

Options:
    1. Anonymiser un utilisateur (droit à l'oubli)
    2. Supprimer complètement un utilisateur
    3. Exporter les données d'un utilisateur
    4. Anonymisation en masse (utilisateurs inactifs)
    5. Statistiques de conformité
    6. Nettoyer les anciens logs d'audit
    7. Traiter les suppressions en attente
    8. Quitter
"""

import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(
    0, str(Path(__file__).parent.parent.parent / "STREAMLIT" / "airquality" / "app")
)

from gdpr_anonymizer_sync import GDPRAnonymizer


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def clear_screen():
    """Efface l'écran du terminal"""
    os.system("cls" if os.name == "nt" else "clear")


def print_header():
    """Affiche l'en-tête du menu"""
    print("\n" + "=" * 60)
    print("   🛡️  INTERFACE D'ADMINISTRATION RGPD")
    print("   Brussels Air Quality Platform")
    print("=" * 60 + "\n")


def print_menu():
    """Affiche le menu principal"""
    print("📋 MENU PRINCIPAL")
    print("-" * 40)
    print("1. 👤 Anonymiser un utilisateur (Article 17)")
    print("2. 🗑️  Supprimer complètement un utilisateur")
    print("3. 📥 Exporter les données d'un utilisateur (Article 15)")
    print("4. 🔄 Anonymisation en masse (comptes inactifs)")
    print("5. 📊 Statistiques de conformité RGPD")
    print("6. 🧹 Nettoyer les anciens logs d'audit")
    print("7. ⏳ Traiter les suppressions en attente")
    print("8. ❌ Quitter")
    print("-" * 40)


def get_user_input(prompt: str, default: str = None) -> str:
    """Récupère une entrée utilisateur avec valeur par défaut"""
    if default:
        response = input(f"{prompt} [{default}]: ").strip()
        return response if response else default
    return input(f"{prompt}: ").strip()


def anonymize_single_user(gdpr: GDPRAnonymizer):
    """Anonymise un utilisateur spécifique"""
    print("\n🔐 ANONYMISATION D'UN UTILISATEUR")
    print("-" * 40)
    print("Cette action est IRRÉVERSIBLE.")
    print("L'identité de l'utilisateur sera remplacée par un hash.")
    print("-" * 40)

    user_id = get_user_input("ID de l'utilisateur à anonymiser")

    if not user_id.isdigit():
        print("❌ ID invalide")
        return

    user_id = int(user_id)

    confirm = get_user_input(
        f"Confirmer l'anonymisation du user {user_id}? (oui/non)", default="non"
    ).lower()

    if confirm not in ["oui", "o", "yes", "y"]:
        print("❌ Opération annulée")
        return

    success, message = gdpr.anonymize_user(user_id)

    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")


def delete_user(gdpr: GDPRAnonymizer):
    """Supprime complètement un utilisateur"""
    print("\n🗑️  SUPPRESSION DÉFINITIVE")
    print("-" * 40)
    print("⚠️  ATTENTION: Cette action est IRRÉVERSIBLE!")
    print("Toutes les données seront PERDUES DÉFINITIVEMENT.")
    print("-" * 40)

    user_id = get_user_input("ID de l'utilisateur à supprimer")

    if not user_id.isdigit():
        print("❌ ID invalide")
        return

    user_id = int(user_id)

    confirm1 = get_user_input(
        f"Êtes-vous sûr de vouloir supprimer le user {user_id}? (écrire 'SUPPRIMER')",
        default="",
    )

    if confirm1 != "SUPPRIMER":
        print("❌ Opération annulée (confirmation incorrecte)")
        return

    success, message = gdpr.delete_user_data(user_id, confirm=True)

    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")


def export_user_data(gdpr: GDPRAnonymizer):
    """Exporte les données d'un utilisateur"""
    print("\n📥 EXPORT DES DONNÉES UTILISATEUR")
    print("-" * 40)
    print("Article 15 - Droit d'accès")
    print("-" * 40)

    user_id = get_user_input("ID de l'utilisateur")

    if not user_id.isdigit():
        print("❌ ID invalide")
        return

    user_id = int(user_id)

    export_data = gdpr.export_user_data(user_id)

    if not export_data:
        print("❌ Utilisateur introuvable ou erreur")
        return

    filename = get_user_input(
        "Nom du fichier de sortie",
        default=f"export_user_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )

    filepath = Path(__file__).parent.parent / "exports" / filename
    filepath.parent.mkdir(exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, default=str)

    print(f"✅ Données exportées vers: {filepath}")


def batch_anonymize(gdpr: GDPRAnonymizer):
    """Anonymisation en masse des comptes inactifs"""
    print("\n🔄 ANONYMISATION EN MASSE")
    print("-" * 40)
    print("Cette opération anonymise les comptes inactifs depuis")
    print("plus de 2 ans (730 jours) par défaut.")
    print("-" * 40)

    inactive_days = get_user_input(
        "Jours d'inactivité avant anonymisation", default="730"
    )

    if not inactive_days.isdigit():
        print("❌ Nombre invalide")
        return

    confirm = get_user_input(
        "Confirmer l'anonymisation en masse? (oui/non)", default="non"
    ).lower()

    if confirm not in ["oui", "o", "yes", "y"]:
        print("❌ Opération annulée")
        return

    print("\n⏳ Traitement en cours...")

    result = gdpr.batch_anonymize_inactive_users(inactive_days=int(inactive_days))

    print("\n📊 RÉSULTAT:")
    print(f"  - Utilisateurs traités: {result.get('processed', 0)}")
    print(f"  - Réussis: {result.get('successful', 0)}")
    print(f"  - Échoués: {result.get('failed', 0)}")

    if result.get("successful", 0) > 0:
        print("\n✅ Anonymisation en masse terminée")


def show_compliance_stats(gdpr: GDPRAnonymizer):
    """Affiche les statistiques de conformité"""
    print("\n📊 STATISTIQUES DE CONFORMITÉ RGPD")
    print("=" * 50)

    stats = gdpr.get_compliance_stats()

    print(f"\n👥 UTILISATEURS:")
    print(f"  - Total: {stats['total_users']}")
    print(f"  - Actifs: {stats['active_users']}")
    print(f"  - Anonymisés: {stats['anonymized_users']}")
    print(f"  - En attente suppression: {stats['pending_deletions']}")

    print(f"\n✅ CONSENTEMENT:")
    print(f"  - Avec consentement: {stats['users_with_consent']}")
    print(f"  - Taux de consentement: {stats['consent_rate']}%")

    print(f"\n🔐 SESSIONS:")
    print(f"  - Total: {stats['total_sessions']}")

    print(f"\n📅 POLITIQUE DE RÉTENTION:")
    policy = stats["retention_policy"]
    print(f"  - Utilisateurs inactifs: {policy['inactive_user_days']} jours")
    print(
        f"  - Période de grâce suppression: {policy['deleted_user_grace_period']} jours"
    )
    print(f"  - Logs d'audit: {policy['audit_log_days']} jours")
    print(f"  - Géolocalisation: {policy['geolocation_days']} jours")
    print(f"  - Adresses IP: {policy['ip_address_days']} jours")


def clean_audit_logs(gdpr: GDPRAnonymizer):
    """Nettoie les anciens logs d'audit"""
    print("\n🧹 NETTOYAGE DES LOGS D'AUDIT")
    print("-" * 40)

    days = get_user_input("Supprimer les logs plus vieux que (jours)", default="365")

    if not days.isdigit():
        print("❌ Nombre invalide")
        return

    confirm = get_user_input(
        f"Confirmer la suppression des logs de plus de {days} jours? (oui/non)",
        default="non",
    ).lower()

    if confirm not in ["oui", "o", "yes", "y"]:
        print("❌ Opération annulée")
        return

    deleted = gdpr.clean_old_audit_logs(days=int(days))
    print(f"✅ {deleted} logs supprimés")


def process_pending_deletions(gdpr: GDPRAnonymizer):
    """Traite les suppressions en attente après période de grâce"""
    print("\n⏳ TRAITEMENT DES SUPPRESSIONS EN ATTENTE")
    print("-" * 40)
    print("Cette opération supprime définitivement les comptes")
    print("dont la période de grâce de 30 jours est écoulée.")
    print("-" * 40)

    confirm = get_user_input(
        "Confirmer le traitement? (oui/non)", default="non"
    ).lower()

    if confirm not in ["oui", "o", "yes", "y"]:
        print("❌ Opération annulée")
        return

    result = gdpr.process_pending_deletions()

    print(f"\n📊 RÉSULTAT:")
    print(f"  - Comptes traités: {result.get('processed', 0)}")
    print(f"  - Supprimés: {result.get('deleted', 0)}")


def main():
    """Point d'entrée principal"""
    clear_screen()
    print_header()

    gdpr = GDPRAnonymizer()

    while True:
        print_menu()
        choice = get_user_input("Choix", default="8")

        clear_screen()
        print_header()

        try:
            if choice == "1":
                anonymize_single_user(gdpr)
            elif choice == "2":
                delete_user(gdpr)
            elif choice == "3":
                export_user_data(gdpr)
            elif choice == "4":
                batch_anonymize(gdpr)
            elif choice == "5":
                show_compliance_stats(gdpr)
            elif choice == "6":
                clean_audit_logs(gdpr)
            elif choice == "7":
                process_pending_deletions(gdpr)
            elif choice == "8":
                print("👋 Au revoir!")
                break
            else:
                print("❌ Choix invalide")
        except Exception as e:
            print(f"❌ Erreur: {e}")
            logger.exception("Erreur CLI RGPD")

        input("\n⏎ Appuyez sur Entrée pour continuer...")
        clear_screen()
        print_header()


if __name__ == "__main__":
    main()
