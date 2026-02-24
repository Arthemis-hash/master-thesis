#!/usr/bin/env python3
"""
Script de nettoyage et optimisation après migration PostgreSQL
- Supprime fichiers OLD/backup
- Nettoie __pycache__
- Crée backup des bases SQLite
- Génère rapport d'optimisation
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

def cleanup_old_files():
    """Supprime les fichiers OLD et backup"""
    print("\n" + "="*60)
    print("NETTOYAGE DES FICHIERS OLD/BACKUP")
    print("="*60)

    app_dir = Path(__file__).parent / 'app'
    old_files = []

    # Chercher fichiers OLD
    for file in app_dir.glob('*_OLD.py'):
        old_files.append(file)

    if old_files:
        print(f"\n📋 {len(old_files)} fichiers OLD trouvés:")
        for f in old_files:
            print(f"   - {f.name} ({f.stat().st_size / 1024:.1f} KB)")

        response = input("\n❓ Voulez-vous supprimer ces fichiers? (y/N): ")
        if response.lower() == 'y':
            for f in old_files:
                f.unlink()
                print(f"   ✅ Supprimé: {f.name}")
            print(f"\n✅ {len(old_files)} fichiers supprimés")
        else:
            print("⏭️  Fichiers conservés")
    else:
        print("✅ Aucun fichier OLD trouvé")


def cleanup_pycache():
    """Nettoie tous les __pycache__"""
    print("\n" + "="*60)
    print("NETTOYAGE __pycache__")
    print("="*60)

    root_dir = Path(__file__).parent
    pycache_dirs = list(root_dir.rglob('__pycache__'))

    if pycache_dirs:
        print(f"\n📋 {len(pycache_dirs)} dossiers __pycache__ trouvés")

        total_size = 0
        for d in pycache_dirs:
            for f in d.glob('*.pyc'):
                total_size += f.stat().st_size

        print(f"💾 Espace occupé: {total_size / 1024:.1f} KB")

        response = input("\n❓ Voulez-vous nettoyer? (y/N): ")
        if response.lower() == 'y':
            for d in pycache_dirs:
                shutil.rmtree(d)
            print(f"✅ {len(pycache_dirs)} dossiers supprimés")
        else:
            print("⏭️  __pycache__ conservés")
    else:
        print("✅ Aucun __pycache__ trouvé")


def backup_sqlite_databases():
    """Crée un backup des bases SQLite"""
    print("\n" + "="*60)
    print("BACKUP DES BASES SQLite")
    print("="*60)

    db_dir = Path(__file__).parent / 'app' / 'databases'

    if not db_dir.exists():
        print("⚠️  Aucun dossier databases trouvé")
        return

    sqlite_files = list(db_dir.glob('*.db'))

    if sqlite_files:
        print(f"\n📋 {len(sqlite_files)} bases SQLite trouvées")

        total_size = sum(f.stat().st_size for f in sqlite_files) / (1024 * 1024)
        print(f"💾 Taille totale: {total_size:.2f} MB")

        backup_dir = Path(__file__).parent / 'sqlite_backup'

        response = input(f"\n❓ Créer backup dans {backup_dir.name}? (y/N): ")
        if response.lower() == 'y':
            backup_dir.mkdir(exist_ok=True)

            for f in sqlite_files:
                dest = backup_dir / f.name
                shutil.copy2(f, dest)
                print(f"   ✅ Copié: {f.name}")

            print(f"\n✅ Backup créé dans: {backup_dir}")
            print(f"   Total: {len(sqlite_files)} fichiers ({total_size:.2f} MB)")
        else:
            print("⏭️  Backup annulé")
    else:
        print("ℹ️  Aucune base SQLite trouvée")


def check_code_duplication():
    """Vérifie les duplications de code"""
    print("\n" + "="*60)
    print("VÉRIFICATION DUPLICATIONS CODE")
    print("="*60)

    app_dir = Path(__file__).parent / 'app'

    # Fichiers de base de données
    db_files = {
        'db_utils.py': 'SQLite (ancien)',
        'db_utils_postgres.py': 'PostgreSQL/Prisma (async)',
        'db_async_wrapper.py': 'Wrapper synchrone pour Streamlit'
    }

    print("\n📊 Fichiers de gestion base de données:")
    for filename, description in db_files.items():
        filepath = app_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size / 1024
            print(f"   ✅ {filename:25} - {description:30} ({size:.1f} KB)")
        else:
            print(f"   ❌ {filename:25} - MANQUANT")

    # Fichiers d'authentification
    auth_files = {
        'auth.py': 'UI authentification Streamlit',
        'auth_db.py': 'Gestion DB auth (Prisma)',
        'auth_manager.py': 'Manager authentification'
    }

    print("\n📊 Fichiers d'authentification:")
    for filename, description in auth_files.items():
        filepath = app_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size / 1024
            print(f"   ✅ {filename:25} - {description:30} ({size:.1f} KB)")


def generate_optimization_report():
    """Génère un rapport d'optimisation"""
    print("\n" + "="*60)
    print("RAPPORT D'OPTIMISATION")
    print("="*60)

    report_lines = []
    report_lines.append("# RAPPORT D'OPTIMISATION POST-MIGRATION\n")
    report_lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    # Architecture actuelle
    report_lines.append("## ARCHITECTURE ACTUELLE\n\n")
    report_lines.append("```\n")
    report_lines.append("app.py\n")
    report_lines.append("  └─> db_async_wrapper.py (Wrapper synchrone)\n")
    report_lines.append("       └─> db_utils_postgres.py (PostgreSQL/Prisma async)\n")
    report_lines.append("            └─> Prisma Client\n")
    report_lines.append("                 └─> PostgreSQL (airquality_db)\n")
    report_lines.append("```\n\n")

    # Fichiers actifs
    app_dir = Path(__file__).parent / 'app'
    py_files = sorted([f for f in app_dir.glob('*.py') if not f.name.startswith('_')])

    report_lines.append("## FICHIERS ACTIFS\n\n")
    for f in py_files:
        size = f.stat().st_size / 1024
        report_lines.append(f"- {f.name:30} ({size:6.1f} KB)\n")

    # Recommandations
    report_lines.append("\n## RECOMMANDATIONS\n\n")

    if (app_dir / 'db_utils.py').exists():
        report_lines.append("### ⚠️ Ancien fichier SQLite présent\n")
        report_lines.append("- **Fichier**: `db_utils.py`\n")
        report_lines.append("- **Action**: Conserver en backup ou supprimer\n")
        report_lines.append("- **Statut**: Plus utilisé (remplacé par db_async_wrapper.py)\n\n")

    report_lines.append("### ✅ Optimisations possibles\n\n")
    report_lines.append("1. **Centraliser .env**\n")
    report_lines.append("   - Actuellement: 3 copies du fichier .env\n")
    report_lines.append("   - Recommandation: 1 seul fichier à la racine\n\n")

    report_lines.append("2. **Ajouter indexes PostGIS**\n")
    report_lines.append("   - Pour requêtes spatiales sur addresses.geom\n")
    report_lines.append("   - Améliore performances recherche géographique\n\n")

    report_lines.append("3. **Implémenter cache**\n")
    report_lines.append("   - Redis pour statistiques fréquemment demandées\n")
    report_lines.append("   - Réduit charge PostgreSQL\n\n")

    report_lines.append("4. **Vues matérialisées**\n")
    report_lines.append("   - Pour statistiques complexes\n")
    report_lines.append("   - Refresh périodique\n\n")

    # Écrire le rapport
    report_path = Path(__file__).parent / 'OPTIMIZATION_REPORT.md'
    report_path.write_text(''.join(report_lines))

    print(f"\n✅ Rapport généré: {report_path.name}")
    print(f"   Consultez le fichier pour les recommandations détaillées")


def main():
    print("\n" + "🧹 " + "="*58)
    print("   NETTOYAGE & OPTIMISATION POST-MIGRATION")
    print("   " + "="*58)

    try:
        # 1. Nettoyage fichiers OLD
        cleanup_old_files()

        # 2. Nettoyage __pycache__
        cleanup_pycache()

        # 3. Backup SQLite
        backup_sqlite_databases()

        # 4. Vérification duplications
        check_code_duplication()

        # 5. Rapport d'optimisation
        generate_optimization_report()

        print("\n" + "="*60)
        print("✅ NETTOYAGE TERMINÉ")
        print("="*60)
        print("\nProchaines étapes recommandées:")
        print("1. Consulter OPTIMIZATION_REPORT.md")
        print("2. Tester l'application: streamlit run app/app.py")
        print("3. Monitorer les performances PostgreSQL")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
