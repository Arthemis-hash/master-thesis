#!/usr/bin/env python3
"""
Client API Open-Meteo pour données météorologiques
Supporte données actuelles ET historiques (gratuit)
"""

import requests
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OpenMeteoClient:
    """Client pour télécharger données météo Open-Meteo (gratuit)"""
    
    def __init__(self):
        """Initialise le client Open-Meteo (pas de clé API nécessaire)"""
        self.base_url_forecast = "https://api.open-meteo.com/v1/forecast"
        self.base_url_archive = "https://archive-api.open-meteo.com/v1/archive"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AirQualityWeatherApp/1.0'
        })
        logger.info("✅ Client Open-Meteo initialisé (gratuit, pas de clé requise)")
    
    def _make_request(self, url: str, params: Dict) -> Optional[Dict]:
        """
        Effectue une requête HTTP avec gestion d'erreurs
        
        Args:
            url: URL complète
            params: Paramètres de requête
            
        Returns:
            Réponse JSON ou None si erreur
        """
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            logger.debug(f"Requête réussie: {url}")
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ Erreur HTTP {response.status_code}: {e}")
            return None
            
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout de la requête API")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erreur requête: {e}")
            return None
    
    def get_current_weather(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Récupère météo actuelle
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Données météo actuelles formatées
        """
        params = {
            'latitude': lat,
            'longitude': lon,
            'current': [
                'temperature_2m', 'relative_humidity_2m', 'apparent_temperature',
                'precipitation', 'rain', 'snowfall', 'weather_code',
                'cloud_cover', 'pressure_msl', 'surface_pressure',
                'wind_speed_10m', 'wind_direction_10m', 'wind_gusts_10m'
            ],
            'timezone': 'auto'
        }
        
        # Convertir liste en string séparée par virgules
        params['current'] = ','.join(params['current'])
        
        data = self._make_request(self.base_url_forecast, params)
        
        if not data or 'current' not in data:
            logger.error("❌ Données météo actuelles non disponibles")
            return None
        
        current = data['current']
        
        return {
            'timestamp': datetime.fromisoformat(current['time']),
            'temperature': current.get('temperature_2m'),
            'feels_like': current.get('apparent_temperature'),
            'humidity': current.get('relative_humidity_2m'),
            'pressure': current.get('pressure_msl'),
            'wind_speed': current.get('wind_speed_10m'),
            'wind_gusts': current.get('wind_gusts_10m'),
            'wind_angle': current.get('wind_direction_10m'),
            'precipitation_total': current.get('precipitation'),
            'rain': current.get('rain'),
            'snowfall': current.get('snowfall'),
            'cloud_cover': current.get('cloud_cover'),
            'weather_code': current.get('weather_code')
        }
    
    def get_hourly_forecast(self, lat: float, lon: float, days: int = 7) -> Optional[pd.DataFrame]:
        """
        Récupère prévisions horaires (toutes les 3 heures)
        
        Args:
            lat: Latitude
            lon: Longitude
            days: Nombre de jours de prévision (max 16)
            
        Returns:
            DataFrame avec prévisions toutes les 3 heures
        """
        days = min(days, 16)
        
        params = {
            'latitude': lat,
            'longitude': lon,
            'hourly': [
                'temperature_2m', 'relative_humidity_2m', 'apparent_temperature',
                'precipitation', 'rain', 'snowfall', 'weather_code',
                'pressure_msl', 'surface_pressure', 'cloud_cover',
                'wind_speed_10m', 'wind_direction_10m', 'wind_gusts_10m'
            ],
            'forecast_days': days,
            'timezone': 'auto'
        }
        
        params['hourly'] = ','.join(params['hourly'])
        
        data = self._make_request(self.base_url_forecast, params)
        
        if not data or 'hourly' not in data:
            logger.error("❌ Prévisions horaires non disponibles")
            return None
        
        hourly = data['hourly']
        
        df = pd.DataFrame({
            'date': pd.to_datetime(hourly['time']),
            'temperature': hourly.get('temperature_2m'),
            'feels_like': hourly.get('apparent_temperature'),
            'humidity': hourly.get('relative_humidity_2m'),
            'pressure': hourly.get('pressure_msl'),
            'wind_speed': hourly.get('wind_speed_10m'),
            'wind_direction': hourly.get('wind_direction_10m'),
            'wind_gusts': hourly.get('wind_gusts_10m'),
            'precipitation_total': hourly.get('precipitation'),
            'rain': hourly.get('rain'),
            'snowfall': hourly.get('snowfall'),
            'cloud_cover': hourly.get('cloud_cover'),
            'weather_code': hourly.get('weather_code')
        })
        
        # Filtrer pour garder seulement les données toutes les 3 heures
        df = df[df['date'].dt.hour % 3 == 0].reset_index(drop=True)
        
        logger.info(f"✅ {len(df)} prévisions (toutes les 3h) récupérées")
        
        return df
    
    def get_historical_weather(self, lat: float, lon: float, 
                              start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """
        Récupère données météo historiques (toutes les 3 heures, depuis 1940)
        
        Args:
            lat: Latitude
            lon: Longitude
            start_date: Date de début
            end_date: Date de fin
            
        Returns:
            DataFrame avec données toutes les 3 heures
        """
        # Valider les dates
        if end_date < start_date:
            logger.error("❌ Date de fin antérieure à date de début")
            return None
        
        # Open-Meteo Archive supporte depuis 1940
        if start_date.year < 1940:
            logger.warning("⚠️ Données avant 1940 non disponibles, ajustement à 1940")
            start_date = datetime(1940, 1, 1)
        
        # Pas de données futures dans l'archive
        max_date = datetime.now() - timedelta(days=5)
        if end_date > max_date:
            logger.warning(f"⚠️ Date de fin ajustée à {max_date.strftime('%Y-%m-%d')}")
            end_date = max_date
        
        params = {
            'latitude': lat,
            'longitude': lon,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'hourly': [
                'temperature_2m', 'relative_humidity_2m', 'apparent_temperature',
                'precipitation', 'rain', 'snowfall', 'weather_code',
                'pressure_msl', 'surface_pressure', 'cloud_cover',
                'wind_speed_10m', 'wind_direction_10m', 'wind_gusts_10m'
            ],
            'timezone': 'auto'
        }
        
        params['hourly'] = ','.join(params['hourly'])
        
        logger.info(f"📥 Téléchargement historique: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}")
        
        data = self._make_request(self.base_url_archive, params)
        
        if not data or 'hourly' not in data:
            logger.error("❌ Données historiques non disponibles")
            return None
        
        hourly = data['hourly']
        
        df = pd.DataFrame({
            'date': pd.to_datetime(hourly['time']),
            'temperature': hourly.get('temperature_2m'),
            'feels_like': hourly.get('apparent_temperature'),
            'humidity': hourly.get('relative_humidity_2m'),
            'pressure': hourly.get('pressure_msl'),
            'wind_speed': hourly.get('wind_speed_10m'),
            'wind_direction': hourly.get('wind_direction_10m'),
            'wind_gusts': hourly.get('wind_gusts_10m'),
            'precipitation_total': hourly.get('precipitation'),
            'rain': hourly.get('rain'),
            'snowfall': hourly.get('snowfall'),
            'cloud_cover': hourly.get('cloud_cover'),
            'weather_code': hourly.get('weather_code')
        })
        
        # Filtrer pour garder seulement les données toutes les 3 heures
        df = df[df['date'].dt.hour % 3 == 0].reset_index(drop=True)
        
        logger.info(f"✅ {len(df)} enregistrements historiques (toutes les 3h) récupérés")
        
        return df
    
    def get_daily_forecast(self, lat: float, lon: float, days: int = 7) -> Optional[pd.DataFrame]:
        """
        Récupère prévisions journalières
        
        Args:
            lat: Latitude
            lon: Longitude
            days: Nombre de jours (max 16)
            
        Returns:
            DataFrame avec prévisions journalières
        """
        days = min(days, 16)
        
        params = {
            'latitude': lat,
            'longitude': lon,
            'daily': [
                'weather_code', 'temperature_2m_max', 'temperature_2m_min',
                'apparent_temperature_max', 'apparent_temperature_min',
                'precipitation_sum', 'rain_sum', 'snowfall_sum',
                'precipitation_hours', 'wind_speed_10m_max', 'wind_gusts_10m_max',
                'wind_direction_10m_dominant', 'sunrise', 'sunset'
            ],
            'forecast_days': days,
            'timezone': 'auto'
        }
        
        params['daily'] = ','.join(params['daily'])
        
        data = self._make_request(self.base_url_forecast, params)
        
        if not data or 'daily' not in data:
            logger.error("❌ Prévisions journalières non disponibles")
            return None
        
        daily = data['daily']
        
        df = pd.DataFrame({
            'day': pd.to_datetime(daily['time']),
            'weather_code': daily.get('weather_code'),
            'temperature_min': daily.get('temperature_2m_min'),
            'temperature_max': daily.get('temperature_2m_max'),
            'feels_like_min': daily.get('apparent_temperature_min'),
            'feels_like_max': daily.get('apparent_temperature_max'),
            'precipitation_sum': daily.get('precipitation_sum'),
            'rain_sum': daily.get('rain_sum'),
            'snowfall_sum': daily.get('snowfall_sum'),
            'wind_speed_max': daily.get('wind_speed_10m_max'),
            'wind_gusts_max': daily.get('wind_gusts_10m_max'),
            'wind_direction': daily.get('wind_direction_10m_dominant'),
            'sunrise': pd.to_datetime(daily.get('sunrise')),
            'sunset': pd.to_datetime(daily.get('sunset'))
        })
        
        logger.info(f"✅ {len(df)} prévisions journalières récupérées")
        
        return df