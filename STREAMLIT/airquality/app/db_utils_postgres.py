#!/usr/bin/env python3
"""
============================================================
MODULE DE GESTION DES BASES DE DONNÉES - PostgreSQL/Prisma
============================================================
Remplacement de db_utils.py (SQLite) par version PostgreSQL
Gestion de DEUX bases de données distinctes via Prisma:
- AirQualityDB : Données de qualité de l'air
- WeatherDB : Données météorologiques

Architecture: PostgreSQL + Prisma + PostGIS
============================================================
"""

# ============================================================
# IMPORTS
# ============================================================
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import pandas as pd

from prisma import Prisma
from prisma.models import Address, AirQualityRecord, WeatherRecord

logger = logging.getLogger(__name__)


# ============================================================
# CLIENT PRISMA SINGLETON
# ============================================================

class DatabaseClient:
    """Client Prisma singleton partagé"""

    _instance: Optional[Prisma] = None
    _is_connected: bool = False
    _loop: Optional[object] = None

    @classmethod
    async def get_client(cls) -> Prisma:
        """Récupère ou crée le client Prisma"""
        import asyncio
        current_loop = asyncio.get_running_loop()

        # Si le loop a changé (reload Streamlit), on doit recréer le client
        if cls._is_connected and cls._loop is not None and cls._loop is not current_loop:
            logger.warning("⚠️ Event loop changed (Streamlit reload?). Resetting Prisma client.")
            if cls._instance:
                try:
                    await cls._instance.disconnect()
                except Exception:
                    pass # Ignore errors on disconnect from dead loop
            cls._instance = None
            cls._is_connected = False

        if cls._instance is None:
            cls._instance = Prisma()

        if not cls._is_connected:
            await cls._instance.connect()
            cls._is_connected = True
            cls._loop = current_loop
            logger.info("✅ Prisma DB client connected")

        return cls._instance

    @classmethod
    async def disconnect(cls):
        """Ferme la connexion"""
        if cls._instance and cls._is_connected:
            await cls._instance.disconnect()
            cls._is_connected = False
            cls._loop = None
            logger.info("🔌 Prisma DB client disconnected")


# ============================================================
# GESTIONNAIRE D'ADRESSES
# ============================================================

class AddressManager:
    """Gestion des adresses géolocalisées"""

    def __init__(self):
        self.db: Optional[Prisma] = None

    async def _ensure_connected(self):
        if not self.db:
            self.db = await DatabaseClient.get_client()

    @staticmethod
    def sanitize_address(address: str) -> str:
        """Normalise une adresse"""
        import re

        # Si l'adresse est déjà normalisée (commence par code_postal_), la retourner telle quelle
        if re.match(r'^\d{4,5}_', address):
            return address[:50]

        # Extraire code postal et ville
        parts = address.split(',')
        postal_code = None
        city = None

        for part in parts:
            part = part.strip()
            # Chercher code postal seulement au début de la partie
            if not postal_code:
                postal_match = re.match(r'^(\d{4,5})\b', part)
                if postal_match:
                    postal_code = postal_match.group(1)

            city_keywords = ['bruxelles', 'brussels', 'brussel', 'ixelles', 'elsene',
                           'schaerbeek', 'etterbeek', 'anderlecht', 'molenbeek']
            if any(keyword in part.lower() for keyword in city_keywords):
                # Enlever le code postal du début si présent
                city_part = re.sub(r'^(\d{4,5})\s*', '', part)
                city = re.sub(r'[^\w\s-]', '', city_part).strip()

        if postal_code and city:
            normalized = f"{postal_code}_{re.sub(r'\s+', '_', city.lower())}"
        elif postal_code:
            normalized = postal_code
        elif city:
            normalized = re.sub(r'\s+', '_', city.lower())
        else:
            first_part = parts[0].strip()
            normalized = re.sub(r'[^\w\s-]', '', first_part)
            normalized = re.sub(r'\s+', '_', normalized.lower())

        return normalized[:50]

    async def get_or_create_address(
        self,
        full_address: str,
        latitude: float,
        longitude: float
    ) -> Address:
        """Récupère ou crée une adresse"""
        await self._ensure_connected()

        normalized = self.sanitize_address(full_address)

        # Chercher adresse existante
        existing = await self.db.address.find_first(
            where={'normalizedAddress': normalized}
        )

        if existing:
            # Mettre à jour les coordonnées si elles ont changé
            if existing.latitude != latitude or existing.longitude != longitude:
                logger.info(f"🔄 Mise à jour coordonnées pour {normalized}: "
                          f"({existing.latitude}, {existing.longitude}) → ({latitude}, {longitude})")
                updated = await self.db.address.update(
                    where={'id': existing.id},
                    data={
                        'latitude': latitude,
                        'longitude': longitude,
                        'fullAddress': full_address  # Mettre à jour aussi le nom complet
                    }
                )
                return updated
            return existing

        # Créer nouvelle adresse
        new_address = await self.db.address.create(
            data={
                'fullAddress': full_address,
                'normalizedAddress': normalized,
                'latitude': latitude,
                'longitude': longitude,
                'country': 'Belgium'
            }
        )

        logger.info(f"✅ Adresse créée: {normalized} (ID: {new_address.id})")
        return new_address

    async def find_address_by_normalized(self, normalized_address: str) -> Optional[Address]:
        """Trouve une adresse par son nom normalisé"""
        await self._ensure_connected()

        return await self.db.address.find_first(
            where={'normalizedAddress': normalized_address}
        )


# ============================================================
# CLASSE : BASE DE DONNÉES AIR QUALITY (PostgreSQL)
# ============================================================

class AirQualityDB:
    """Base de données PostgreSQL pour la qualité de l'air"""

    def __init__(self, address: str = None):
        """
        Initialise la base Air Quality avec Prisma

        Args:
            address: Adresse pour laquelle gérer les données
        """
        self.current_address = address or "Bruxelles"
        self.normalized_address = AddressManager.sanitize_address(self.current_address)
        self.db: Optional[Prisma] = None
        self.address_manager = AddressManager()
        self.address_id: Optional[int] = None

        logger.info(f"✅ AirQualityDB (Prisma) initialisée: {self.current_address}")

    async def _ensure_connected(self):
        """Assure connexion active"""
        if not self.db:
            self.db = await DatabaseClient.get_client()

    async def _ensure_address(self, lat: float = 50.8503, lon: float = 4.3517):
        """Assure que l'adresse existe"""
        if not self.address_id:
            address = await self.address_manager.get_or_create_address(
                self.current_address, lat, lon
            )
            self.address_id = address.id

    async def insert_data(self, dataframe: pd.DataFrame, lat: float = 50.8503, lon: float = 4.3517, force_update: bool = False) -> bool:
        """
        Insère nouvelles données dans PostgreSQL (optimisé batch).

        Stratégie: 1 SELECT pour récupérer tous les timestamps existants,
        puis 1 create_many pour les nouveaux enregistrements.
        Élimine le pattern N+1 (anciennement N SELECTs + N INSERTs).

        Args:
            dataframe: DataFrame avec nouvelles données
            lat: Latitude
            lon: Longitude
            force_update: Si True, met à jour les enregistrements existants au lieu de les ignorer

        Returns:
            True si succès
        """
        if dataframe is None or dataframe.empty:
            logger.error("❌ DataFrame vide")
            return False

        try:
            await self._ensure_connected()
            await self._ensure_address(lat, lon)

            # Préparer les timestamps du DataFrame
            df_timestamps = [pd.to_datetime(row['date']) for _, row in dataframe.iterrows()]
            min_ts = min(df_timestamps)
            max_ts = max(df_timestamps)

            # 1 seul SELECT: récupérer tous les timestamps existants pour cette plage
            existing_records = await self.db.airqualityrecord.find_many(
                where={
                    'addressId': self.address_id,
                    'timestamp': {'gte': min_ts, 'lte': max_ts}
                }
            )
            existing_ts_set = {r.timestamp for r in existing_records}
            existing_by_ts = {r.timestamp: r for r in existing_records}

            logger.info(f"📊 Batch insert: {len(dataframe)} lignes, {len(existing_ts_set)} existantes")

            # Séparer les nouvelles données des existantes
            new_records = []
            updated = 0
            skipped = 0

            for _, row in dataframe.iterrows():
                timestamp = pd.to_datetime(row['date'])

                if timestamp in existing_ts_set:
                    if force_update:
                        # Mise à jour individuelle (inévitable pour UPDATE)
                        existing = existing_by_ts[timestamp]
                        await self.db.airqualityrecord.update(
                            where={'id': existing.id},
                            data={
                                'pm10': row.get('pm10'),
                                'pm25': row.get('pm2_5'),
                                'carbonMonoxide': row.get('carbon_monoxide'),
                                'nitrogenDioxide': row.get('nitrogen_dioxide'),
                                'ozone': row.get('ozone'),
                                'sulfurDioxide': row.get('sulphur_dioxide'),
                                'dataSource': 'openmeteo'
                            }
                        )
                        updated += 1
                    else:
                        skipped += 1
                    continue

                # Ajouter aux nouveaux enregistrements pour batch insert
                new_records.append({
                    'timestamp': timestamp,
                    'addressId': self.address_id,
                    'pm10': row.get('pm10'),
                    'pm25': row.get('pm2_5'),
                    'carbonMonoxide': row.get('carbon_monoxide'),
                    'nitrogenDioxide': row.get('nitrogen_dioxide'),
                    'ozone': row.get('ozone'),
                    'sulfurDioxide': row.get('sulphur_dioxide'),
                    'dataSource': 'openmeteo'
                })

            # Batch INSERT en une seule requête
            inserted = 0
            if new_records:
                result = await self.db.airqualityrecord.create_many(
                    data=new_records,
                    skip_duplicates=True
                )
                inserted = result

            logger.info(f"✅ Air quality: {inserted} nouveaux, {updated} mis à jour, {skipped} ignorés")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur insertion globale: {e}")
            return False

    async def get_location_data(self, address: str = None) -> pd.DataFrame:
        """
        Récupère données air quality pour une adresse

        Returns:
            DataFrame avec les données
        """
        await self._ensure_connected()

        if address is None:
            address = self.current_address

        normalized = AddressManager.sanitize_address(address)

        logger.info(f"🔍 get_location_data - Recherche adresse:")
        logger.info(f"   Input address: '{address}'")
        logger.info(f"   Normalized: '{normalized}'")
        logger.info(f"   self.current_address: '{self.current_address}'")

        # Trouver l'adresse
        addr = await self.address_manager.find_address_by_normalized(normalized)

        if not addr:
            logger.warning(f"⚠️ Adresse non trouvée dans la base: '{normalized}'")
            return pd.DataFrame()

        logger.info(f"✅ Adresse trouvée: ID={addr.id}, coords=({addr.latitude}, {addr.longitude})")

        # Récupérer les données
        records = await self.db.airqualityrecord.find_many(
            where={'addressId': addr.id},
            order={'timestamp': 'desc'}
        )

        if not records:
            logger.warning(f"⚠️ Aucun enregistrement pour addressId={addr.id}")
            return pd.DataFrame()

        # Convertir en DataFrame
        data = []
        for record in records:
            # Utiliser getattr pour TOUS les champs optionnels (protection contre désync Prisma)
            data.append({
                'date': record.timestamp,
                'address': addr.fullAddress,
                'normalized_address': addr.normalizedAddress,
                'latitude': addr.latitude,
                'longitude': addr.longitude,

                # Polluants principaux (colonnes réelles de air_quality_records)
                'pm10': getattr(record, 'pm10', None),
                'pm2_5': getattr(record, 'pm25', None),
                'nitrogen_dioxide': getattr(record, 'nitrogenDioxide', None),
                'ozone': getattr(record, 'ozone', None),
                'sulphur_dioxide': getattr(record, 'sulfurDioxide', None),
                'carbon_monoxide': getattr(record, 'carbonMonoxide', None),

                # Indices AQI
                'aqi_value': getattr(record, 'aqiValue', None),
                'aqi_category': getattr(record, 'aqiCategory', None),
            })

        return pd.DataFrame(data)

    async def get_pollen_data(self, address: str = None) -> pd.DataFrame:
        """
        Récupère données pollens depuis la table pollen_records

        Returns:
            DataFrame avec les données pollens (noms utilisateur-friendly)
        """
        await self._ensure_connected()

        if address is None:
            address = self.current_address

        normalized = AddressManager.sanitize_address(address)
        addr = await self.address_manager.find_address_by_normalized(normalized)

        if not addr:
            logger.warning(f"⚠️ Adresse non trouvée pour pollens: '{normalized}'")
            return pd.DataFrame()

        # Récupérer les données pollens
        records = await self.db.pollenrecord.find_many(
            where={'addressId': addr.id},
            order={'timestamp': 'desc'}
        )

        if not records:
            logger.info(f"ℹ️ Aucun enregistrement pollen pour addressId={addr.id}")
            return pd.DataFrame()

        # Mapping noms botaniques → noms utilisateur-friendly
        data = []
        for record in records:
            data.append({
                'date': record.timestamp,
                'address': addr.fullAddress,
                # Pollens avec noms courants
                'grass_pollen': getattr(record, 'graminaceae', None) or getattr(record, 'poaceae', None),
                'birch_pollen': getattr(record, 'betula', None),
                'alder_pollen': getattr(record, 'alnus', None),
                'hazel_pollen': getattr(record, 'corylus', None),
                'cypress_pollen': getattr(record, 'cupressaceae', None),
                'poplar_pollen': getattr(record, 'populus', None),
                'oak_pollen': getattr(record, 'quercus', None),
                'ash_pollen': getattr(record, 'fraxinus', None),
                'plane_pollen': getattr(record, 'platanus', None),
                'nettle_pollen': getattr(record, 'urticaceae', None),
                'mugwort_pollen': getattr(record, 'artemisia', None),
                'ragweed_pollen': getattr(record, 'ambrosia', None),
                'plantain_pollen': getattr(record, 'plantago', None),
                'chenopod_pollen': getattr(record, 'chenopod', None),
                'total_pollen': getattr(record, 'totalPollen', None),
            })

        logger.info(f"✅ Pollens récupérés: {len(data)} enregistrements")
        return pd.DataFrame(data)

    async def insert_pollen_data(self, dataframe: pd.DataFrame, lat: float = 50.8503, lon: float = 4.3517) -> bool:
        """
        Insère données pollens dans la table pollen_records.
        Le DataFrame doit contenir les colonnes Open-Meteo: alder_pollen, birch_pollen, grass_pollen, etc.
        
        Args:
            dataframe: DataFrame avec colonnes pollen (noms Open-Meteo)
            lat: Latitude
            lon: Longitude
            
        Returns:
            True si succès
        """
        # Colonnes pollen attendues depuis Open-Meteo
        pollen_cols = ['alder_pollen', 'birch_pollen', 'grass_pollen', 'olive_pollen', 
                      'ragweed_pollen', 'mugwort_pollen']
        
        # Vérifier qu'au moins une colonne pollen existe
        available_pollen_cols = [col for col in pollen_cols if col in dataframe.columns]
        if not available_pollen_cols:
            logger.info("ℹ️ Aucune colonne pollen dans le DataFrame, skip insertion pollen")
            return True
        
        try:
            await self._ensure_connected()
            await self._ensure_address(lat, lon)
            
            # Préparer les timestamps
            df_timestamps = [pd.to_datetime(row['date']) for _, row in dataframe.iterrows()]
            min_ts = min(df_timestamps)
            max_ts = max(df_timestamps)
            
            # Récupérer timestamps existants
            existing_records = await self.db.pollenrecord.find_many(
                where={
                    'addressId': self.address_id,
                    'timestamp': {'gte': min_ts, 'lte': max_ts}
                }
            )
            existing_ts_set = {r.timestamp for r in existing_records}
            
            # Préparer nouveaux enregistrements
            new_records = []
            for _, row in dataframe.iterrows():
                timestamp = pd.to_datetime(row['date'])
                
                if timestamp in existing_ts_set:
                    continue  # Skip duplicates
                
                # Mapping Open-Meteo → noms botaniques DB
                # Note: On utilise les noms du schéma Prisma
                record = {
                    'timestamp': timestamp,
                    'addressId': self.address_id,
                    'alnus': self._safe_float(row.get('alder_pollen')),      # Alder = Aulne
                    'betula': self._safe_float(row.get('birch_pollen')),     # Birch = Bouleau
                    'graminaceae': self._safe_float(row.get('grass_pollen')), # Grass = Graminées
                    'artemisia': self._safe_float(row.get('mugwort_pollen')), # Mugwort = Armoise
                    'ambrosia': self._safe_float(row.get('ragweed_pollen')),  # Ragweed = Ambroisie
                    'dataSource': 'openmeteo'
                }
                
                # Olive pollen si disponible
                if 'olive_pollen' in row:
                    # Olive n'est pas dans le schéma actuel, on le stocke comme olive... à ajouter
                    pass
                
                new_records.append(record)
            
            # Batch insert
            inserted = 0
            if new_records:
                result = await self.db.pollenrecord.create_many(
                    data=new_records,
                    skip_duplicates=True
                )
                inserted = result
            
            logger.info(f"✅ Pollens: {inserted} nouveaux enregistrements (sur {len(dataframe)} lignes)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur insertion pollens: {e}")
            return False
    
    def _safe_float(self, value) -> Optional[float]:
        """Convertit une valeur en float, retourne None si NaN ou invalide"""
        import math
        if value is None:
            return None
        try:
            f = float(value)
            if math.isnan(f):
                return None
            return f
        except (ValueError, TypeError):
            return None

    async def get_date_range(self, address: str = None) -> Optional[Dict]:
        """
        Récupère l'intervalle de dates pour une adresse
        OPTIMISÉ: 1 seule requête agrégée au lieu de 3 requêtes séparées

        Returns:
            dict avec start_date et end_date ou None
        """
        await self._ensure_connected()

        if address is None:
            address = self.current_address

        normalized = AddressManager.sanitize_address(address)
        addr = await self.address_manager.find_address_by_normalized(normalized)

        if not addr:
            return None

        # OPTIMISATION: 1 seule requête agrégée au lieu de 3 requêtes
        result = await self.db.query_raw('''
            SELECT 
                MIN(timestamp) as start_date,
                MAX(timestamp) as end_date,
                COUNT(*) as total_records
            FROM air_quality_records 
            WHERE address_id = $1
        ''', addr.id)

        if not result or result[0]['total_records'] == 0:
            return None

        return {
            'start_date': result[0]['start_date'],
            'end_date': result[0]['end_date'],
            'total_records': result[0]['total_records']
        }


# ============================================================
# CLASSE : BASE DE DONNÉES MÉTÉO (PostgreSQL)
# ============================================================

class WeatherDB:
    """Base de données PostgreSQL pour la météo"""

    def __init__(self, address: str = None):
        """
        Initialise la base Weather avec Prisma

        Args:
            address: Adresse pour laquelle gérer les données
        """
        self.current_address = address or "Bruxelles"
        self.normalized_address = AddressManager.sanitize_address(self.current_address)
        self.db: Optional[Prisma] = None
        self.address_manager = AddressManager()
        self.address_id: Optional[int] = None

        logger.info(f"✅ WeatherDB (Prisma) initialisée: {self.current_address}")

    async def _ensure_connected(self):
        if not self.db:
            self.db = await DatabaseClient.get_client()

    async def _ensure_address(self, lat: float = 50.8503, lon: float = 4.3517):
        if not self.address_id:
            address = await self.address_manager.get_or_create_address(
                self.current_address, lat, lon
            )
            self.address_id = address.id

    async def insert_data(self, dataframe: pd.DataFrame, lat: float = 50.8503, lon: float = 4.3517, force_update: bool = False) -> bool:
        """Insère données météo dans PostgreSQL (optimisé batch)."""
        if dataframe is None or dataframe.empty:
            logger.error("❌ DataFrame météo vide")
            return False

        try:
            await self._ensure_connected()
            await self._ensure_address(lat, lon)

            # Préparer les timestamps du DataFrame
            df_timestamps = [pd.to_datetime(row['date']) for _, row in dataframe.iterrows()]
            min_ts = min(df_timestamps)
            max_ts = max(df_timestamps)

            # 1 seul SELECT: récupérer tous les timestamps existants pour cette plage
            existing_records = await self.db.weatherrecord.find_many(
                where={
                    'addressId': self.address_id,
                    'timestamp': {'gte': min_ts, 'lte': max_ts}
                }
            )
            existing_ts_set = {r.timestamp for r in existing_records}
            existing_by_ts = {r.timestamp: r for r in existing_records}

            logger.info(f"📊 Météo batch: {len(dataframe)} lignes, {len(existing_ts_set)} existantes")

            new_records = []
            updated = 0
            skipped = 0

            for _, row in dataframe.iterrows():
                timestamp = pd.to_datetime(row['date'])

                if timestamp in existing_ts_set:
                    if force_update:
                        existing = existing_by_ts[timestamp]
                        await self.db.weatherrecord.update(
                            where={'id': existing.id},
                            data={
                                'temperature': row.get('temperature'),
                                'feelsLike': row.get('feels_like'),
                                'humidity': row.get('humidity'),
                                'pressure': row.get('pressure'),
                                'windSpeed': row.get('wind_speed'),
                                'windDirection': row.get('wind_direction'),
                                'windGusts': row.get('wind_gusts'),
                                'cloudCover': row.get('cloud_cover'),
                                'precipitation1h': row.get('rain'),
                                'weatherCode': row.get('weather_code'),
                                'visibility': row.get('visibility'),
                                'dataSource': 'meteosource'
                            }
                        )
                        updated += 1
                    else:
                        skipped += 1
                    continue

                new_records.append({
                    'timestamp': timestamp,
                    'addressId': self.address_id,
                    'temperature': row.get('temperature'),
                    'feelsLike': row.get('feels_like'),
                    'humidity': row.get('humidity'),
                    'pressure': row.get('pressure'),
                    'windSpeed': row.get('wind_speed'),
                    'windDirection': row.get('wind_direction'),
                    'windGusts': row.get('wind_gusts'),
                    'cloudCover': row.get('cloud_cover'),
                    'precipitation1h': row.get('rain'),
                    'weatherCode': row.get('weather_code'),
                    'visibility': row.get('visibility'),
                    'dataSource': 'meteosource'
                })

            # Batch INSERT
            inserted = 0
            if new_records:
                result = await self.db.weatherrecord.create_many(
                    data=new_records,
                    skip_duplicates=True
                )
                inserted = result

            logger.info(f"✅ Météo: {inserted} nouveaux, {updated} mis à jour, {skipped} ignorés")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur insertion météo globale: {e}")
            return False

    async def save_hourly_weather(self, address: str, lat: float, lon: float, hourly_df: pd.DataFrame) -> bool:
        """
        Sauvegarde données météo horaires (historiques ou prévisions)
        Compatible avec download_weather.py

        Args:
            address: Adresse
            lat: Latitude
            lon: Longitude
            hourly_df: DataFrame avec colonnes: date, temperature, etc.

        Returns:
            True si succès
        """
        # Utiliser insert_data existant qui gère déjà les données horaires
        return await self.insert_data(hourly_df, lat, lon)

    async def save_current_weather(self, address: str, lat: float, lon: float, current_data: Dict) -> bool:
        """
        Sauvegarde météo actuelle

        Args:
            address: Adresse
            lat: Latitude
            lon: Longitude
            current_data: Dict avec température, vent, etc.

        Returns:
            True si succès
        """
        try:
            await self._ensure_connected()
            await self._ensure_address(lat, lon)

            timestamp = datetime.now()

            # Vérifier si existe déjà
            existing = await self.db.weatherrecord.find_first(
                where={
                    'addressId': self.address_id,
                    'timestamp': timestamp
                }
            )

            if existing:
                logger.info("Météo actuelle déjà présente")
                return True

            # Créer enregistrement
            await self.db.weatherrecord.create(
                data={
                    'timestamp': timestamp,
                    'addressId': self.address_id,
                    'temperature': current_data.get('temperature'),
                    'feelsLike': current_data.get('feels_like'),
                    'humidity': current_data.get('humidity'),
                    'pressure': current_data.get('pressure'),
                    'windSpeed': current_data.get('wind_speed'),
                    'windDirection': current_data.get('wind_direction'),
                    'windGusts': current_data.get('wind_gusts'),
                    'cloudCover': current_data.get('cloud_cover'),
                    'precipitation1h': current_data.get('rain'),
                    'weatherCode': current_data.get('weather_code'),
                    'visibility': current_data.get('visibility'),
                    'dataSource': 'open-meteo'
                }
            )

            logger.info("✅ Météo actuelle sauvegardée")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde météo actuelle: {e}")
            return False

    async def save_daily_weather(self, address: str, lat: float, lon: float, daily_df: pd.DataFrame) -> bool:
        """
        Sauvegarde prévisions journalières

        Args:
            address: Adresse
            lat: Latitude
            lon: Longitude
            daily_df: DataFrame avec prévisions journalières

        Returns:
            True si succès
        """
        # Pour les prévisions journalières, on peut les convertir en format horaire
        # en utilisant le midi de chaque jour, ou ignorer si pas nécessaire
        logger.info(f"Sauvegarde de {len(daily_df)} prévisions journalières (conversion en horaire)")
        return await self.insert_data(daily_df, lat, lon)

    async def get_latest_current_weather(self, address: str = None) -> Optional[Dict]:
        """Récupère la météo actuelle la plus récente"""
        await self._ensure_connected()

        if address is None:
            address = self.current_address

        normalized = AddressManager.sanitize_address(address)
        addr = await self.address_manager.find_address_by_normalized(normalized)

        if not addr:
            return None

        record = await self.db.weatherrecord.find_first(
            where={'addressId': addr.id},
            order={'timestamp': 'desc'}
        )

        if not record:
            return None

        return {
            'temperature': record.temperature,
            'feels_like': record.feelsLike,
            'humidity': record.humidity,
            'pressure': record.pressure,
            'wind_speed': record.windSpeed,
            'wind_direction': record.windDirection,
            'timestamp': record.timestamp
        }

    async def get_temperature_statistics(self, address: str = None) -> Dict:
        """
        Calcule statistiques de température
        OPTIMISÉ: Calcul côté base de données (AVG, MIN, MAX)
        """
        await self._ensure_connected()

        if address is None:
            address = self.current_address

        normalized = AddressManager.sanitize_address(address)
        addr = await self.address_manager.find_address_by_normalized(normalized)

        if not addr:
            return {}

        # OPTIMISATION: Calculs agrégés en SQL
        result = await self.db.query_raw('''
            SELECT 
                AVG(temperature) as avg_temp,
                MIN(temperature) as min_temp,
                MAX(temperature) as max_temp,
                COUNT(*) as total_records
            FROM weather_records 
            WHERE address_id = $1 AND temperature IS NOT NULL
        ''', addr.id)

        if not result or result[0]['total_records'] == 0:
            return {}
            
        row = result[0]

        return {
            'avg_temp': row['avg_temp'],
            'min_temp': row['min_temp'],
            'max_temp': row['max_temp'],
            'total_records': row['total_records']
        }

    async def get_hourly_forecast(self, address: str = None, hours: int = 24) -> pd.DataFrame:
        """Récupère prévisions horaires"""
        await self._ensure_connected()

        if address is None:
            address = self.current_address

        normalized = AddressManager.sanitize_address(address)
        addr = await self.address_manager.find_address_by_normalized(normalized)

        if not addr:
            return pd.DataFrame()

        records = await self.db.weatherrecord.find_many(
            where={'addressId': addr.id},
            order={'timestamp': 'desc'},
            take=hours
        )

        if not records:
            return pd.DataFrame()

        data = []
        for record in records:
            data.append({
                'date': record.timestamp,
                'address': addr.fullAddress,
                'temperature': record.temperature,
                'feels_like': record.feelsLike,
                'humidity': record.humidity,
                'pressure': record.pressure,
                'wind_speed': record.windSpeed,
                'wind_direction': record.windDirection,
                'wind_gusts': record.windGusts,
                'cloud_cover': record.cloudCover,
                'rain': record.precipitation1h,
                'weather_code': record.weatherCode,
                'visibility': record.visibility
            })

        df = pd.DataFrame(data)
        df = df.sort_values('date')
        return df


# ============================================================
# GESTIONNAIRE DE BASES (Compatible avec l'ancien code)
# ============================================================

class DatabaseManager:
    """Gestionnaire compatible avec l'ancien code SQLite"""

    @staticmethod
    def sanitize_address(address: str) -> str:
        """Wrapper pour compatibilité"""
        return AddressManager.sanitize_address(address)

    @staticmethod
    async def list_all_databases(db_type: str = 'air_quality') -> List[Dict]:
        """
        Liste toutes les adresses disponibles dans PostgreSQL
        OPTIMISÉ: Utilise 1 seule requête SQL avec JOIN au lieu de boucle N+1
        """
        db = await DatabaseClient.get_client()
        databases = []

        try:
            if db_type == 'air_quality':
                # Requête optimisée pour Air Quality
                # Récupère adresses + stats en 1 seule passe
                query = '''
                    SELECT 
                        a.id, a.normalized_address, a.updated_at,
                        COUNT(r.id) as count,
                        MIN(r.timestamp) as min_date,
                        MAX(r.timestamp) as max_date
                    FROM addresses a
                    LEFT JOIN air_quality_records r ON a.id = r.address_id
                    GROUP BY a.id
                    HAVING COUNT(r.id) > 0
                    ORDER BY a.created_at DESC
                '''
                results = await db.query_raw(query)
                
                for row in results:
                    databases.append({
                        'path': f'postgresql://{row["normalized_address"]}',
                        'type': 'air_quality',
                        'size': 0, # N/A PostgreSQL
                        'modified': row['updated_at'],
                        'address': row['normalized_address'],
                        'records': row['count'],
                        'date_range': f"{row['min_date'] or 'N/A'} → {row['max_date'] or 'N/A'}"
                    })
                    
            else:
                # Requête optimisée pour Weather
                query = '''
                    SELECT 
                        a.id, a.normalized_address, a.updated_at,
                        COUNT(r.id) as count,
                        MIN(r.timestamp) as min_date,
                        MAX(r.timestamp) as max_date
                    FROM addresses a
                    LEFT JOIN weather_records r ON a.id = r.address_id
                    GROUP BY a.id
                    HAVING COUNT(r.id) > 0
                    ORDER BY a.created_at DESC
                '''
                results = await db.query_raw(query)
                
                for row in results:
                    databases.append({
                        'path': f'postgresql://{row["normalized_address"]}',
                        'type': 'weather',
                        'size': 0,
                        'modified': row['updated_at'],
                        'address': row['normalized_address'],
                        'records': row['count'],
                        'date_range': f"{row['min_date'] or 'N/A'} → {row['max_date'] or 'N/A'}"
                    })

            return databases
            
        except Exception as e:
            # Fallback en cas d'erreur de requête (table manquante, etc)
            import logging
            logging.getLogger(__name__).error(f"❌ Erreur list_all_databases optimisé: {e}")
            return []


# ============================================================
# GESTIONNAIRE DE STATIONS
# ============================================================

class StationManager:
    """Gestion des stations de mesure avec support PostGIS"""

    def __init__(self):
        self.db: Optional[Prisma] = None

    async def _ensure_connected(self):
        """Assure la connexion à la base de données"""
        if not self.db:
            self.db = await DatabaseClient.get_client()

    async def get_all_stations(self, station_type: Optional[str] = None, active_only: bool = True) -> List[Dict]:
        """
        Récupère toutes les stations de mesure

        Args:
            station_type: Type de station ('air_quality', 'weather') ou None pour toutes
            active_only: Si True, ne retourne que les stations actives

        Returns:
            Liste de dictionnaires avec les informations des stations
        """
        await self._ensure_connected()

        where_clause = {}
        if station_type:
            where_clause['stationType'] = station_type
        if active_only:
            where_clause['isActive'] = True

        stations = await self.db.station.find_many(
            where=where_clause if where_clause else None,
            order={'stationName': 'asc'}
        )

        result = []
        for station in stations:
            # Récupérer le nombre de mesures pour cette station
            air_quality_count = await self.db.airqualityrecord.count(
                where={'stationId': station.id}
            )
            weather_count = await self.db.weatherrecord.count(
                where={'stationId': station.id}
            )

            # Récupérer la dernière mesure
            last_measurement = None
            if station.stationType == 'air_quality':
                last_record = await self.db.airqualityrecord.find_first(
                    where={'stationId': station.id},
                    order={'timestamp': 'desc'}
                )
                if last_record:
                    last_measurement = last_record.timestamp
            else:
                last_record = await self.db.weatherrecord.find_first(
                    where={'stationId': station.id},
                    order={'timestamp': 'desc'}
                )
                if last_record:
                    last_measurement = last_record.timestamp

            result.append({
                'id': station.id,
                'station_code': station.stationCode,
                'station_name': station.stationName,
                'station_type': station.stationType,
                'latitude': station.latitude,
                'longitude': station.longitude,
                'elevation': station.elevation,
                'metadata': station.metadata,
                'is_active': station.isActive,
                'air_quality_records': air_quality_count,
                'weather_records': weather_count,
                'last_measurement': last_measurement,
                'created_at': station.createdAt,
                'updated_at': station.updatedAt
            })

        return result

    async def get_stations_near_location(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        station_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Récupère les stations dans un rayon donné autour d'une position
        Utilise PostGIS pour le calcul de distance

        Args:
            latitude: Latitude du point central
            longitude: Longitude du point central
            radius_km: Rayon de recherche en kilomètres
            station_type: Type de station ou None pour toutes

        Returns:
            Liste de stations triées par distance
        """
        await self._ensure_connected()

        # Utiliser une requête SQL brute avec PostGIS pour calculer les distances
        # ST_Distance retourne la distance en degrés, conversion approximative: 1° ≈ 111 km
        radius_degrees = radius_km / 111.0

        where_parts = [f"ST_DWithin(geom, ST_SetSRID(ST_MakePoint({longitude}, {latitude}), 4326), {radius_degrees})"]

        if station_type:
            where_parts.append(f"station_type = '{station_type}'")

        where_clause = " AND ".join(where_parts)

        query = f"""
            SELECT
                id, station_code, station_name, station_type,
                latitude, longitude, elevation, metadata, is_active,
                created_at, updated_at,
                ST_Distance(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint({longitude}, {latitude}), 4326)::geography
                ) / 1000 as distance_km
            FROM stations
            WHERE {where_clause}
            ORDER BY distance_km ASC
        """

        stations = await self.db.query_raw(query)

        result = []
        for station in stations:
            # Récupérer le nombre de mesures
            air_quality_count = await self.db.airqualityrecord.count(
                where={'stationId': station['id']}
            )
            weather_count = await self.db.weatherrecord.count(
                where={'stationId': station['id']}
            )

            result.append({
                'id': station['id'],
                'station_code': station['station_code'],
                'station_name': station['station_name'],
                'station_type': station['station_type'],
                'latitude': station['latitude'],
                'longitude': station['longitude'],
                'elevation': station['elevation'],
                'metadata': station['metadata'],
                'is_active': station['is_active'],
                'distance_km': round(station['distance_km'], 2),
                'air_quality_records': air_quality_count,
                'weather_records': weather_count,
                'created_at': station['created_at'],
                'updated_at': station['updated_at']
            })

        return result

    async def get_station_by_code(self, station_code: str) -> Optional[Dict]:
        """
        Récupère une station par son code

        Args:
            station_code: Code unique de la station

        Returns:
            Dictionnaire avec les informations de la station ou None
        """
        await self._ensure_connected()

        station = await self.db.station.find_unique(
            where={'stationCode': station_code}
        )

        if not station:
            return None

        air_quality_count = await self.db.airqualityrecord.count(
            where={'stationId': station.id}
        )
        weather_count = await self.db.weatherrecord.count(
            where={'stationId': station.id}
        )

        return {
            'id': station.id,
            'station_code': station.stationCode,
            'station_name': station.stationName,
            'station_type': station.stationType,
            'latitude': station.latitude,
            'longitude': station.longitude,
            'elevation': station.elevation,
            'metadata': station.metadata,
            'is_active': station.isActive,
            'air_quality_records': air_quality_count,
            'weather_records': weather_count,
            'created_at': station.createdAt,
            'updated_at': station.updatedAt
        }

    async def create_station(
        self,
        station_code: str,
        station_name: str,
        station_type: str,
        latitude: float,
        longitude: float,
        elevation: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Crée une nouvelle station

        Args:
            station_code: Code unique de la station
            station_name: Nom de la station
            station_type: Type ('air_quality' ou 'weather')
            latitude: Latitude
            longitude: Longitude
            elevation: Altitude (optionnel)
            metadata: Métadonnées additionnelles (optionnel)

        Returns:
            Dictionnaire avec les informations de la station créée
        """
        await self._ensure_connected()

        # Créer le point PostGIS
        # ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        station = await self.db.station.create(
            data={
                'stationCode': station_code,
                'stationName': station_name,
                'stationType': station_type,
                'latitude': latitude,
                'longitude': longitude,
                'elevation': elevation,
                'metadata': metadata,
                'isActive': True
            }
        )

        # Mettre à jour la géométrie PostGIS avec une requête raw
        await self.db.execute_raw(
            f"""
            UPDATE stations
            SET geom = ST_SetSRID(ST_MakePoint({longitude}, {latitude}), 4326)
            WHERE id = {station.id}
            """
        )

        return {
            'id': station.id,
            'station_code': station.stationCode,
            'station_name': station.stationName,
            'station_type': station.stationType,
            'latitude': station.latitude,
            'longitude': station.longitude,
            'elevation': station.elevation,
            'metadata': station.metadata,
            'is_active': station.isActive
        }


# ============================================================
# EXPORT
# ============================================================

__all__ = [
    'DatabaseClient',
    'AddressManager',
    'AirQualityDB',
    'WeatherDB',
    'DatabaseManager',
    'StationManager'
]
