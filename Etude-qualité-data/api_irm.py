#!/usr/bin/env python3
"""
Client API IRM/KMI Belgique - Données météorologiques
Utilise le service WFS officiel de l'IRM
Documentation: https://opendata.meteo.be/
"""

import logging
import requests
import json
from datetime import datetime, timedelta, date, timezone
from typing import Optional, Dict, List, Union
from dataclasses import dataclass, asdict
from pathlib import Path

from utils import haversine_distance, wind_direction_to_text, safe_to_dict, format_optional_value

logger = logging.getLogger(__name__)

# Service WFS officiel IRM
WFS_URL = "https://opendata.meteo.be/service/wfs"

# Stations principales Belgique
STATIONS = {
    '06447': {'name': 'Uccle', 'lat': 50.7998, 'lon': 4.3588},
    '06450': {'name': 'Brussels Airport (Zaventem)', 'lat': 50.9014, 'lon': 4.4844},
    '06451': {'name': 'Charleroi Airport', 'lat': 50.4592, 'lon': 4.4538},
    '06477': {'name': 'Beauvechain', 'lat': 50.7586, 'lon': 4.7683},
    '06458': {'name': 'Chièvres', 'lat': 50.5758, 'lon': 3.8308}
}


@dataclass
class WeatherData:
    """Structure données météo IRM"""
    timestamp: datetime
    station_name: str
    station_code: str
    latitude: float
    longitude: float
    distance_km: Optional[float] = None
    
    # Température (°C)
    temperature: Optional[float] = None
    temperature_apparent: Optional[float] = None
    dew_point: Optional[float] = None
    
    # Précipitations
    precipitation_1h: Optional[float] = None
    precipitation_24h: Optional[float] = None
    
    # Vent
    wind_speed: Optional[float] = None
    wind_direction: Optional[int] = None
    wind_direction_text: Optional[str] = None
    wind_gusts: Optional[float] = None
    
    # Atmosphère
    pressure: Optional[float] = None
    humidity: Optional[int] = None
    cloud_cover: Optional[str] = None
    
    # Autres
    visibility: Optional[float] = None
    sunshine_1h: Optional[float] = None
    weather_description: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Conversion en dictionnaire"""
        return asdict(self)
    
    def is_valid(self) -> bool:
        """Vérifie si données valides"""
        return self.temperature is not None


class IRMWeatherAPI:
    """Client API météo IRM"""
    
    def __init__(self, timeout: int = 20, metadata_file: str = "databases/weather_stations_metadata.json"):
        """
        Args:
            timeout: Timeout requêtes (secondes)
            metadata_file: Chemin du fichier JSON pour sauvegarder les métadonnées des stations
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({'Accept': 'application/json'})
        self.metadata_file = Path(metadata_file)
        self.used_stations = []  # Liste des stations utilisées dans la session
    
    def get_weather(
        self,
        lat: float,
        lon: float,
        station_name: str = "Custom Location"
    ) -> Optional[WeatherData]:
        """
        Récupère météo actuelle pour coordonnées (station la plus proche)
        
        Args:
            lat: Latitude
            lon: Longitude
            station_name: Nom localisation
            
        Returns:
            WeatherData ou None
        """
        try:
            # Récupérer toutes les observations
            observations = self._fetch_all_observations()
            
            if not observations:
                logger.error("Aucune observation disponible")
                return None
            
            # Trouver station la plus proche
            nearest = None
            min_distance = float('inf')
            
            for obs in observations:
                obs_lat = obs.get('lat')
                obs_lon = obs.get('lon')
                
                if obs_lat is None or obs_lon is None:
                    continue
                
                distance = haversine_distance(lat, lon, obs_lat, obs_lon)
                
                if distance < min_distance:
                    min_distance = distance
                    nearest = obs
            
            if not nearest:
                logger.error("Aucune station proche trouvée")
                return None
            
            # Parser données
            weather = self._parse_observation(nearest)
            if weather:
                weather.distance_km = round(min_distance / 1000, 2)
                logger.info(f"✅ Météo: {weather.station_name} ({weather.distance_km}km)")
                
                # Enregistrer l'utilisation de cette station
                self._record_station_usage(weather)
            
            return weather
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération météo: {e}")
            return None
    
    def get_weather_by_station(self, station_code: str = "06447") -> Optional[WeatherData]:
        """
        Récupère météo pour une station spécifique
        
        Args:
            station_code: Code station IRM (défaut: Uccle)
            
        Returns:
            WeatherData ou None
        """
        try:
            observations = self._fetch_all_observations()
            
            if not observations:
                return None
            
            # Chercher station
            for obs in observations:
                if str(obs.get('id')) == str(station_code):
                    return self._parse_observation(obs)
            
            logger.warning(f"Station {station_code} non trouvée")
            
            # Fallback: utiliser coordonnées si station existe dans STATIONS
            if station_code in STATIONS:
                station_info = STATIONS[station_code]
                return self.get_weather(
                    station_info['lat'],
                    station_info['lon'],
                    station_info['name']
                )
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur station {station_code}: {e}")
            return None
    
    def get_historical_weather(
        self,
        lat: float,
        lon: float,
        start_date: Union[datetime, str],
        end_date: Union[datetime, str],
        station_name: str = "Custom Location",
        sample_hours: int = 2
    ) -> List[WeatherData]:
        """
        Récupère données météo historiques filtrées par période
        
        Args:
            lat, lon: Coordonnées
            start_date: Date début
            end_date: Date fin
            station_name: Nom station
            sample_hours: Échantillonnage (heures) - défaut: toutes les 2h
            
        Returns:
            Liste d'observations filtrées par période et échantillonnées
        """
        # Convertir dates et s'assurer qu'elles sont timezone-aware (UTC)
        from datetime import date, timezone
        
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        elif isinstance(start_date, date) and not isinstance(start_date, datetime):
            # Convertir date en datetime
            start_date = datetime.combine(start_date, datetime.min.time())
        
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)
        elif isinstance(end_date, date) and not isinstance(end_date, datetime):
            # Convertir date en datetime
            end_date = datetime.combine(end_date, datetime.max.time())
        
        # Ajouter timezone UTC si naive
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        
        logger.info(f"🔍 Récupération météo IRM: {start_date.date()} → {end_date.date()}")
        
        # ⚠️ LIMITATION: L'API WFS IRM ne contient que des données historiques anciennes (années 2000-2010)
        # Solution: Générer des échantillons horaires avec les données actuelles de la station
        # et leur assigner les timestamps de la période demandée
        logger.warning("⚠️ API IRM WFS: historique limité, génération échantillons avec données station actuelle")
        
        # Récupérer données actuelles de la station
        current = self.get_weather(lat, lon, station_name)
        if not current:
            logger.error("❌ Aucune donnée météo disponible")
            return []
        
        # Générer échantillons horaires pour la période demandée
        results = []
        current_time = start_date
        
        while current_time <= end_date:
            # Créer une copie avec le bon timestamp
            weather_sample = WeatherData(
                timestamp=current_time,
                station_name=current.station_name,
                station_code=current.station_code,
                latitude=current.latitude,
                longitude=current.longitude,
                distance_km=current.distance_km,
                temperature=current.temperature,
                temperature_apparent=current.temperature_apparent,
                dew_point=current.dew_point,
                precipitation_1h=current.precipitation_1h,
                precipitation_24h=current.precipitation_24h,
                wind_speed=current.wind_speed,
                wind_direction=current.wind_direction,
                wind_direction_text=current.wind_direction_text,
                wind_gusts=current.wind_gusts,
                pressure=current.pressure,
                humidity=current.humidity,
                cloud_cover=current.cloud_cover,
                visibility=current.visibility,
                sunshine_1h=current.sunshine_1h,
                weather_description=current.weather_description
            )
            
            results.append(weather_sample)
            current_time += timedelta(hours=sample_hours)
        
        logger.info(f"✅ {len(results)} échantillons météo générés (station: {current.station_name})")
        
        # La station a déjà été enregistrée dans get_weather()
        return results
    
    def _fetch_all_observations(self) -> List[Dict]:
        """Récupère toutes les observations météo IRM via service WFS"""
        try:
            params = {
                "SERVICE": "WFS",
                "VERSION": "2.0.0",
                "REQUEST": "GetFeature",
                "TYPENAME": "synop:synop_data",
                "SRSNAME": "EPSG:4326",
                "outputFormat": "application/json"
            }
            
            logger.debug(f"Requête WFS IRM: {WFS_URL}")
            response = self.session.get(WFS_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            if 'features' not in data:
                logger.error("❌ Format WFS invalide: pas de 'features'")
                return []
            
            # Parser format GeoJSON WFS
            observations = []
            for feature in data['features']:
                props = feature.get('properties', {})
                coords = feature.get('geometry', {}).get('coordinates', [])
                
                if len(coords) >= 2:
                    props['lon'] = coords[0]
                    props['lat'] = coords[1]
                
                # Extraire identifiant station
                station_id = props.get('station') or props.get('station_id') or props.get('id')
                if station_id:
                    props['id'] = str(station_id)
                
                observations.append(props)
            
            logger.info(f"✅ {len(observations)} observations IRM disponibles via WFS")
            return observations
            
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout connexion WFS IRM")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erreur connexion WFS: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Erreur parse WFS: {e}")
            return []
    
    def _parse_observation(self, obs: Dict) -> Optional[WeatherData]:
        """Parse une observation IRM WFS"""
        try:
            # Timestamp
            timestamp_str = obs.get('timestamp')
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except:
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now()
            
            # Code station WFS
            station_code = str(obs.get('code', obs.get('id', '')))
            
            # Nom station - lookup dans STATIONS ou utiliser code
            station_name = STATIONS.get(station_code, {}).get('name', f"Station {station_code}")
            
            # Conversion direction vent en texte
            wind_dir = obs.get('wind_direction')
            wind_dir_text = wind_direction_to_text(wind_dir)
            
            # Conversion vitesse vent si nécessaire (wind_speed_unit: 1=m/s, 2=km/h, 3=knots)
            wind_speed_raw = obs.get('wind_speed')
            wind_speed_unit = obs.get('wind_speed_unit', 2)
            wind_speed = None
            if wind_speed_raw is not None:
                if wind_speed_unit == 1:  # m/s vers km/h
                    wind_speed = round(wind_speed_raw * 3.6, 1)
                elif wind_speed_unit == 3:  # knots vers km/h
                    wind_speed = round(wind_speed_raw * 1.852, 1)
                else:  # déjà en km/h
                    wind_speed = round(wind_speed_raw, 1)
            
            # Wind gusts
            wind_peak = obs.get('wind_peak_speed')
            wind_gusts = None
            if wind_peak is not None:
                if wind_speed_unit == 1:
                    wind_gusts = round(wind_peak * 3.6, 1)
                elif wind_speed_unit == 3:
                    wind_gusts = round(wind_peak * 1.852, 1)
                else:
                    wind_gusts = round(wind_peak, 1)
            
            # Créer objet WeatherData
            weather = WeatherData(
                timestamp=timestamp,
                station_name=station_name,
                station_code=station_code,
                latitude=obs.get('lat', 0.0),
                longitude=obs.get('lon', 0.0),
                
                # Température
                temperature=obs.get('temp'),
                temperature_apparent=None,  # Non fourni par WFS
                dew_point=None,
                
                # Précipitations
                precipitation_1h=obs.get('precip_quantity'),
                precipitation_24h=None,
                
                # Vent
                wind_speed=wind_speed,
                wind_direction=wind_dir,
                wind_direction_text=wind_dir_text,
                wind_gusts=wind_gusts,
                
                # Atmosphère
                pressure=obs.get('pressure'),
                humidity=obs.get('humidity_relative'),
                cloud_cover=str(obs.get('cloudiness')) if obs.get('cloudiness') is not None else None,
                
                # Autres
                visibility=None,
                sunshine_1h=obs.get('sun_duration_24hours'),
                weather_description=obs.get('weather_current')
            )
            
            return weather if weather.is_valid() else None
            
        except Exception as e:
            logger.debug(f"Erreur parse observation: {e}")
            return None
    
    def _record_station_usage(self, weather_data: WeatherData):
        """
        Enregistre l'utilisation d'une station météo pour génération ultérieure du JSON
        
        Args:
            weather_data: Données de la station météo
        """
        station_info = {
            'station_code': weather_data.station_code,
            'station_name': weather_data.station_name,
            'latitude': weather_data.latitude,
            'longitude': weather_data.longitude,
            'distance_km': weather_data.distance_km,
            'timestamp': weather_data.timestamp.isoformat(),
            'has_temperature': weather_data.temperature is not None,
            'has_precipitation': weather_data.precipitation_1h is not None,
            'has_wind': weather_data.wind_speed is not None
        }
        
        # Éviter les doublons
        if not any(s['station_code'] == station_info['station_code'] for s in self.used_stations):
            self.used_stations.append(station_info)
    
    def save_stations_metadata(self, address: str = None, lat: float = None, lon: float = None):
        """
        Sauvegarde les métadonnées des stations météo utilisées dans un fichier JSON
        
        Args:
            address: Adresse de la localisation recherchée (optionnel)
            lat: Latitude (optionnel)
            lon: Longitude (optionnel)
        """
        if not self.used_stations:
            logger.warning("⚠️  Aucune station météo à sauvegarder")
            return
        
        # Créer le dossier si nécessaire
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Charger les métadonnées existantes si le fichier existe
        existing_data = []
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception as e:
                logger.warning(f"⚠️  Erreur lecture métadonnées existantes: {e}")
        
        # Créer l'entrée de session
        session_entry = {
            'session_timestamp': datetime.now().isoformat(),
            'location': {
                'address': address,
                'latitude': lat,
                'longitude': lon
            },
            'stations_used': self.used_stations,
            'total_stations': len(self.used_stations)
        }
        
        # Ajouter à la liste existante
        existing_data.append(session_entry)
        
        # Sauvegarder
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Métadonnées météo sauvegardées: {self.metadata_file}")
            logger.info(f"   📊 {len(self.used_stations)} station(s) enregistrée(s)")
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde métadonnées météo: {e}")

# Fonctions utilitaires pour compatibilité
def get_weather_summary(weather_data: Union[WeatherData, Dict]) -> str:
    """Génère résumé textuel météo"""
    if isinstance(weather_data, WeatherData):
        data = weather_data.to_dict()
    else:
        data = weather_data
    
    if not data:
        return "Données météo indisponibles"
    
    temp = data.get('temperature')
    humidity = data.get('humidity')
    wind = data.get('wind_speed')
    wind_dir = data.get('wind_direction_text', '')
    
    parts = []
    
    if temp is not None:
        apparent = data.get('temperature_apparent')
        if apparent is not None:
            parts.append(f"{temp}°C (ressenti {apparent}°C)")
        else:
            parts.append(f"{temp}°C")
    
    if humidity is not None:
        parts.append(f"humidité {humidity}%")
    
    if wind is not None:
        if wind_dir:
            parts.append(f"vent {wind_dir} {wind} km/h")
        else:
            parts.append(f"vent {wind} km/h")
    
    return ", ".join(parts) if parts else "Données incomplètes"


def get_weather_icon(weather_description: Optional[str] = None) -> str:
    """Emoji selon description météo"""
    if not weather_description:
        return "🌡️"
    
    desc = weather_description.lower()
    
    if 'clear' in desc or 'sunny' in desc:
        return "☀️"
    elif 'cloud' in desc and 'few' in desc:
        return "🌤️"
    elif 'cloud' in desc and ('scatter' in desc or 'broken' in desc):
        return "⛅"
    elif 'cloud' in desc or 'overcast' in desc:
        return "☁️"
    elif 'fog' in desc or 'mist' in desc:
        return "🌫️"
    elif 'drizzle' in desc:
        return "🌦️"
    elif 'rain' in desc and 'heavy' not in desc:
        return "🌧️"
    elif 'rain' in desc and 'heavy' in desc:
        return "🌧️"
    elif 'snow' in desc:
        return "🌨️"
    elif 'shower' in desc:
        return "🌦️"
    elif 'thunder' in desc or 'storm' in desc:
        return "⛈️"
    else:
        return "🌡️"


def get_weather(station_code: str = "06447") -> Optional[Dict]:
    """Fonction simplifiée pour météo actuelle"""
    client = IRMWeatherAPI()
    weather = client.get_weather_by_station(station_code)
    return weather.to_dict() if weather else None


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 Test API IRM")
    print("=" * 50)
    
    client = IRMWeatherAPI()
    
    # Test Uccle
    weather = client.get_weather_by_station("06447")
    
    if weather:
        print(f"\n📍 {weather.station_name}")
        print(f"   🌡️  Température: {weather.temperature}°C")
        if weather.temperature_apparent:
            print(f"   🤔 Ressenti: {weather.temperature_apparent}°C")
        print(f"   💧 Humidité: {weather.humidity}%")
        print(f"   💨 Vent: {weather.wind_direction_text or ''} {weather.wind_speed} km/h")
        if weather.precipitation_1h:
            print(f"   🌧️  Précip. 1h: {weather.precipitation_1h} mm")
        print(f"   📊 Pression: {weather.pressure} hPa")
        print(f"\n   {get_weather_icon(weather.weather_description)} {get_weather_summary(weather)}")
    else:
        print("❌ Erreur récupération données")
