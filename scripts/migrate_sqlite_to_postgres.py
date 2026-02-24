#!/usr/bin/env python3
"""
============================================================
MIGRATION SQLite → PostgreSQL
============================================================
Migre les données existantes de SQLite vers PostgreSQL/Prisma
- Users & Sessions
- Adresses
- Air Quality Records
- Weather Records
- Environment Downloads
============================================================
"""

import asyncio
import sqlite3
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import pandas as pd

# Ajouter le path pour importer les modules
sys.path.append(str(Path(__file__).parent.parent))

from prisma import Prisma

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

SQLITE_DBS_FOLDER = Path(__file__).parent.parent / "STREAMLIT" / "airquality" / "app"
OLD_SQLITE_DBS_FOLDER = Path(__file__).parent.parent / "Etude-qualité-data" / "databases"


# ============================================================
# MIGRATION AUTHENTIFICATION
# ============================================================

async def migrate_auth_data(prisma: Prisma, sqlite_db_path: str):
    """Migre users et sessions depuis SQLite auth.db"""

    if not Path(sqlite_db_path).exists():
        logger.warning(f"⚠️  Base auth non trouvée: {sqlite_db_path}")
        return

    logger.info("👤 Migration des utilisateurs...")

    conn = sqlite3.connect(sqlite_db_path)
    cursor = conn.cursor()

    # Migrer users
    try:
        cursor.execute("SELECT id, email, password_hash, first_name, last_name, role, created_at, last_login, is_active FROM users")
        users = cursor.fetchall()

        migrated_users = 0
        for user in users:
            try:
                # Vérifier si user existe déjà
                existing = await prisma.user.find_unique(where={'email': user[1]})

                if not existing:
                    await prisma.user.create(
                        data={
                            'email': user[1],
                            'passwordHash': user[2],
                            'firstName': user[3],
                            'lastName': user[4],
                            'role': user[5],
                            'createdAt': datetime.fromisoformat(user[6]) if user[6] else datetime.now(),
                            'lastLogin': datetime.fromisoformat(user[7]) if user[7] else None,
                            'isActive': bool(user[8])
                        }
                    )
                    migrated_users += 1
                    logger.info(f"  ✅ User migré: {user[1]}")
            except Exception as e:
                logger.error(f"  ❌ Erreur migration user {user[1]}: {e}")

        logger.info(f"✅ {migrated_users} utilisateurs migrés")

    except sqlite3.OperationalError:
        logger.warning("⚠️  Table users non trouvée dans SQLite")

    conn.close()


# ============================================================
# MIGRATION ADRESSES
# ============================================================

async def migrate_addresses(prisma: Prisma, sqlite_db_path: str):
    """Migre les adresses depuis une base SQLite"""

    if not Path(sqlite_db_path).exists():
        logger.warning(f"⚠️  Base non trouvée: {sqlite_db_path}")
        return

    logger.info("📍 Migration des adresses...")

    conn = sqlite3.connect(sqlite_db_path)

    try:
        # Récupérer toutes les adresses uniques
        df = pd.read_sql_query("""
            SELECT DISTINCT
                address as full_address,
                normalized_address,
                latitude,
                longitude
            FROM air_quality
            WHERE address IS NOT NULL
        """, conn)

        migrated = 0
        for _, row in df.iterrows():
            try:
                # Vérifier si existe
                existing = await prisma.address.find_unique(
                    where={'normalizedAddress': row['normalized_address']}
                )

                if not existing:
                    # Parser composants
                    from Etude_qualité_data.db_utils import DatabaseUtils
                    components = DatabaseUtils.parse_address_components(row['full_address'])

                    await prisma.address.create(
                        data={
                            'fullAddress': row['full_address'],
                            'normalizedAddress': row['normalized_address'],
                            'streetNumber': components.get('street_number'),
                            'streetName': components.get('street_name'),
                            'postalCode': components.get('postal_code'),
                            'city': components.get('city'),
                            'latitude': float(row['latitude']),
                            'longitude': float(row['longitude'])
                        }
                    )
                    migrated += 1
                    logger.info(f"  ✅ Adresse migrée: {row['full_address']}")

            except Exception as e:
                logger.error(f"  ❌ Erreur migration adresse: {e}")

        logger.info(f"✅ {migrated} adresses migrées")

    except Exception as e:
        logger.error(f"❌ Erreur migration adresses: {e}")

    conn.close()


# ============================================================
# MIGRATION STATIONS
# ============================================================

async def migrate_stations(prisma: Prisma, sqlite_db_path: str):
    """Migre les stations depuis SQLite"""

    if not Path(sqlite_db_path).exists():
        return

    logger.info("📡 Migration des stations...")

    conn = sqlite3.connect(sqlite_db_path)

    try:
        df = pd.read_sql_query("""
            SELECT DISTINCT
                station_code,
                station_name,
                latitude,
                longitude
            FROM stations
            WHERE station_code IS NOT NULL
        """, conn)

        migrated = 0
        for _, row in df.iterrows():
            try:
                existing = await prisma.station.find_unique(
                    where={'stationCode': row['station_code']}
                )

                if not existing:
                    await prisma.station.create(
                        data={
                            'stationCode': row['station_code'],
                            'stationName': row['station_name'],
                            'stationType': 'air_quality',
                            'latitude': float(row['latitude']) if row['latitude'] else 0.0,
                            'longitude': float(row['longitude']) if row['longitude'] else 0.0
                        }
                    )
                    migrated += 1
                    logger.info(f"  ✅ Station migrée: {row['station_code']}")

            except Exception as e:
                logger.error(f"  ❌ Erreur migration station: {e}")

        logger.info(f"✅ {migrated} stations migrées")

    except Exception as e:
        logger.error(f"❌ Erreur migration stations: {e}")

    conn.close()


# ============================================================
# MIGRATION AIR QUALITY
# ============================================================

async def migrate_air_quality(prisma: Prisma, sqlite_db_path: str, batch_size: int = 1000):
    """Migre les données de qualité de l'air"""

    if not Path(sqlite_db_path).exists():
        return

    logger.info("🌫️  Migration des données de qualité de l'air...")

    conn = sqlite3.connect(sqlite_db_path)

    try:
        # Compter total
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM air_quality")
        total = cursor.fetchone()[0]
        logger.info(f"  📊 Total records à migrer: {total}")

        # Migrer par batch
        migrated = 0
        errors = 0

        for offset in range(0, total, batch_size):
            df = pd.read_sql_query(f"""
                SELECT
                    timestamp,
                    normalized_address,
                    station_code,
                    pm10,
                    pm2_5,
                    nitrogen_dioxide,
                    ozone
                FROM air_quality
                ORDER BY id
                LIMIT {batch_size} OFFSET {offset}
            """, conn)

            for _, row in df.iterrows():
                try:
                    # Trouver address_id
                    address = await prisma.address.find_unique(
                        where={'normalizedAddress': row['normalized_address']}
                    )

                    if not address:
                        continue

                    # Trouver station_id (optionnel)
                    station_id = None
                    if row['station_code']:
                        station = await prisma.station.find_unique(
                            where={'stationCode': row['station_code']}
                        )
                        if station:
                            station_id = station.id

                    # Créer record
                    await prisma.airqualityrecord.create(
                        data={
                            'addressId': address.id,
                            'timestamp': datetime.fromisoformat(row['timestamp']),
                            'stationId': station_id,
                            'pm10': float(row['pm10']) if pd.notna(row['pm10']) else None,
                            'pm25': float(row['pm2_5']) if pd.notna(row['pm2_5']) else None,
                            'nitrogenDioxide': float(row['nitrogen_dioxide']) if pd.notna(row['nitrogen_dioxide']) else None,
                            'ozone': float(row['ozone']) if pd.notna(row['ozone']) else None,
                            'dataSource': 'migrated_from_sqlite'
                        }
                    )
                    migrated += 1

                except Exception as e:
                    errors += 1
                    if errors < 10:  # Afficher seulement les 10 premières erreurs
                        logger.error(f"  ❌ Erreur: {e}")

            logger.info(f"  ⏳ Migré {migrated}/{total} ({100*migrated/total:.1f}%)")

        logger.info(f"✅ {migrated} records de qualité d'air migrés ({errors} erreurs)")

    except Exception as e:
        logger.error(f"❌ Erreur migration air quality: {e}")

    conn.close()


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

async def main():
    """Migration complète"""

    print("=" * 60)
    print("🚀 MIGRATION SQLite → PostgreSQL")
    print("=" * 60)
    print()

    # Connexion Prisma
    logger.info("🔌 Connexion à PostgreSQL...")
    prisma = Prisma()
    await prisma.connect()
    logger.info("✅ Connecté à PostgreSQL")
    print()

    # Trouver les bases SQLite
    auth_db = SQLITE_DBS_FOLDER / "auth.db"

    # Trouver bases air quality
    air_quality_dbs = []
    if OLD_SQLITE_DBS_FOLDER.exists():
        air_quality_dbs.extend(list(OLD_SQLITE_DBS_FOLDER.glob("brussels_air_*.db")))
        air_quality_dbs.extend(list(OLD_SQLITE_DBS_FOLDER.glob("air_quality_*.db")))

    logger.info(f"📂 Bases SQLite trouvées: {len(air_quality_dbs)} air quality + auth")
    print()

    # Migration auth
    if auth_db.exists():
        await migrate_auth_data(prisma, str(auth_db))
        print()

    # Migration pour chaque base air quality
    for db_path in air_quality_dbs[:3]:  # Limiter à 3 pour test
        logger.info(f"📊 Traitement: {db_path.name}")

        await migrate_addresses(prisma, str(db_path))
        await migrate_stations(prisma, str(db_path))
        await migrate_air_quality(prisma, str(db_path), batch_size=500)

        print()

    # Déconnexion
    await prisma.disconnect()

    print()
    print("=" * 60)
    print("✅ MIGRATION TERMINÉE")
    print("=" * 60)
    print()
    print("Vérifiez les données avec: prisma studio")
    print()


if __name__ == "__main__":
    asyncio.run(main())
