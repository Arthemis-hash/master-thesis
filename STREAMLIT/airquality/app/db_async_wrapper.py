#!/usr/bin/env python3
"""
============================================================
WRAPPER SYNCHRONE POUR FONCTIONS ASYNC PRISMA
============================================================
Permet d'utiliser les fonctions async de db_utils_postgres
dans du code synchrone comme Streamlit
============================================================
"""

import asyncio
import pandas as pd
from typing import Optional, Dict, List
import threading

from db_utils_postgres import (
    AirQualityDB as AirQualityDBAsync,
    WeatherDB as WeatherDBAsync,
    DatabaseManager as DatabaseManagerAsync,
    AddressManager,
    StationManager as StationManagerAsync
)
from db_environment import (
    EnvironmentDB as EnvironmentDBAsync,
    SatelliteDownloadManager,
    StreetViewDownloadManager,
    ImageAnalysisManager
)


# Event loop global pour éviter de créer/fermer à chaque appel
_loop = None
_loop_lock = threading.Lock()


def get_event_loop():
    """Récupère ou crée l'event loop réutilisable"""
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            # Ne pas set_event_loop pour éviter conflits avec Streamlit
        return _loop


def run_async(coro):
    """
    Execute une coroutine dans l'event loop réutilisable
    N'utilise PAS asyncio.run() car ça ferme le loop
    """
    loop = get_event_loop()

    # Si on est déjà dans un event loop (cas Streamlit parfois)
    try:
        if asyncio.get_running_loop():
            # Créer une nouvelle task dans le loop courant
            return asyncio.create_task(coro)
    except RuntimeError:
        # Pas de loop en cours, utiliser notre loop
        pass

    # Exécuter dans notre loop sans le fermer
    if not loop.is_running():
        return loop.run_until_complete(coro)
    else:
        # Si le loop tourne déjà (thread différent), créer future
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()


class AirQualityDB:
    """Wrapper synchrone pour AirQualityDB async"""

    def __init__(self, address: str = None, force_new: bool = False):
        self.async_db = AirQualityDBAsync(address=address)
        self.current_address = self.async_db.current_address
        self.normalized_address = self.async_db.normalized_address
        # Propriété db_path pour compatibilité (PostgreSQL n'utilise plus de fichiers)
        self._db_path = f"postgresql://airquality_db/{self.normalized_address}"

    @property
    def db_path(self) -> str:
        """Path virtuel pour compatibilité avec ancien système SQLite"""
        return self._db_path

    @db_path.setter
    def db_path(self, value: str):
        """Setter pour compatibilité, mais ignoré (PostgreSQL centralisé)"""
        self._db_path = value

    def insert_data(self, dataframe: pd.DataFrame, lat: float = 50.8503, lon: float = 4.3517, force_update: bool = False) -> bool:
        """Version synchrone de insert_data"""
        return run_async(self.async_db.insert_data(dataframe, lat, lon, force_update))

    def get_location_data(self, address: str = None) -> pd.DataFrame:
        """Version synchrone de get_location_data"""
        return run_async(self.async_db.get_location_data(address))

    def get_date_range(self, address: str = None) -> Optional[Dict]:
        """Version synchrone de get_date_range"""
        return run_async(self.async_db.get_date_range(address))

    def get_pollen_data(self, address: str = None) -> pd.DataFrame:
        """Version synchrone de get_pollen_data - récupère pollens depuis table séparée"""
        return run_async(self.async_db.get_pollen_data(address))

    def insert_pollen_data(self, dataframe: pd.DataFrame, lat: float = 50.8503, lon: float = 4.3517) -> bool:
        """Version synchrone de insert_pollen_data - stocke pollens dans table dédiée"""
        return run_async(self.async_db.insert_pollen_data(dataframe, lat, lon))

    def get_location_summary(self, address: str = None) -> Optional[Dict]:
        """
        Résumé air quality pour une adresse (compatible avec ancien système)
        Retourne statistiques agrégées depuis PostgreSQL
        """
        import logging
        logger = logging.getLogger(__name__)

        # Utiliser l'adresse courante si non spécifiée
        search_address = address or self.current_address

        # Normaliser l'adresse recherchée pour garantir la cohérence
        normalized_search = DatabaseManager.sanitize_address(search_address)

        # Récupérer toutes les données pour cette adresse
        df = self.get_location_data(search_address)

        if df.empty:
            logger.warning(f"📊 get_location_summary: DataFrame vide pour '{search_address}'")
            return None

        # Calculer statistiques (similaire à l'ancien get_location_summary)
        lat = df['latitude'].iloc[0] if 'latitude' in df.columns and len(df) > 0 else None
        lon = df['longitude'].iloc[0] if 'longitude' in df.columns and len(df) > 0 else None

        logger.info(f"📊 get_location_summary pour '{search_address}':")
        logger.info(f"   Adresse recherchée: '{search_address}'")
        logger.info(f"   Adresse normalisée: '{normalized_search}'")
        logger.info(f"   Coordonnées du DataFrame: lat={lat}, lon={lon}")
        logger.info(f"   Nombre de lignes dans DataFrame: {len(df)}")

        summary = {
            'address': search_address,
            'normalized_address': normalized_search,  # Utiliser l'adresse normalisée correcte
            'total_records': len(df),
            'avg_pm10': df['pm10'].mean() if 'pm10' in df.columns else None,
            'avg_pm2_5': df['pm2_5'].mean() if 'pm2_5' in df.columns else None,
            'avg_no2': df['nitrogen_dioxide'].mean() if 'nitrogen_dioxide' in df.columns else None,
            'avg_o3': df['ozone'].mean() if 'ozone' in df.columns else None,
            'avg_so2': df['sulphur_dioxide'].mean() if 'sulphur_dioxide' in df.columns else None,
            'avg_co': df['carbon_monoxide'].mean() if 'carbon_monoxide' in df.columns else None,
            'max_pm10': df['pm10'].max() if 'pm10' in df.columns else None,
            'max_pm2_5': df['pm2_5'].max() if 'pm2_5' in df.columns else None,
            'start_date': df['date'].min() if 'date' in df.columns else None,
            'end_date': df['date'].max() if 'date' in df.columns else None,
            'pollution_alert_pct': (df['pm2_5'] > 20).mean() * 100 if 'pm2_5' in df.columns else 0,
            'latitude': lat,
            'longitude': lon
        }

        return summary

    def get_qev_score(self, address: str = None) -> Optional[Dict]:
        """
        Calcule et retourne le score QeV pour une adresse.

        Args:
            address: Adresse à analyser (optionnel, utilise current_address si None)

        Returns:
            Dict avec tous les détails du score QeV ou None si impossible de calculer
        """
        import logging
        logger = logging.getLogger(__name__)

        from qev_service import QeVService

        # Utiliser l'adresse courante si non spécifiée
        search_address = address or self.current_address

        logger.info(f"🎯 Calcul QeV demandé pour adresse: '{search_address}'")

        # Récupérer les données air quality
        df = self.get_location_data(search_address)

        if df.empty:
            logger.warning(f"⚠️ Pas de données air quality pour '{search_address}' - QeV impossible")
            return None

        logger.info(f"✅ Données air quality récupérées: {len(df)} enregistrements")
        logger.info(f"   Colonnes disponibles: {list(df.columns)}")
        logger.info(f"   PM2.5 moyen: {df['pm2_5'].mean():.2f} μg/m³" if 'pm2_5' in df.columns else "   PM2.5: non disponible")
        logger.info(f"   NO2 moyen: {df['nitrogen_dioxide'].mean():.2f} μg/m³" if 'nitrogen_dioxide' in df.columns else "   NO2: non disponible")

        # Récupérer coordonnées
        summary = self.get_location_summary(search_address)
        if not summary or summary['latitude'] is None:
            logger.warning(f"⚠️ Coordonnées manquantes pour '{search_address}' - QeV impossible")
            return None

        latitude = summary['latitude']
        longitude = summary['longitude']

        logger.info(f"📍 Coordonnées pour QeV: lat={latitude:.6f}, lon={longitude:.6f}")

        # Utiliser le service QeV pour calculer
        qev_service = QeVService()

        try:
            qev_result = qev_service.calculate_qev_for_address(
                address=search_address,
                latitude=latitude,
                longitude=longitude,
                air_quality_df=df
                # traffic_data=None => estimation automatique via OSM Overpass
            )

            logger.info(f"✅ QeV calculé avec succès: {qev_result.get('QeV', 'N/A')}")

            # Persister le score QeV en base de données
            try:
                from db_utils_postgres import DatabaseClient, AddressManager

                normalized_scores = qev_result.get('normalized_scores', {})
                sub_indices = qev_result.get('sub_indices', {})
                weights = qev_result.get('weights', {})

                async def _persist_qev():
                    db = await DatabaseClient.get_client()
                    addr_mgr = AddressManager()
                    addr_record = await addr_mgr.get_or_create_address(
                        search_address, latitude, longitude
                    )
                    await db.qevscore.create(data={
                        'addressId': addr_record.id,
                        'qevScore': qev_result['QeV'],
                        'qevCategory': qev_result['QeV_category'],
                        'rawAirIndex': sub_indices.get('I_Air'),
                        'rawTrafficNuisance': sub_indices.get('I_Trafic'),
                        'rawGreenIndex': sub_indices.get('I_Vert'),
                        'normalizedAirScore': normalized_scores.get('S_Air'),
                        'normalizedTrafficScore': normalized_scores.get('S_Trafic'),
                        'normalizedGreenScore': normalized_scores.get('S_Vert'),
                        'weightAir': weights.get('air', 0.50),
                        'weightTraffic': weights.get('traffic', 0.25),
                        'weightGreen': weights.get('green', 0.25),
                    })
                    logger.info("✅ Score QeV persisté en PostgreSQL")

                run_async(_persist_qev())
            except Exception as db_err:
                logger.warning(f"⚠️ Impossible de persister le QeV en DB: {db_err}")

            return qev_result

        except Exception as e:
            logger.error(f"❌ Erreur calcul QeV: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None


class WeatherDB:
    """Wrapper synchrone pour WeatherDB async"""

    def __init__(self, address: str = None, force_new: bool = False):
        self.async_db = WeatherDBAsync(address=address)
        self.current_address = self.async_db.current_address
        self.normalized_address = self.async_db.normalized_address
        # Propriété db_path pour compatibilité (PostgreSQL n'utilise plus de fichiers)
        self._db_path = f"postgresql://airquality_db/{self.normalized_address}_weather"

    @property
    def db_path(self) -> str:
        """Path virtuel pour compatibilité avec ancien système SQLite"""
        return self._db_path

    @db_path.setter
    def db_path(self, value: str):
        """Setter pour compatibilité, mais ignoré (PostgreSQL centralisé)"""
        self._db_path = value

    def insert_data(self, dataframe: pd.DataFrame, lat: float = 50.8503, lon: float = 4.3517, force_update: bool = False) -> bool:
        """Version synchrone de insert_data"""
        return run_async(self.async_db.insert_data(dataframe, lat, lon, force_update))

    def get_hourly_forecast(self, address: str = None, hours: int = 24) -> pd.DataFrame:
        """Version synchrone de get_hourly_forecast"""
        return run_async(self.async_db.get_hourly_forecast(address, hours))

    def save_hourly_weather(self, address: str, lat: float, lon: float, hourly_df: pd.DataFrame) -> bool:
        """Version synchrone de save_hourly_weather"""
        return run_async(self.async_db.save_hourly_weather(address, lat, lon, hourly_df))

    def save_current_weather(self, address: str, lat: float, lon: float, current_data: Dict) -> bool:
        """Version synchrone de save_current_weather"""
        return run_async(self.async_db.save_current_weather(address, lat, lon, current_data))

    def save_daily_weather(self, address: str, lat: float, lon: float, daily_df: pd.DataFrame) -> bool:
        """Version synchrone de save_daily_weather"""
        return run_async(self.async_db.save_daily_weather(address, lat, lon, daily_df))

    def get_latest_current_weather(self, address: str = None) -> Optional[Dict]:
        """Version synchrone de get_latest_current_weather"""
        return run_async(self.async_db.get_latest_current_weather(address))

    def get_temperature_statistics(self, address: str = None) -> Dict:
        """Version synchrone de get_temperature_statistics"""
        return run_async(self.async_db.get_temperature_statistics(address))


class DatabaseManager:
    """Wrapper synchrone pour DatabaseManager async"""

    @staticmethod
    def sanitize_address(address: str) -> str:
        """Wrapper synchrone"""
        return DatabaseManagerAsync.sanitize_address(address)

    @staticmethod
    def list_all_databases(db_type: str = 'air_quality') -> List[Dict]:
        """Version synchrone de list_all_databases"""
        return run_async(DatabaseManagerAsync.list_all_databases(db_type))


class EnvironmentDB:
    """Wrapper synchrone pour EnvironmentDB async (données environnement)"""

    def __init__(self):
        self.async_db = EnvironmentDBAsync()
        self.satellite = self.async_db.satellite
        self.streetview = self.async_db.streetview
        self.analysis = self.async_db.analysis

    def get_latest_satellite_download(self, address_id: int) -> Optional[Dict]:
        """Récupère le dernier téléchargement satellite pour une adresse"""
        download = run_async(self.satellite.get_latest_download(address_id))
        if not download:
            return None

        return {
            'id': download.id,
            'address_id': download.addressId,
            'download_date': download.downloadDate,
            'radius_km': download.radiusKm,
            'zoom_levels': download.zoomLevels,
            'map_types': download.mapTypes,
            'total_images': download.totalImages,
            'output_directory': download.outputDirectory,
            'metadata': download.metadata
        }

    def get_latest_streetview_download(self, address_id: int) -> Optional[Dict]:
        """Récupère le dernier téléchargement street view pour une adresse"""
        download = run_async(self.streetview.get_latest_download(address_id))
        if not download:
            return None

        return {
            'id': download.id,
            'address_id': download.addressId,
            'download_date': download.downloadDate,
            'radius_m': download.radiusM,
            'total_photos': download.totalPhotos,
            'quality_filter': download.qualityFilterUsed,
            'output_directory': download.outputDirectory,
            'metadata': download.metadata
        }

    def get_all_downloads_summary(self, address_id: int) -> Dict:
        """Récupère résumé de tous les téléchargements pour une adresse"""
        return run_async(self.async_db.get_all_downloads_summary(address_id))

    def get_environment_statistics(self, address_id: int) -> Dict:
        """Calcule statistiques environnementales pour une adresse"""
        return run_async(self.async_db.get_environment_statistics(address_id))

    def insert_satellite_download(
        self,
        address_id: int,
        radius_km: float,
        zoom_levels: List[int],
        map_types: List[str],
        output_directory: str,
        metadata: Optional[Dict] = None
    ) -> int:
        """Version synchrone de insert_satellite_download"""
        return run_async(
            self.async_db.insert_satellite_download(
                address_id, radius_km, zoom_levels, map_types,
                output_directory, metadata
            )
        )

    def insert_streetview_download(
        self,
        address_id: int,
        radius_m: int,
        total_photos: int,
        output_directory: str,
        quality_filter_used: bool = True,
        metadata: Optional[Dict] = None
    ) -> int:
        """Version synchrone de insert_streetview_download"""
        return run_async(
            self.async_db.insert_streetview_download(
                address_id, radius_m, total_photos,
                quality_filter_used, output_directory, metadata
            )
        )

    def list_satellite_downloads(self, address_id: int) -> List[Dict]:
        """Liste tous les téléchargements satellite pour une adresse"""
        downloads = run_async(self.satellite.list_downloads_by_address(address_id))
        return [
            {
                'id': d.id,
                'download_date': d.downloadDate,
                'radius_km': d.radiusKm,
                'zoom_levels': d.zoomLevels,
                'map_types': d.mapTypes,
                'total_images': d.totalImages,
                'output_directory': d.outputDirectory
            }
            for d in downloads
        ]

    def list_streetview_downloads(self, address_id: int) -> List[Dict]:
        """Liste tous les téléchargements street view pour une adresse"""
        downloads = run_async(self.streetview.list_downloads_by_address(address_id))
        return [
            {
                'id': d.id,
                'download_date': d.downloadDate,
                'radius_m': d.radiusM,
                'total_photos': d.totalPhotos,
                'quality_filter': d.qualityFilterUsed,
                'output_directory': d.outputDirectory
            }
            for d in downloads
        ]

    def get_latest_analysis(
        self,
        image_type: Optional[str] = None,
        image_id: Optional[int] = None,
        analysis_type: Optional[str] = None
    ) -> Optional[Dict]:
        """Récupère la dernière analyse d'images"""
        analysis = run_async(self.analysis.get_latest_analysis(
            image_type=image_type,
            image_id=image_id,
            analysis_type=analysis_type
        ))
        if not analysis:
            return None

        return {
            'id': analysis.id,
            'image_type': analysis.imageType,
            'image_id': analysis.imageId,
            'analysis_type': analysis.analysisType,
            'model_name': analysis.modelName,
            'results': analysis.results,
            'statistics': analysis.statistics,
            'created_at': analysis.createdAt
        }


class AddressManagerWrapper:
    """Wrapper synchrone pour AddressManager"""

    def __init__(self):
        self.async_mgr = AddressManager()

    @staticmethod
    def sanitize_address(address: str) -> str:
        """Normalise une adresse (statique, pas besoin async)"""
        return AddressManager.sanitize_address(address)

    def find_address_by_normalized(self, normalized_address: str) -> Optional[Dict]:
        """Trouve une adresse par son nom normalisé"""
        addr = run_async(self.async_mgr.find_address_by_normalized(normalized_address))
        if not addr:
            return None

        return {
            'id': addr.id,
            'full_address': addr.fullAddress,
            'normalized_address': addr.normalizedAddress,
            'latitude': addr.latitude,
            'longitude': addr.longitude,
            'country': addr.country
        }

    def get_or_create_address(
        self,
        full_address: str,
        latitude: float,
        longitude: float
    ) -> Dict:
        """Récupère ou crée une adresse"""
        addr = run_async(
            self.async_mgr.get_or_create_address(full_address, latitude, longitude)
        )

        return {
            'id': addr.id,
            'full_address': addr.fullAddress,
            'normalized_address': addr.normalizedAddress,
            'latitude': addr.latitude,
            'longitude': addr.longitude,
            'country': addr.country
        }


class StationManager:
    """Wrapper synchrone pour StationManager async"""

    def __init__(self):
        self.async_mgr = StationManagerAsync()

    def get_all_stations(self, station_type: Optional[str] = None, active_only: bool = True) -> List[Dict]:
        """Version synchrone de get_all_stations"""
        return run_async(self.async_mgr.get_all_stations(station_type, active_only))

    def get_stations_near_location(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        station_type: Optional[str] = None
    ) -> List[Dict]:
        """Version synchrone de get_stations_near_location"""
        return run_async(
            self.async_mgr.get_stations_near_location(latitude, longitude, radius_km, station_type)
        )

    def get_station_by_code(self, station_code: str) -> Optional[Dict]:
        """Version synchrone de get_station_by_code"""
        return run_async(self.async_mgr.get_station_by_code(station_code))

    def create_station(
        self,
        station_code: str,
        station_name: str,
        station_type: str,
        latitude: float,
        longitude: float,
        elevation: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Version synchrone de create_station"""
        return run_async(
            self.async_mgr.create_station(
                station_code, station_name, station_type,
                latitude, longitude, elevation, metadata
            )
        )


# Export
__all__ = [
    'AirQualityDB',
    'WeatherDB',
    'DatabaseManager',
    'EnvironmentDB',
    'AddressManager',
    'AddressManagerWrapper',
    'StationManager'
]
