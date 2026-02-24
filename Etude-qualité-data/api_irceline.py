#!/usr/bin/env python3
"""
Client API IRCELINE pour qualité de l'air en Belgique
"""

import logging
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Union
from dataclasses import dataclass, asdict
from pathlib import Path

from utils import haversine_distance, safe_to_dict

logger = logging.getLogger(__name__)

BASE_URL = "https://geo.irceline.be/sos/api/v1"

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
    timestamp: datetime
    station_id: str
    station_name: str
    latitude: float
    longitude: float
    distance_km: Optional[float] = None
    pm10: Optional[float] = None
    pm2_5: Optional[float] = None
    no2: Optional[float] = None
    o3: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def is_valid(self) -> bool:
        return any([self.pm10, self.pm2_5, self.no2, self.o3])

class IrcelineAPI:
    def __init__(self, timeout: int = 30, metadata_file: str = "databases/stations_metadata.json"):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({'Accept': 'application/json'})
        self.metadata_file = Path(metadata_file)
        self.used_stations = []
        logger.info("✅ Client IRCELINE initialisé")
    
    def _record_station_usage(self, station_data: AirQualityData, pollutants_measured: List[str]):
        station_info = {
            'station_id': station_data.station_id,
            'station_name': station_data.station_name,
            'latitude': station_data.latitude,
            'longitude': station_data.longitude,
            'distance_km': station_data.distance_km,
            'pollutants_measured': pollutants_measured,
            'timestamp': station_data.timestamp.isoformat()
        }
        if not any(s['station_id'] == station_info['station_id'] for s in self.used_stations):
            self.used_stations.append(station_info)
    
    def save_stations_metadata(self, address: str = None, lat: float = None, lon: float = None):
        if not self.used_stations:
            logger.warning("⚠️  Aucune station à sauvegarder")
            return
        
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        
        existing_data = []
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception as e:
                logger.warning(f"⚠️  Erreur lecture: {e}")
        
        session_entry = {
            'session_timestamp': datetime.now().isoformat(),
            'location': {'address': address, 'latitude': lat, 'longitude': lon},
            'stations_used': self.used_stations,
            'total_stations': len(self.used_stations)
        }
        
        existing_data.append(session_entry)
        
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Métadonnées sauvegardées: {self.metadata_file}")
            logger.info(f"   📊 {len(self.used_stations)} station(s)")
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde: {e}")
    
    def get_air_quality(self, lat: float, lon: float, radius_km: float = 10.0, max_stations: int = 3) -> List[AirQualityData]:
        try:
            stations = self._get_stations()
            if not stations:
                return []
            
            nearby_stations = []
            for station in stations:
                coords = station.get('geometry', {}).get('coordinates', [])
                if len(coords) < 2:
                    continue
                
                station_lon, station_lat = coords[0], coords[1]
                distance_m = haversine_distance(lat, lon, station_lat, station_lon)
                distance_km_calc = distance_m / 1000.0
                
                if distance_km_calc <= radius_km:
                    nearby_stations.append({'station': station, 'distance_km': distance_km_calc})
            
            nearby_stations.sort(key=lambda x: x['distance_km'])
            nearby_stations = nearby_stations[:max_stations]
            
            if not nearby_stations:
                return []
            
            results = []
            for item in nearby_stations:
                station = item['station']
                data = self._get_station_data(station, item['distance_km'])
                if data and data.is_valid():
                    results.append(data)
                    
                    pollutants_measured = []
                    if data.pm10 is not None:
                        pollutants_measured.append('pm10')
                    if data.pm2_5 is not None:
                        pollutants_measured.append('pm2_5')
                    if data.no2 is not None:
                        pollutants_measured.append('no2')
                    if data.o3 is not None:
                        pollutants_measured.append('o3')
                    
                    self._record_station_usage(data, pollutants_measured)
            
            logger.info(f"✅ {len(results)} stations trouvées")
            return results
        except Exception as e:
            logger.error(f"❌ Erreur: {e}")
            return []
    
    def _get_stations(self) -> List[Dict]:
        try:
            url = f"{BASE_URL}/stations"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                logger.info(f"✅ {len(data)} stations disponibles")
                return data
            return []
        except Exception as e:
            logger.error(f"❌ Erreur stations: {e}")
            return []
    
    def _get_station_data(self, station: Dict, distance_km: float) -> Optional[AirQualityData]:
        try:
            props = station.get('properties', {})
            coords = station.get('geometry', {}).get('coordinates', [])
            
            if len(coords) < 2:
                return None
            
            station_id = str(props.get('id', ''))
            station_name = props.get('label', 'Unknown')
            lon, lat = coords[0], coords[1]
            
            data = AirQualityData(
                timestamp=datetime.now(),
                station_id=station_id,
                station_name=station_name,
                latitude=lat,
                longitude=lon,
                distance_km=round(distance_km, 2)
            )
            
            for pollutant, phenomenon_id in PHENOMENON_IDS.items():
                if pollutant not in ['pm10', 'pm2_5', 'no2', 'o3']:
                    continue
                try:
                    value = self._get_latest_value(station_id, phenomenon_id)
                    if value is not None and value >= 0:
                        setattr(data, pollutant, round(value, 2))
                except:
                    continue
            
            return data if data.is_valid() else None
        except:
            return None
    
    def _get_latest_value(self, station_id: str, phenomenon_id: str) -> Optional[float]:
        try:
            url = f"{BASE_URL}/timeseries"
            params = {'station': station_id, 'phenomenon': phenomenon_id, 'expanded': 'true'}
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                timeseries = data[0]
                last_value = timeseries.get('lastValue', {})
                value = last_value.get('value')
                return float(value) if value is not None else None
            return None
        except:
            return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("🧪 Test API IRCELINE")
    lat, lon = 50.8503, 4.3517
    client = IrcelineAPI()
    data = client.get_air_quality(lat, lon, radius_km=5.0, max_stations=1)
    if data:
        print(f"\n✅ {len(data)} stations")
        client.save_stations_metadata(address="Test", lat=lat, lon=lon)
    else:
        print("❌ Aucune donnée")
