#!/usr/bin/env python3
"""
Client API IRCELINE pour qualité de l'air en Belgique
Utilise l'API REST directe d'IRCELINE
Documentation: https://geo.irceline.be/sos/api/v1/
"""

import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Union
from dataclasses import dataclass, asdict

from utils import haversine_distance, safe_to_dict

logger = logging.getLogger(__name__)

# API IRCELINE SOS (Sensor Observation Service)
BASE_URL = "https://geo.irceline.be/sos/api/v1"

# Codes phénomènes IRCELINE
PHENOMENON_IDS = {
    'pm10': '5',
    'pm2_5': '6001',
    'no2': '8',
    'o3': '7',
    'so2': '1',
    'co': '391'
}


@dataclass
class AirQualityData:
    """Structure données qualité de l'air"""
    timestamp: datetime
    station_id: str
    station_name: str
    latitude: float
    longitude: float
    distance_km: Optional[float] = None
    
    # Polluants (µg/m³)
    pm10: Optional[float] = None
    pm2_5: Optional[float] = None
    no2: Optional[float] = None
    o3: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Conversion en dictionnaire"""
        return asdict(self)
    
    def is_valid(self) -> bool:
        """Vérifie si au moins un polluant est disponible"""
        return any([self.pm10, self.pm2_5, self.no2, self.o3])


class IrcelineAPI:
    """Client API IRCELINE avec support géographique"""
    
    def __init__(self, timeout: int = 30):
        """
        Args:
            timeout: Timeout requêtes HTTP (secondes)
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({'Accept': 'application/json'})
        
    def get_air_quality(
        self,
        lat: float,
        lon: float,
        radius_km: float = 10.0,
        max_stations: int = 3
    ) -> List[AirQualityData]:
        """
        Récupère qualité air pour coordonnées données
        
        Args:
            lat: Latitude
            lon: Longitude
            radius_km: Rayon recherche (km)
            max_stations: Nombre max de stations
            
        Returns:
            Liste de AirQualityData triée par distance
        """
        try:
            # Récupérer toutes les stations
            stations = self._get_stations()
            
            if not stations:
                logger.warning("Aucune station disponible")
                return []
            
            # Filtrer par distance
            nearby_stations = []
            for station in stations:
                station_lat = station.get('geometry', {}).get('coordinates', [None, None])[1]
                station_lon = station.get('geometry', {}).get('coordinates', [None, None])[0]
                
                if station_lat is None or station_lon is None:
                    continue
                
                distance = haversine_distance(lat, lon, station_lat, station_lon)
                
                if distance <= radius_km * 1000:  # Convertir km en m
                    nearby_stations.append({
                        'station': station,
                        'distance': distance
                    })
            
            # Trier par distance
            nearby_stations.sort(key=lambda x: x['distance'])
            nearby_stations = nearby_stations[:max_stations]
            
            if not nearby_stations:
                logger.warning(f"Aucune station dans {radius_km}km de ({lat}, {lon})")
                return []
            
            # Récupérer données pour chaque station
            results = []
            for item in nearby_stations:
                station = item['station']
                data = self._get_station_data(station, item['distance'] / 1000)
                if data and data.is_valid():
                    results.append(data)
            
            logger.info(f"✅ {len(results)} stations trouvées dans {radius_km}km")
            return results
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération données: {e}")
            return []
    
    def _get_stations(self) -> List[Dict]:
        """Récupère liste des stations IRCELINE"""
        try:
            url = f"{BASE_URL}/stations"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list):
                logger.info(f"✅ {len(data)} stations IRCELINE disponibles")
                return data
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération stations: {e}")
            return []
    
    def _get_station_data(self, station: Dict, distance_km: float) -> Optional[AirQualityData]:
        """Récupère données complètes d'une station"""
        try:
            props = station.get('properties', {})
            coords = station.get('geometry', {}).get('coordinates', [])
            
            if len(coords) < 2:
                return None
            
            station_id = str(props.get('id', ''))
            station_name = props.get('label', 'Unknown')
            lon, lat = coords[0], coords[1]
            
            # Créer objet données
            data = AirQualityData(
                timestamp=datetime.now(),
                station_id=station_id,
                station_name=station_name,
                latitude=lat,
                longitude=lon,
                distance_km=round(distance_km, 2)
            )
            
            # Récupérer chaque polluant
            for pollutant, phenomenon_id in PHENOMENON_IDS.items():
                if pollutant not in ['pm10', 'pm2_5', 'no2', 'o3']:
                    continue
                    
                try:
                    value = self._get_latest_value(station_id, phenomenon_id)
                    if value is not None and value >= 0:
                        setattr(data, pollutant, round(value, 2))
                except Exception as e:
                    logger.debug(f"Erreur {pollutant} station {station_id}: {e}")
                    continue
            
            return data if data.is_valid() else None
            
        except Exception as e:
            logger.debug(f"Erreur station: {e}")
            return None
    
    def _get_latest_value(self, station_id: str, phenomenon_id: str) -> Optional[float]:
        """Récupère dernière valeur pour un polluant"""
        try:
            url = f"{BASE_URL}/timeseries"
            params = {
                'station': station_id,
                'phenomenon': phenomenon_id,
                'expanded': 'true'
            }
            
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                timeseries = data[0]
                last_value = timeseries.get('lastValue', {})
                return last_value.get('value')
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur récupération valeur: {e}")
            return None
    
    def get_all_pollutants_historical(
        self,
        lat: float,
        lon: float,
        start_date: Union[datetime, str],
        end_date: Union[datetime, str],
        radius_km: float = 10.0
    ) -> Dict[str, pd.DataFrame]:
        """
        Récupère tous les polluants pour une période
        
        Returns:
            Dict {pollutant: DataFrame}
        """
        results = {}
        
        for pollutant in ['pm10', 'pm2_5', 'no2', 'o3']:
            df = self.get_historical_data(
                lat, lon, start_date, end_date, pollutant, radius_km
            )
            if not df.empty:
                results[pollutant] = df
        
        return results
    
    def get_historical_data(
        self,
        lat: float,
        lon: float,
        start_date: Union[datetime, str],
        end_date: Union[datetime, str],
        pollutant: str = 'pm2_5',
        radius_km: float = 10.0
    ) -> pd.DataFrame:
        """
        Récupère données historiques
        
        Args:
            lat, lon: Coordonnées
            start_date: Date début
            end_date: Date fin
            pollutant: Type polluant (pm10, pm2_5, no2, o3)
            radius_km: Rayon recherche
            
        Returns:
            DataFrame avec colonnes: timestamp, value, station_id, station_name
        """
        try:
            # Convertir dates
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date)
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date)
            
            # Trouver stations proches
            current_data = self.get_air_quality(lat, lon, radius_km, max_stations=1)
            if not current_data:
                logger.warning("Aucune station proche trouvée")
                return pd.DataFrame()
            
            station = current_data[0]
            phenomenon_id = PHENOMENON_IDS.get(pollutant)
            
            if not phenomenon_id:
                logger.error(f"Polluant invalide: {pollutant}")
                return pd.DataFrame()
            
            # Récupérer timeseries ID
            url = f"{BASE_URL}/timeseries"
            params = {
                'station': station.station_id,
                'phenomenon': phenomenon_id,
                'expanded': 'true'
            }
            
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            timeseries_data = response.json()
            
            if not isinstance(timeseries_data, list) or len(timeseries_data) == 0:
                logger.warning(f"Pas de timeseries pour {pollutant}")
                return pd.DataFrame()
            
            timeseries_id = timeseries_data[0].get('id')
            
            # Récupérer données historiques
            data_url = f"{BASE_URL}/timeseries/{timeseries_id}/getData"
            data_params = {
                'timespan': f"{start_date.isoformat()}/{end_date.isoformat()}"
            }
            
            data_response = self.session.get(data_url, params=data_params, timeout=self.timeout)
            data_response.raise_for_status()
            values = data_response.json()
            
            if not values or 'values' not in values:
                logger.warning(f"Pas de données historiques pour {pollutant}")
                return pd.DataFrame()
            
            # Parser données
            records = []
            for item in values['values']:
                try:
                    timestamp = datetime.fromtimestamp(item['timestamp'] / 1000)  # Convertir ms en s
                    value = item['value']
                    
                    if value is not None and value >= 0:
                        records.append({
                            'timestamp': timestamp,
                            'value': round(value, 2),
                            'pollutant': pollutant,
                            'unit': 'µg/m³',
                            'station_id': station.station_id,
                            'station_name': station.station_name,
                            'latitude': station.latitude,
                            'longitude': station.longitude
                        })
                except:
                    continue
            
            df = pd.DataFrame(records)
            if not df.empty:
                df = df.sort_values('timestamp')
                logger.info(f"✅ {len(df)} mesures {pollutant.upper()} récupérées")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Erreur données historiques: {e}")
            return pd.DataFrame()


# Fonction utilitaire pour compatibilité
def get_air_quality(lat: float, lon: float, radius_km: float = 10.0) -> List[Dict]:
    """Fonction simplifiée"""
    client = IrcelineAPI()
    results = client.get_air_quality(lat, lon, radius_km)
    return [data.to_dict() for data in results]


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 Test API IRCELINE")
    print("=" * 50)
    
    # Bruxelles centre
    lat, lon = 50.8503, 4.3517
    
    client = IrcelineAPI()
    data = client.get_air_quality(lat, lon, radius_km=10.0, max_stations=2)
    
    if data:
        for station_data in data:
            print(f"\n📍 {station_data.station_name}")
            print(f"   Distance: {station_data.distance_km}km")
            print(f"   PM2.5: {station_data.pm2_5} µg/m³")
            print(f"   PM10: {station_data.pm10} µg/m³")
            print(f"   NO2: {station_data.no2} µg/m³")
            print(f"   O3: {station_data.o3} µg/m³")
    else:
        print("❌ Aucune donnée disponible")
