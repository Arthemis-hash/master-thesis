#!/usr/bin/env python3
"""
============================================================
TÂCHES PROGRAMMÉES (CRON JOBS) - RGPD
============================================================
Scripts pour automatisation des tâches de conformité RGPD

Configuration Cron:
------------------
# Anonymisation automatique des comptes inactifs
0 2 * * * cd /path/to/project && python scripts/gdpr/scheduled_jobs.py anonymize

# Nettoyage des logs d'audit anciens (hebdomadaire)
0 3 * * 0 cd /path/to/project && python scripts/gdpr/scheduled_jobs.py clean-logs

# Traitement des suppressions en attente
0 4 * * * cd /path/to/project && python scripts/gdpr/scheduled_jobs.py process-deletions

# Statistiques quotidiennes
0 5 * * * cd /path/to/project && python scripts/gdpr/scheduled_jobs.py stats
"""

import sys
import os
import logging
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(
    0, str(Path(__file__).parent.parent.parent / "STREAMLIT" / "airquality" / "app")
)

from gdpr_anonymizer_sync import GDPRAnonymizer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("/var/log/gdpr_cron.log")],
)
logger = logging.getLogger(__name__)


def run_anonymization():
    """
    Tâche 1: Anonymisation automatique des comptes inactifs

    Exécution: Tous les jours à 2h du matin

    Anonymise les comptes utilisateurs qui n'ont pas été actifs
    depuis plus de 730 jours (2 ans)
    """
    logger.info("=== Début anonymisation automatique ===")

    gdpr = GDPRAnonymizer()

    try:
        result = gdpr.batch_anonymize_inactive_users(inactive_days=730, batch_size=100)

        logger.info(f"Résultat: {result}")

        if result.get("successful", 0) > 0:
            logger.info(f"✅ {result['successful']} utilisateurs anonymisés")
        else:
            logger.info("Aucun utilisateur à anonymiser")

        return result

    except Exception as e:
        logger.error(f"❌ Erreur anonymisation: {e}")
        raise


def run_clean_logs():
    """
    Tâche 2: Nettoyage des logs d'audit anciens

    Exécution: Tous les dimanches à 3h du matin

    Supprime les logs d'audit de plus de 365 jours (1 an)
    """
    logger.info("=== Début nettoyage logs d'audit ===")

    gdpr = GDPRAnonymizer()

    try:
        deleted = gdpr.clean_old_audit_logs(days=365)

        logger.info(f"✅ {deleted} logs supprimés")

        return {"deleted": deleted}

    except Exception as e:
        logger.error(f"❌ Erreur nettoyage logs: {e}")
        raise


def run_process_deletions():
    """
    Tâche 3: Traitement des suppressions en attente

    Exécution: Tous les jours à 4h du matin

    Supprime définitivement les comptes dont la période de grâce
    de 30 jours est écoulée
    """
    logger.info("=== Début traitement suppressions en attente ===")

    gdpr = GDPRAnonymizer()

    try:
        result = gdpr.process_pending_deletions()

        logger.info(f"Résultat: {result}")

        if result.get("deleted", 0) > 0:
            logger.info(f"✅ {result['deleted']} comptes supprimés définitivement")
        else:
            logger.info("Aucune suppression à traiter")

        return result

    except Exception as e:
        logger.error(f"❌ Erreur traitement suppressions: {e}")
        raise


def run_stats():
    """
    Tâche 4: Génération des statistiques quotidiennes

    Exécution: Tous les jours à 5h du matin

    Génère un rapport de conformité RGPD
    """
    logger.info("=== Génération statistiques quotidiennes ===")

    gdpr = GDPRAnonymizer()

    try:
        stats = gdpr.get_compliance_stats()

        logger.info(f"""
========================================
STATISTIQUES CONFORMITÉ RGPD - {datetime.now().strftime("%Y-%m-%d")}
========================================

UTILISATEURS:
- Total: {stats["total_users"]}
- Actifs: {stats["active_users"]}
- Anonymisés: {stats["anonymized_users"]}
- En attente suppression: {stats["pending_deletions"]}

CONSENTEMENT:
- Avec consentement: {stats["users_with_consent"]}
- Taux: {stats["consent_rate"]}%

SESSIONS:
- Total: {stats["total_sessions"]}
========================================
        """)

        return stats

    except Exception as e:
        logger.error(f"❌ Erreur statistiques: {e}")
        raise


def run_all():
    """Exécute toutes les tâches dans l'ordre"""
    logger.info("=== Exécution complète tâches RGPD ===")

    results = {}

    results["anonymization"] = run_anonymization()
    results["clean_logs"] = run_clean_logs()
    results["process_deletions"] = run_process_deletions()
    results["stats"] = run_stats()

    logger.info("=== Toutes les tâches terminées ===")

    return results


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description="Tâches cron RGPD")

    parser.add_argument(
        "task",
        choices=["anonymize", "clean-logs", "process-deletions", "stats", "all"],
        help="Tâche à exécuter",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Simulation sans modification"
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.warning("🔍 Mode DRY-RUN activé - aucune modification ne sera effectuée")

    start_time = datetime.now()
    logger.info(f"🕐 Début tâche: {args.task} à {start_time}")

    try:
        if args.task == "anonymize":
            if not args.dry_run:
                run_anonymization()
            else:
                logger.info("DRY-RUN: Serait passé à anonymisation")

        elif args.task == "clean-logs":
            if not args.dry_run:
                run_clean_logs()
            else:
                logger.info("DRY-RUN: Serait passé au nettoyage des logs")

        elif args.task == "process-deletions":
            if not args.dry_run:
                run_process_deletions()
            else:
                logger.info("DRY-RUN: Serait passé au traitement des suppressions")

        elif args.task == "stats":
            run_stats()

        elif args.task == "all":
            if not args.dry_run:
                run_all()
            else:
                logger.info("DRY-RUN: Serait passé à toutes les tâches")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"✅ Tâche '{args.task}' terminée en {duration:.2f}s")

    except Exception as e:
        logger.error(f"❌ Échec de la tâche '{args.task}': {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
