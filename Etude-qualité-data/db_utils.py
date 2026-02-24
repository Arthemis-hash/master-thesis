#!/usr/bin/env python3
"""
============================================================
GESTIONNAIRE BASES DE DONNÉES - Brussels Air Quality
============================================================
Architecture Prisma + PostgreSQL + PostGIS
- Gestion asynchrone avec Prisma
- Support géospatial avec PostGIS
- Relations optimisées
- Transactions et batch operations
============================================================
"""

import logging
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import pandas as pd
from prisma import Prisma
from prisma.models import (
    Address, Station, AirQualityRecord, WeatherRecord,
    DataAnomaly, SatelliteDownload, StreetViewDownload,
    MetaScore
)

logger = logging.getLogger(__name__)

# ============================================================
# CLIENT PRISMA GLOBAL
# ============================================================

class DatabaseClient:
    """Client Prisma singleton pour gérer les connexions"""

    _instance: Optional[Prisma] = None
    _is_connected: bool = False

    @classmethod
    async def get_client(cls) -> Prisma:
        """Récupère ou crée le client Prisma"""
        if cls._instance is None:
            cls._instance = Prisma()

        if not cls._is_connected:
            await cls._instance.connect()
            cls._is_connected = True
            logger.info("✅ Prisma client connected to PostgreSQL")

        return cls._instance

    @classmethod
    async def disconnect(cls):
        """Ferme la connexion Prisma"""
        if cls._instance and cls._is_connected:
            await cls._instance.disconnect()
            cls._is_connected = False
            logger.info("🔌 Prisma client disconnected")


# ============================================================
# UTILITAIRES
# ============================================================

class DatabaseUtils:
    """Utilitaires pour normalisation et validation"""

    @staticmethod
    def sanitize_address(address: str) -> str:
        """
        Normalise adresse pour stockage unique
        Ex: "151 Boulevard du Triomphe, 1050 Bruxelles" -> "151_boulevard_du_triomphe_1050_bruxelles"
        """
        if not address:
            return "unknown"

        normalized = address.lower().strip()
        normalized = re.sub(r'[^\w\s-]', '_', normalized)
        normalized = re.sub(r'\s+', '_', normalized)
        normalized = re.sub(r'_+', '_', normalized)
        normalized = normalized.strip('_')

        if len(normalized) > 100:
            parts = normalized.split('_')
            if len(parts) > 4:
                normalized = '_'.join(parts[:3] + parts[-2:])
            normalized = normalized[:100]

        return normalized

    @staticmethod
    def parse_address_components(address: str) -> Dict[str, Optional[str]]:
        """
        Parse une adresse en composants
        Ex: "151 Boulevard du Triomphe, 1050 Bruxelles" ->
            {street_number: "151", street_name: "Boulevard du Triomphe", postal_code: "1050", city: "Bruxelles"}
        """
        components = {
            'street_number': None,
            'street_name': None,
            'postal_code': None,
            'city': None
        }

        # Recherche code postal (4 chiffres en Belgique)
        postal_match = re.search(r'\b(\d{4})\b', address)
        if postal_match:
            components['postal_code'] = postal_match.group(1)

        # Recherche numéro de rue au début
        number_match = re.match(r'^(\d+[a-zA-Z]?)\s+', address)
        if number_match:
            components['street_number'] = number_match.group(1)

        # Split par virgule pour extraire ville
        parts = [p.strip() for p in address.split(',')]
        if len(parts) >= 2:
            # Dernière partie contient souvent code postal + ville
            last_part = parts[-1]
            city_match = re.search(r'\d{4}\s+(.+)$', last_part)
            if city_match:
                components['city'] = city_match.group(1).strip()

            # Première partie contient numéro + rue
            if components['street_number']:
                street_name = parts[0].replace(components['street_number'], '').strip()
                components['street_name'] = street_name

        return components


# ============================================================
# GESTIONNAIRE ADRESSES
# ============================================================

class AddressManager:
    """Gestion des adresses avec géolocalisation"""

    def __init__(self):
        self.db: Optional[Prisma] = None

    async def _ensure_connected(self):
        """Assure que la connexion DB est active"""
        if not self.db:
            self.db = await DatabaseClient.get_client()

    async def get_or_create_address(
        self,
        full_address: str,
        latitude: float,
        longitude: float
    ) -> Address:
        """
        Récupère ou crée une adresse
        PostGIS crée automatiquement le point géométrique via trigger
        """
        await self._ensure_connected()

        normalized = DatabaseUtils.sanitize_address(full_address)
        components = DatabaseUtils.parse_address_components(full_address)

        # Vérifier si l'adresse existe
        existing = await self.db.address.find_unique(
            where={'normalizedAddress': normalized}
        )

        if existing:
            logger.info(f"📍 Adresse existante: {existing.id}")
            return existing

        # Créer nouvelle adresse
        address = await self.db.address.create(
            data={
                'fullAddress': full_address,
                'normalizedAddress': normalized,
                'streetNumber': components.get('street_number'),
                'streetName': components.get('street_name'),
                'postalCode': components.get('postal_code'),
                'city': components.get('city'),
                'latitude': latitude,
                'longitude': longitude,
            }
        )

        logger.info(f"✅ Nouvelle adresse créée: {address.id} - {full_address}")
        return address

    async def find_address(self, search: str) -> Optional[Address]:
        """Recherche une adresse par texte"""
        await self._ensure_connected()

        normalized = DatabaseUtils.sanitize_address(search)

        address = await self.db.address.find_unique(
            where={'normalizedAddress': normalized}
        )

        return address

    async def get_address_by_id(self, address_id: int) -> Optional[Address]:
        """Récupère adresse par ID"""
        await self._ensure_connected()

        return await self.db.address.find_unique(where={'id': address_id})

    async def list_all_addresses(self) -> List[Address]:
        """Liste toutes les adresses"""
        await self._ensure_connected()

        return await self.db.address.find_many(
            order={'createdAt': 'desc'}
        )


# ============================================================
# GESTIONNAIRE STATIONS
# ============================================================

class StationManager:
    """Gestion des stations de mesure (air quality + météo)"""

    def __init__(self):
        self.db: Optional[Prisma] = None

    async def _ensure_connected(self):
        if not self.db:
            self.db = await DatabaseClient.get_client()

    async def get_or_create_station(
        self,
        station_code: str,
        station_name: str,
        station_type: str,
        latitude: float,
        longitude: float,
        elevation: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> Station:
        """Récupère ou crée une station"""
        await self._ensure_connected()

        existing = await self.db.station.find_unique(
            where={'stationCode': station_code}
        )

        if existing:
            # Mettre à jour si nécessaire
            if existing.latitude != latitude or existing.longitude != longitude:
                existing = await self.db.station.update(
                    where={'id': existing.id},
                    data={
                        'latitude': latitude,
                        'longitude': longitude,
                        'stationName': station_name,
                        'elevation': elevation,
                        'metadata': metadata
                    }
                )
            return existing

        # Créer nouvelle station
        station = await self.db.station.create(
            data={
                'stationCode': station_code,
                'stationName': station_name,
                'stationType': station_type,
                'latitude': latitude,
                'longitude': longitude,
                'elevation': elevation,
                'metadata': metadata
            }
        )

        logger.info(f"✅ Station créée: {station_code} - {station_name}")
        return station

    async def find_stations_near_location(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float = 5000
    ) -> List[Dict]:
        """
        Trouve les stations dans un rayon (utilise la fonction PostGIS)
        """
        await self._ensure_connected()

        # Utiliser la fonction SQL personnalisée
        query = f"""
        SELECT * FROM find_stations_within_radius(
            {latitude}, {longitude}, {radius_meters}
        )
        """

        result = await self.db.query_raw(query)
        return result


# ============================================================
# GESTIONNAIRE QUALITÉ DE L'AIR
# ============================================================

class AirQualityManager:
    """Gestion des données de qualité de l'air"""

    # Mapping polluants API -> DB
    POLLUTANT_MAPPING = {
        'no2': 'nitrogenDioxide',
        'o3': 'ozone',
        'pm10': 'pm10',
        'pm2_5': 'pm25',
        'pm25': 'pm25',
        'so2': 'sulfurDioxide',
        'co': 'carbonMonoxide'
    }

    def __init__(self):
        self.db: Optional[Prisma] = None

    async def _ensure_connected(self):
        if not self.db:
            self.db = await DatabaseClient.get_client()

    async def insert_measurement(
        self,
        address_id: int,
        timestamp: datetime,
        pollutant: str,
        value: float,
        station_id: Optional[int] = None,
        data_source: str = "brussels_opendata"
    ) -> Optional[AirQualityRecord]:
        """
        Insert ou update une mesure de qualité d'air
        """
        await self._ensure_connected()

        # Mapper le polluant
        db_field = self.POLLUTANT_MAPPING.get(pollutant.lower())
        if not db_field:
            logger.warning(f"⚠️ Polluant inconnu: {pollutant}")
            return None

        # Vérifier si enregistrement existe
        existing = await self.db.airqualityrecord.find_first(
            where={
                'addressId': address_id,
                'timestamp': timestamp,
                'stationId': station_id
            }
        )

        if existing:
            # Update
            update_data = {db_field: value, 'dataSource': data_source}
            record = await self.db.airqualityrecord.update(
                where={'id': existing.id},
                data=update_data
            )
            logger.debug(f"🔄 Mesure mise à jour: {pollutant} = {value}")
        else:
            # Insert
            create_data = {
                'addressId': address_id,
                'timestamp': timestamp,
                'stationId': station_id,
                'dataSource': data_source,
                db_field: value
            }
            record = await self.db.airqualityrecord.create(data=create_data)
            logger.debug(f"✅ Nouvelle mesure: {pollutant} = {value}")

        # Vérifier anomalies
        await self._check_anomaly(record, pollutant, value)

        return record

    async def _check_anomaly(
        self,
        record: AirQualityRecord,
        pollutant: str,
        value: float
    ):
        """Détecte et enregistre les anomalies"""
        thresholds = {
            'pm10': 500,
            'pm25': 300,
            'nitrogenDioxide': 1000,
            'ozone': 600,
            'sulfurDioxide': 1000,
            'carbonMonoxide': 40000
        }

        db_field = self.POLLUTANT_MAPPING.get(pollutant.lower())
        threshold = thresholds.get(db_field)

        if threshold and value > threshold:
            await self.db.dataanomaly.create(
                data={
                    'recordType': 'air_quality',
                    'recordId': record.id,
                    'issueType': 'extreme_value',
                    'pollutant': pollutant,
                    'value': value,
                    'threshold': threshold,
                    'description': f'Valeur {pollutant} anormalement élevée: {value} > {threshold}'
                }
            )
            logger.warning(f"⚠️ Anomalie détectée: {pollutant} = {value}")

    async def batch_insert_measurements(
        self,
        address_id: int,
        df: pd.DataFrame,
        pollutant: str,
        station_id: Optional[int] = None
    ) -> Dict[str, int]:
        """
        Insertion en batch pour performance
        """
        await self._ensure_connected()

        stats = {'inserted': 0, 'updated': 0, 'errors': 0}

        for _, row in df.iterrows():
            try:
                record = await self.insert_measurement(
                    address_id=address_id,
                    timestamp=row['timestamp'],
                    pollutant=pollutant,
                    value=row['value'],
                    station_id=station_id
                )

                if record:
                    stats['inserted'] += 1
            except Exception as e:
                logger.error(f"❌ Erreur insertion: {e}")
                stats['errors'] += 1

        logger.info(f"📊 Batch {pollutant}: +{stats['inserted']} ❌{stats['errors']}")
        return stats

    async def get_measurements(
        self,
        address_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[AirQualityRecord]:
        """Récupère les mesures pour une adresse"""
        await self._ensure_connected()

        where_clause = {'addressId': address_id}

        if start_date or end_date:
            where_clause['timestamp'] = {}
            if start_date:
                where_clause['timestamp']['gte'] = start_date
            if end_date:
                where_clause['timestamp']['lte'] = end_date

        records = await self.db.airqualityrecord.find_many(
            where=where_clause,
            order={'timestamp': 'desc'},
            take=limit,
            include={'station': True, 'address': True}
        )

        return records

    async def get_summary_stats(self, address_id: int) -> Dict[str, Any]:
        """Statistiques résumées pour une adresse"""
        await self._ensure_connected()

        # Utiliser agrégation Prisma
        records = await self.db.airqualityrecord.find_many(
            where={'addressId': address_id}
        )

        if not records:
            return {}

        df = pd.DataFrame([r.dict() for r in records])

        summary = {
            'total_records': len(df),
            'date_range': {
                'start': df['timestamp'].min(),
                'end': df['timestamp'].max()
            },
            'averages': {
                'pm10': df['pm10'].mean() if 'pm10' in df else None,
                'pm25': df['pm25'].mean() if 'pm25' in df else None,
                'no2': df['nitrogenDioxide'].mean() if 'nitrogenDioxide' in df else None,
                'o3': df['ozone'].mean() if 'ozone' in df else None
            },
            'max_values': {
                'pm10': df['pm10'].max() if 'pm10' in df else None,
                'pm25': df['pm25'].max() if 'pm25' in df else None
            }
        }

        return summary


# ============================================================
# GESTIONNAIRE MÉTÉO
# ============================================================

class WeatherManager:
    """Gestion des données météo"""

    def __init__(self):
        self.db: Optional[Prisma] = None

    async def _ensure_connected(self):
        if not self.db:
            self.db = await DatabaseClient.get_client()

    async def insert_weather_data(
        self,
        address_id: int,
        timestamp: datetime,
        weather_data: Dict,
        station_id: Optional[int] = None,
        data_source: str = "irm"
    ) -> WeatherRecord:
        """Insert ou update donnée météo"""
        await self._ensure_connected()

        # Vérifier si existe
        existing = await self.db.weatherrecord.find_first(
            where={
                'addressId': address_id,
                'timestamp': timestamp,
                'stationId': station_id
            }
        )

        data = {
            'addressId': address_id,
            'timestamp': timestamp,
            'stationId': station_id,
            'dataSource': data_source,
            **weather_data
        }

        if existing:
            record = await self.db.weatherrecord.update(
                where={'id': existing.id},
                data=data
            )
        else:
            record = await self.db.weatherrecord.create(data=data)

        return record

    async def get_latest_weather(self, address_id: int) -> Optional[WeatherRecord]:
        """Dernière observation météo"""
        await self._ensure_connected()

        return await self.db.weatherrecord.find_first(
            where={'addressId': address_id},
            order={'timestamp': 'desc'},
            include={'station': True}
        )


# ============================================================
# EXPORT CLASSES
# ============================================================

__all__ = [
    'DatabaseClient',
    'DatabaseUtils',
    'AddressManager',
    'StationManager',
    'AirQualityManager',
    'WeatherManager'
]
