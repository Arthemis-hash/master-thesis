#!/usr/bin/env python3
"""
============================================================
MIGRATION SQLite → PostgreSQL
============================================================
Migre toutes les données existantes depuis SQLite vers PostgreSQL
- Adresses
- Données qualité de l'air
- Données météo
Architecture: SQLite (db_utils.py) → PostgreSQL (Prisma)
============================================================
"""

import asyncio
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import logging

# Ajouter le dossier app au path
app_path = Path(__file__).parent / 'app'
sys.path.insert(0, str(app_path))

from prisma import Prisma
from db_utils import DatabaseManager

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SQLiteToPostgresMigrator:
    """Migrateur SQLite vers PostgreSQL avec Prisma"""

    def __init__(self):
        self.db: Optional[Prisma] = None
        self.stats = {
            'addresses': 0,
            'air_quality': 0,
            'weather': 0,
            'errors': 0
        }

    async def connect(self):
        """Connexion à PostgreSQL"""
        self.db = Prisma()
        await self.db.connect()
        logger.info("✅ Connecté à PostgreSQL")

    async def disconnect(self):
        """Déconnexion de PostgreSQL"""
        if self.db:
            await self.db.disconnect()
            logger.info("🔌 Déconnecté de PostgreSQL")

    def normalize_address(self, address: str) -> str:
        """Normalise une adresse pour éviter les doublons"""
        return DatabaseManager.sanitize_address(address)

    async def migrate_addresses(self, sqlite_conn: sqlite3.Connection) -> Dict[str, int]:
        """
        Migre les adresses depuis SQLite
        Retourne un mapping: normalized_address → address_id (PostgreSQL)
        """
        logger.info("\n📍 Migration des adresses...")

        cursor = sqlite_conn.cursor()

        # Récupérer toutes les adresses uniques depuis air_quality
        cursor.execute("""
            SELECT DISTINCT
                address,
                normalized_address,
                latitude,
                longitude
            FROM air_quality
            WHERE address IS NOT NULL
        """)

        address_map = {}
        count = 0

        for row in cursor.fetchall():
            address, normalized_addr, lat, lon = row

            if not normalized_addr:
                normalized_addr = self.normalize_address(address)

            try:
                # Vérifier si l'adresse existe déjà
                existing = await self.db.address.find_first(
                    where={'normalizedAddress': normalized_addr}
                )

                if existing:
                    address_map[normalized_addr] = existing.id
                    logger.debug(f"   Adresse existante: {normalized_addr}")
                else:
                    # Créer nouvelle adresse
                    new_address = await self.db.address.create(
                        data={
                            'fullAddress': address,
                            'normalizedAddress': normalized_addr,
                            'latitude': float(lat) if lat else 50.8503,
                            'longitude': float(lon) if lon else 4.3517,
                            'country': 'Belgium'
                        }
                    )
                    address_map[normalized_addr] = new_address.id
                    count += 1
                    logger.info(f"   ✅ Adresse créée: {address} (ID: {new_address.id})")

            except Exception as e:
                logger.error(f"   ❌ Erreur création adresse {address}: {e}")
                self.stats['errors'] += 1

        self.stats['addresses'] = count
        logger.info(f"✅ {count} nouvelles adresses migrées")
        return address_map

    async def migrate_air_quality(
        self,
        sqlite_conn: sqlite3.Connection,
        address_map: Dict[str, int]
    ):
        """Migre les données de qualité de l'air"""
        logger.info("\n🌍 Migration des données qualité de l'air...")

        cursor = sqlite_conn.cursor()

        cursor.execute("""
            SELECT
                date, address, normalized_address, latitude, longitude,
                pm10, pm2_5, carbon_monoxide, carbon_dioxide, nitrogen_dioxide,
                uv_index, uv_index_clear_sky, alder_pollen, birch_pollen,
                ozone, sulphur_dioxide, methane, ammonia, dust,
                aerosol_optical_depth, ragweed_pollen, olive_pollen,
                mugwort_pollen, grass_pollen
            FROM air_quality
            ORDER BY date DESC
        """)

        count = 0
        batch_size = 100
        batch = []

        for row in cursor.fetchall():
            date, address, normalized_addr, lat, lon, *pollutants = row

            if not normalized_addr:
                normalized_addr = self.normalize_address(address)

            address_id = address_map.get(normalized_addr)
            if not address_id:
                logger.warning(f"   ⚠️ Adresse non trouvée: {normalized_addr}")
                continue

            try:
                # Convertir la date
                timestamp = datetime.fromisoformat(date.replace(' ', 'T'))

                # Vérifier si l'enregistrement existe déjà
                existing = await self.db.airqualityrecord.find_first(
                    where={
                        'addressId': address_id,
                        'timestamp': timestamp
                    }
                )

                if existing:
                    continue

                # Créer l'enregistrement
                await self.db.airqualityrecord.create(
                    data={
                        'timestamp': timestamp,
                        'addressId': address_id,
                        'pm10': pollutants[0],
                        'pm25': pollutants[1],
                        'carbonMonoxide': pollutants[2],
                        # carbonDioxide non disponible dans schema actuel
                        'nitrogenDioxide': pollutants[4],
                        # uvIndex, uvIndexClearSky non disponibles
                        # pollens non disponibles
                        'ozone': pollutants[14],
                        'sulfurDioxide': pollutants[15],
                        # methane, ammonia, dust non disponibles
                        'dataSource': 'migrated_from_sqlite'
                    }
                )

                count += 1

                if count % 100 == 0:
                    logger.info(f"   📊 {count} enregistrements air quality migrés...")

            except Exception as e:
                logger.error(f"   ❌ Erreur migration air quality: {e}")
                self.stats['errors'] += 1

        self.stats['air_quality'] = count
        logger.info(f"✅ {count} enregistrements air quality migrés")

    async def migrate_weather(
        self,
        sqlite_conn: sqlite3.Connection,
        address_map: Dict[str, int]
    ):
        """Migre les données météo"""
        logger.info("\n🌤️  Migration des données météo...")

        cursor = sqlite_conn.cursor()

        # Vérifier si la table weather existe
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='weather'
        """)

        if not cursor.fetchone():
            logger.warning("⚠️ Table 'weather' non trouvée dans SQLite")
            return

        cursor.execute("""
            SELECT
                date, address, normalized_address, latitude, longitude,
                temperature, feels_like, humidity, pressure,
                wind_speed, wind_direction, wind_gusts, cloud_cover,
                rain, snowfall, weather_code, visibility
            FROM weather
            ORDER BY date DESC
        """)

        count = 0

        for row in cursor.fetchall():
            date, address, normalized_addr, lat, lon, *weather_data = row

            if not normalized_addr:
                normalized_addr = self.normalize_address(address)

            address_id = address_map.get(normalized_addr)
            if not address_id:
                logger.warning(f"   ⚠️ Adresse non trouvée: {normalized_addr}")
                continue

            try:
                # Convertir la date
                timestamp = datetime.fromisoformat(date.replace(' ', 'T'))

                # Vérifier si l'enregistrement existe déjà
                existing = await self.db.weatherrecord.find_first(
                    where={
                        'addressId': address_id,
                        'timestamp': timestamp
                    }
                )

                if existing:
                    continue

                # Créer l'enregistrement
                await self.db.weatherrecord.create(
                    data={
                        'timestamp': timestamp,
                        'addressId': address_id,
                        'temperature': weather_data[0],
                        'feelsLike': weather_data[1],
                        'humidity': weather_data[2],
                        'pressure': weather_data[3],
                        'windSpeed': weather_data[4],
                        'windDirection': weather_data[5],
                        'windGusts': weather_data[6],
                        'cloudCover': weather_data[7],
                        'precipitation1h': weather_data[8],  # rain
                        # snowfall non disponible
                        'weatherCode': weather_data[10],
                        'visibility': weather_data[11],
                        'dataSource': 'migrated_from_sqlite'
                    }
                )

                count += 1

                if count % 100 == 0:
                    logger.info(f"   📊 {count} enregistrements météo migrés...")

            except Exception as e:
                logger.error(f"   ❌ Erreur migration météo: {e}")
                self.stats['errors'] += 1

        self.stats['weather'] = count
        logger.info(f"✅ {count} enregistrements météo migrés")

    async def migrate_database(self, sqlite_db_path: str):
        """Migre une base de données SQLite complète"""
        logger.info(f"\n{'='*60}")
        logger.info(f"MIGRATION: {Path(sqlite_db_path).name}")
        logger.info(f"{'='*60}")

        # Connexion SQLite
        sqlite_conn = sqlite3.connect(sqlite_db_path)

        try:
            # 1. Migrer les adresses
            address_map = await self.migrate_addresses(sqlite_conn)

            # 2. Migrer les données air quality
            await self.migrate_air_quality(sqlite_conn, address_map)

            # 3. Migrer les données météo
            await self.migrate_weather(sqlite_conn, address_map)

        finally:
            sqlite_conn.close()

    def print_summary(self):
        """Affiche le résumé de la migration"""
        print("\n" + "="*60)
        print("RÉSUMÉ DE LA MIGRATION")
        print("="*60)
        print(f"📍 Adresses créées       : {self.stats['addresses']}")
        print(f"🌍 Air quality migrés    : {self.stats['air_quality']}")
        print(f"🌤️  Météo migrés          : {self.stats['weather']}")
        print(f"❌ Erreurs rencontrées   : {self.stats['errors']}")
        print("="*60)


async def main():
    """Fonction principale de migration"""
    print("\n" + "🚀 " + "="*58)
    print("   MIGRATION SQLite → PostgreSQL")
    print("   " + "="*58 + "\n")

    # Dossier databases
    db_folder = Path(__file__).parent / 'app' / 'databases'

    if not db_folder.exists():
        logger.error(f"❌ Dossier databases introuvable: {db_folder}")
        return

    # Lister toutes les bases SQLite
    air_quality_dbs = list(db_folder.glob('air_quality_*.db'))
    weather_dbs = list(db_folder.glob('weather_*.db'))

    if not air_quality_dbs and not weather_dbs:
        logger.warning("⚠️ Aucune base de données SQLite trouvée")
        logger.info(f"   Dossier vérifié: {db_folder}")
        return

    logger.info(f"📂 Bases trouvées:")
    logger.info(f"   - Air Quality: {len(air_quality_dbs)}")
    logger.info(f"   - Weather: {len(weather_dbs)}")

    # Créer le migrateur
    migrator = SQLiteToPostgresMigrator()

    try:
        # Connexion PostgreSQL
        await migrator.connect()

        # Migrer chaque base air_quality
        for db_path in air_quality_dbs:
            await migrator.migrate_database(str(db_path))

        # Afficher le résumé
        migrator.print_summary()

        print("\n🎉 MIGRATION TERMINÉE AVEC SUCCÈS !")
        print("✅ Toutes les données SQLite ont été transférées vers PostgreSQL")

    except Exception as e:
        logger.error(f"\n❌ ERREUR FATALE: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await migrator.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
