#!/usr/bin/env python3
"""
============================================================
SCRIPT D'AJOUT DE STATIONS D'EXEMPLE
============================================================
Ajoute des stations de mesure IRCELINE et IRM dans la base
de données pour la région de Bruxelles.
"""

import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

from db_utils_postgres import StationManager

# Charger variables d'environnement
env_path = Path(__file__).parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Stations IRCELINE de la région de Bruxelles
# Source: https://www.irceline.be/fr/documentation/open-data
IRCELINE_STATIONS = [
    {
        'station_code': 'BELAB001',
        'station_name': 'Bruxelles - Arts-Loi',
        'station_type': 'air_quality',
        'latitude': 50.8448,
        'longitude': 4.3672,
        'elevation': 53,
        'metadata': {
            'network': 'IRCELINE',
            'station_area_type': 'urban',
            'station_feature': 'traffic',
            'pollutants': ['PM10', 'PM2.5', 'NO2', 'O3', 'BC']
        }
    },
    {
        'station_code': 'BELAB002',
        'station_name': 'Bruxelles - Berchem-Sainte-Agathe',
        'station_type': 'air_quality',
        'latitude': 50.8656,
        'longitude': 4.2975,
        'elevation': 58,
        'metadata': {
            'network': 'IRCELINE',
            'station_area_type': 'urban',
            'station_feature': 'background',
            'pollutants': ['PM10', 'PM2.5', 'NO2', 'O3', 'SO2']
        }
    },
    {
        'station_code': 'BELAB004',
        'station_name': 'Bruxelles - Haren',
        'station_type': 'air_quality',
        'latitude': 50.8906,
        'longitude': 4.4061,
        'elevation': 48,
        'metadata': {
            'network': 'IRCELINE',
            'station_area_type': 'urban',
            'station_feature': 'background',
            'pollutants': ['PM10', 'NO2', 'O3']
        }
    },
    {
        'station_code': 'BELAB005',
        'station_name': 'Bruxelles - Ixelles',
        'station_type': 'air_quality',
        'latitude': 50.8275,
        'longitude': 4.3719,
        'elevation': 65,
        'metadata': {
            'network': 'IRCELINE',
            'station_area_type': 'urban',
            'station_feature': 'background',
            'pollutants': ['PM10', 'PM2.5', 'NO2', 'O3']
        }
    },
    {
        'station_code': 'BELAB006',
        'station_name': 'Bruxelles - Molenbeek',
        'station_type': 'air_quality',
        'latitude': 50.8572,
        'longitude': 4.3136,
        'elevation': 28,
        'metadata': {
            'network': 'IRCELINE',
            'station_area_type': 'urban',
            'station_feature': 'background',
            'pollutants': ['PM10', 'NO2', 'O3']
        }
    },
]

# Stations météo IRM (Institut Royal Météorologique)
IRM_STATIONS = [
    {
        'station_code': 'IRM_UCCLE',
        'station_name': 'Uccle (IRM)',
        'station_type': 'weather',
        'latitude': 50.7981,
        'longitude': 4.3586,
        'elevation': 100,
        'metadata': {
            'network': 'IRM',
            'station_type_detail': 'synoptic',
            'wmo_id': '06447',
            'measurements': [
                'temperature', 'precipitation', 'wind_speed',
                'wind_direction', 'humidity', 'pressure', 'sunshine'
            ]
        }
    },
    {
        'station_code': 'IRM_ZAVENTEM',
        'station_name': 'Zaventem Aéroport (IRM)',
        'station_type': 'weather',
        'latitude': 50.9014,
        'longitude': 4.4844,
        'elevation': 56,
        'metadata': {
            'network': 'IRM',
            'station_type_detail': 'aeronautical',
            'wmo_id': '06451',
            'icao_code': 'EBBR',
            'measurements': [
                'temperature', 'precipitation', 'wind_speed',
                'wind_direction', 'humidity', 'pressure', 'visibility'
            ]
        }
    },
]


async def add_example_stations():
    """Ajoute les stations d'exemple dans la base de données"""
    logger.info("=" * 60)
    logger.info("🚀 AJOUT DE STATIONS D'EXEMPLE")
    logger.info("=" * 60)

    station_mgr = StationManager()

    # Compter les stations existantes
    existing_stations = await station_mgr.get_all_stations(active_only=False)
    logger.info(f"📊 Stations existantes: {len(existing_stations)}")

    all_stations = IRCELINE_STATIONS + IRM_STATIONS
    added_count = 0
    skipped_count = 0

    for station_data in all_stations:
        try:
            # Vérifier si la station existe déjà
            existing = await station_mgr.get_station_by_code(station_data['station_code'])

            if existing:
                logger.info(f"⏭️  Station {station_data['station_code']} existe déjà - ignorée")
                skipped_count += 1
                continue

            # Créer la station
            result = await station_mgr.create_station(
                station_code=station_data['station_code'],
                station_name=station_data['station_name'],
                station_type=station_data['station_type'],
                latitude=station_data['latitude'],
                longitude=station_data['longitude'],
                elevation=station_data.get('elevation'),
                metadata=station_data.get('metadata')
            )

            logger.info(f"✅ Station créée: {result['station_name']} ({result['station_code']})")
            logger.info(f"   📍 Position: {result['latitude']:.6f}, {result['longitude']:.6f}")
            added_count += 1

        except Exception as e:
            logger.error(f"❌ Erreur création station {station_data['station_code']}: {e}")

    logger.info("=" * 60)
    logger.info(f"📊 RÉSUMÉ:")
    logger.info(f"   ✅ Stations ajoutées: {added_count}")
    logger.info(f"   ⏭️  Stations ignorées (déjà existantes): {skipped_count}")
    logger.info(f"   📈 Total de stations: {len(existing_stations) + added_count}")
    logger.info("=" * 60)

    # Afficher les stations par type
    all_stations_after = await station_mgr.get_all_stations(active_only=False)

    air_quality_count = len([s for s in all_stations_after if s['station_type'] == 'air_quality'])
    weather_count = len([s for s in all_stations_after if s['station_type'] == 'weather'])

    logger.info(f"🌬️  Stations qualité de l'air: {air_quality_count}")
    logger.info(f"🌤️  Stations météo: {weather_count}")
    logger.info("=" * 60)


def main():
    """Point d'entrée principal"""
    try:
        asyncio.run(add_example_stations())
        logger.info("✅ Script terminé avec succès!")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'exécution: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
