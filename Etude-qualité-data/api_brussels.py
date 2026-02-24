#!/usr/bin/env python3
"""
Client API Open Data Brussels - Qualité de l'air
⚠️ API INDISPONIBLE: Les datasets Brussels Open Data ont été retirés
"""

import requests
import pandas as pd
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Union

logger = logging.getLogger(__name__)

BASE_URL = "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets"

# ⚠️ IMPORTANT: Les APIs publiques pour la qualité de l'air à Bruxelles ont changé
# Les datasets IRCELINE ne sont plus disponibles sur Brussels Open Data
#
# ALTERNATIVES RECOMMANDÉES:
# 1. OpenAQ API v3: https://openaq.org/ (Nécessite inscription gratuite pour clé API)
# 2. IRCELINE Direct: https://www.irceline.be/en/documentation/open-data
# 3. EEA Air Quality: https://www.eea.europa.eu/data-and-maps/data/aqereporting-8

POLLUTANT_DATASETS = {
    'no2': 'irceline_no2_hourly_average',
    'o3': 'irceline_o3_hourly_average',
    'pm10': 'irceline_pm10_hourly_average',
    'pm2_5': 'irceline_pm25_hourly_average'
}


class BrusselsAirQualityAPI:
    """Client API Open Data Brussels

    ⚠️ ATTENTION: L'API Brussels Open Data pour IRCELINE n'est plus disponible.
    Cette classe retournera des erreurs jusqu'à ce qu'une API alternative soit configurée.
    """

    def __init__(self, radius_meters: int = 3000):
        self.radius = radius_meters
        self.session = requests.Session()
        self.session.headers.update({'Accept': 'application/json'})
        logger.warning("⚠️ Brussels Open Data API pour qualité de l'air non disponible")
        logger.info("💡 Configurez une API alternative (OpenAQ, IRCELINE, etc.)")
        
    def fetch_pollutant(
        self,
        pollutant: str,
        lat: float,
        lon: float,
        start_date: Optional[Union[date, datetime]] = None,
        end_date: Optional[Union[date, datetime]] = None,
        limit: int = 100
    ) -> pd.DataFrame:
        """Récupère données polluant depuis Brussels Open Data (actuellement indisponible)

        Args:
            pollutant: Type de polluant (no2, o3, pm10, pm2_5)
            lat: Latitude
            lon: Longitude
            start_date: Date de début (optionnel, défaut: 7 derniers jours)
            end_date: Date de fin (optionnel, défaut: aujourd'hui)
            limit: Nombre max de résultats
        """

        if pollutant not in POLLUTANT_DATASETS:
            logger.error(f"❌ Polluant inconnu: {pollutant}")
            return pd.DataFrame()

        dataset_id = POLLUTANT_DATASETS[pollutant]
        url = f"{BASE_URL}/{dataset_id}/records"

        # Handle date range
        if start_date is None:
            start_date = datetime.now() - timedelta(days=7)
        if end_date is None:
            end_date = datetime.now()

        # Convert to datetime if date
        if isinstance(start_date, date) and not isinstance(start_date, datetime):
            start_date = datetime.combine(start_date, datetime.min.time())
        if isinstance(end_date, date) and not isinstance(end_date, datetime):
            end_date = datetime.combine(end_date, datetime.max.time())

        params = {
            'limit': limit,
            'timezone': 'UTC',
            'where': f"timestamp >= '{start_date.isoformat()}' AND timestamp <= '{end_date.isoformat()}'"
        }

        logger.info(f"🔍 Recherche {pollutant.upper()}: {start_date.date()} → {end_date.date()}")

        try:
            response = self.session.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()

            if 'results' not in data or not data['results']:
                logger.warning(f"⚠️ {pollutant.upper()}: Aucune donnée")
                return pd.DataFrame()

            # Parser et filtrer par distance
            records = []
            for result in data['results']:
                parsed = self._parse_record(result, pollutant)
                if not parsed:
                    continue

                if parsed['latitude'] and parsed['longitude']:
                    distance = self._haversine_distance(
                        lat, lon,
                        parsed['latitude'],
                        parsed['longitude']
                    )

                    if distance <= self.radius:
                        parsed['distance_m'] = round(distance, 2)
                        records.append(parsed)

            if not records:
                logger.warning(f"⚠️ {pollutant.upper()}: Aucun capteur dans {self.radius}m")
                return pd.DataFrame()

            df = pd.DataFrame(records)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('distance_m').head(limit)

            logger.info(f"✅ {pollutant.upper()}: {len(df)} mesures de {df['station_name'].nunique()} stations")
            return df

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ {pollutant.upper()}: HTTP {e.response.status_code}")
            logger.error(f"❌ L'API Brussels Open Data ne fournit plus les données IRCELINE")
            logger.info("💡 Visitez https://openaq.org/ pour obtenir une API alternative gratuite")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"❌ {pollutant.upper()}: {e}")
            return pd.DataFrame()
    
    def _parse_record(self, result: Dict, pollutant: str) -> Optional[Dict]:
        """Parse record avec gestion flexible des champs"""
        try:
            fields = result.get('fields', {})
            
            # Valeur (plusieurs noms possibles)
            value = (
                fields.get('value') or 
                fields.get('concentration') or
                fields.get('hourly_average')
            )
            
            if value is None or value == -9999 or value < 0:
                return None
            
            # Géolocalisation
            geo = fields.get('geo_point_2d') or fields.get('geopoint')
            if isinstance(geo, dict):
                lat = geo.get('lat')
                lon = geo.get('lon')
            elif isinstance(geo, list) and len(geo) == 2:
                lat, lon = geo
            else:
                # Essayer lat/lon directs
                lat = fields.get('latitude')
                lon = fields.get('longitude')
            
            # Timestamp
            timestamp = (
                fields.get('timestamp') or
                fields.get('datetime') or
                fields.get('date') or
                fields.get('from_datetime')
            )
            
            if not timestamp:
                return None
            
            return {
                'timestamp': timestamp,
                'pollutant': pollutant,
                'value': float(value),
                'unit': 'µg/m³',
                'station_name': fields.get('station_name') or fields.get('location') or 'Unknown',
                'station_code': fields.get('station_id') or fields.get('eoi_code') or 'N/A',
                'latitude': lat,
                'longitude': lon
            }
            
        except Exception as e:
            logger.debug(f"Erreur parse: {e}")
            return None
    
    def fetch_all_pollutants(
        self,
        lat: float,
        lon: float,
        start_date: Optional[Union[date, datetime]] = None,
        end_date: Optional[Union[date, datetime]] = None,
        limit_per_pollutant: int = 100
    ) -> Dict[str, pd.DataFrame]:
        """Récupère tous les polluants pour une période donnée

        Args:
            lat: Latitude
            lon: Longitude
            start_date: Date de début (optionnel)
            end_date: Date de fin (optionnel)
            limit_per_pollutant: Limite par polluant
        """

        results = {}

        for pollutant in POLLUTANT_DATASETS.keys():
            df = self.fetch_pollutant(
                pollutant, lat, lon,
                start_date=start_date,
                end_date=end_date,
                limit=limit_per_pollutant
            )
            if not df.empty:
                results[pollutant] = df

        if not results:
            logger.error("❌ AUCUN POLLUANT RÉCUPÉRÉ - Vérifier portail Open Data Brussels")
            logger.info("💡 Visitez: https://opendata.brussels.be/explore/?q=irceline")

        return results
    
    def get_nearest_station(self, lat: float, lon: float) -> Optional[Dict]:
        """Station la plus proche"""
        
        for pollutant in ['no2', 'pm10', 'pm2_5', 'o3']:
            df = self.fetch_pollutant(pollutant, lat, lon, limit=1)
            
            if not df.empty:
                station = df.iloc[0]
                return {
                    'name': station['station_name'],
                    'code': station['station_code'],
                    'latitude': station['latitude'],
                    'longitude': station['longitude'],
                    'distance_m': station.get('distance_m', 0)
                }
        
        logger.warning("⚠️ Aucune station trouvée")
        return None
    
    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Distance haversine en mètres"""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371000
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c