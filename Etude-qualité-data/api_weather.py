#!/usr/bin/env python3
"""
Client API Météo IRM/KMI Belgique
⚠️ API INDISPONIBLE: L'endpoint JSON public a changé
"""

import requests
import pandas as pd
import logging
from datetime import datetime, timezone, date, timedelta
from typing import Optional, Dict, List, Union

logger = logging.getLogger(__name__)

# ⚠️ IMPORTANT: L'API IRM publique a changé et ne retourne plus de JSON directement
#
# ALTERNATIVES RECOMMANDÉES:
# 1. Open-Meteo API (gratuite, pas d'inscription): https://open-meteo.com/
#    Exemple: https://api.open-meteo.com/v1/forecast?latitude=50.85&longitude=4.35&current=temperature_2m
# 2. OpenWeatherMap API (gratuite jusqu'à 1000 calls/jour): https://openweathermap.org/api
# 3. VisualCrossing Weather API: https://www.visualcrossing.com/

API_URL = "https://opendata.meteo.be/synoptic/current_synoptic_observations.json"

# Stations principales Bruxelles
BRUSSELS_STATIONS = {
    '06447': 'Uccle',
    '06450': 'Brussels National Airport (Zaventem)',
    '06451': 'Brussels South (Charleroi)'
}

DEFAULT_STATION = '06447'  # Uccle - référence climatologique


class IRMWeatherAPI:
    """Client API météo IRM avec support multi-stations

    ⚠️ ATTENTION: L'API IRM publique a changé et ne retourne plus de JSON.
    Cette classe retournera des erreurs jusqu'à ce qu'une API alternative soit configurée.
    """

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        logger.warning("⚠️ API IRM JSON non disponible")
        logger.info("💡 Utilisez Open-Meteo (gratuit) ou OpenWeatherMap pour données météo")

    def fetch_all_observations(self) -> Optional[List[Dict]]:
        """
        Récupère toutes les observations météo Belgique
        ⚠️ Actuellement non fonctionnel - API retourne HTML au lieu de JSON
        """
        try:
            response = self.session.get(API_URL, timeout=self.timeout)
            response.raise_for_status()

            # Vérifier si réponse est vide
            if not response.content:
                logger.error("❌ Réponse API météo vide")
                return None

            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"❌ L'API IRM ne retourne plus de JSON (retourne HTML)")
                logger.error(f"❌ L'endpoint a probablement changé ou nécessite un web scraping")
                logger.info("💡 Utilisez une API alternative (Open-Meteo, OpenWeatherMap)")
                return None

            if 'observations' not in data:
                logger.error(f"❌ Format JSON invalide: {list(data.keys())}")
                return None

            logger.info(f"✅ {len(data['observations'])} stations météo disponibles")
            return data['observations']

        except requests.exceptions.Timeout:
            logger.error("❌ Timeout connexion IRM (>15s)")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erreur connexion IRM: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erreur inattendue IRM: {e}")
            return None

    def fetch_station(self, station_code: str = DEFAULT_STATION) -> Optional[Dict]:
        """
        Récupère données d'une station spécifique
        """
        observations = self.fetch_all_observations()

        if not observations:
            return None

        for station in observations:
            if station.get('station_code') == station_code:
                return self._parse_station_data(station)

        logger.warning(f"⚠️ Station {station_code} introuvable")
        return None

    def fetch_brussels_stations(self) -> List[Dict]:
        """
        Récupère données des stations Bruxelles
        """
        observations = self.fetch_all_observations()

        if not observations:
            return []

        results = []
        for station in observations:
            station_code = station.get('station_code')
            if station_code in BRUSSELS_STATIONS:
                parsed = self._parse_station_data(station)
                if parsed:
                    results.append(parsed)

        logger.info(f"✅ {len(results)} stations Bruxelles")
        return results

    def fetch_nearest_station(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Trouve station météo la plus proche de coordonnées données (données actuelles)
        ⚠️ Actuellement non fonctionnel - API IRM a changé
        """
        observations = self.fetch_all_observations()

        if not observations:
            logger.error("❌ API IRM non disponible - l'endpoint JSON a changé")
            logger.info("💡 ALTERNATIVES:")
            logger.info("   - Open-Meteo (gratuit): https://open-meteo.com/")
            logger.info("   - OpenWeatherMap: https://openweathermap.org/api")
            return None

        nearest = None
        min_distance = float('inf')

        for station in observations:
            if 'latitude' not in station or 'longitude' not in station:
                continue

            distance = self._haversine_distance(
                lat, lon,
                station['latitude'],
                station['longitude']
            )

            if distance < min_distance:
                min_distance = distance
                nearest = station

        if nearest:
            parsed = self._parse_station_data(nearest)
            parsed['distance_km'] = round(min_distance / 1000, 2)
            logger.info(f"✅ Station la plus proche: {parsed['station_name']} ({parsed['distance_km']}km)")
            return parsed

        return None

    def fetch_historical_data(
        self,
        lat: float,
        lon: float,
        start_date: Optional[Union[date, datetime]] = None,
        end_date: Optional[Union[date, datetime]] = None
    ) -> Optional[Union[Dict, List[Dict]]]:
        """
        Récupère données météo historiques pour une période donnée
        ⚠️ Actuellement non fonctionnel - API IRM a changé

        Args:
            lat: Latitude
            lon: Longitude
            start_date: Date de début (optionnel, défaut: 7 derniers jours)
            end_date: Date de fin (optionnel, défaut: aujourd'hui)

        Returns:
            Liste de dictionnaires (données historiques) ou Dict unique (données actuelles)
        """

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

        logger.info(f"🔍 Recherche météo: {start_date.date()} → {end_date.date()}")

        # Pour l'instant, l'API IRM ne retourne que les données actuelles
        # Une API alternative (Open-Meteo) devrait être utilisée pour les données historiques
        logger.error("❌ API IRM ne supporte pas les données historiques")
        logger.info("💡 Pour données historiques, utilisez:")
        logger.info("   - Open-Meteo API: https://api.open-meteo.com/v1/forecast")
        logger.info("   - OpenWeatherMap History: https://openweathermap.org/api/one-call-3")

        # Fallback: retourner les données actuelles uniquement
        current = self.fetch_nearest_station(lat, lon)
        if current:
            logger.warning("⚠️ Retour données actuelles uniquement (pas d'historique)")
            return current

        return None

    def _parse_station_data(self, station: Dict) -> Dict:
        """
        Parse et normalise données station
        """
        timestamp_utc = datetime.fromtimestamp(
            station.get('timestamp_utc', 0),
            timezone.utc
        )

        return {
            'station_code': station.get('station_code'),
            'station_name': station.get('station_name'),
            'latitude': station.get('latitude'),
            'longitude': station.get('longitude'),
            'timestamp': timestamp_utc,
            'temperature': station.get('air_temperature'),
            'feels_like': station.get('feels_like_temperature'),
            'humidity': station.get('humidity_relative'),
            'pressure': station.get('pressure_station_level'),
            'wind_speed': station.get('wind_speed_10m'),
            'wind_direction': station.get('wind_direction_10m'),
            'wind_direction_text': station.get('wind_direction_10m_txt'),
            'wind_gusts': station.get('wind_gust_speed_10m'),
            'cloud_cover': station.get('total_cloud_cover'),
            'visibility': station.get('visibility'),
            'weather_code': station.get('weather_code'),
            'precipitation_1h': station.get('precipitation_1h'),
            'sunshine_1h': station.get('sunshine_duration_1h')
        }

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

    def get_dataframe(self, observations: List[Dict]) -> pd.DataFrame:
        """
        Convertit observations en DataFrame
        """
        if not observations:
            return pd.DataFrame()

        df = pd.DataFrame(observations)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        return df


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def get_weather_summary(weather_data: Dict) -> str:
    """
    Génère résumé textuel météo
    """
    if not weather_data:
        return "Données météo indisponibles"

    temp = weather_data.get('temperature')
    humidity = weather_data.get('humidity')
    wind = weather_data.get('wind_speed')
    wind_dir = weather_data.get('wind_direction_text', 'N/A')

    summary = f"{temp}°C (ressenti {weather_data.get('feels_like')}°C)"

    if humidity:
        summary += f", humidité {humidity}%"

    if wind:
        summary += f", vent {wind_dir} {wind} km/h"

    return summary


def get_weather_icon(weather_code: Optional[int]) -> str:
    """
    Emoji selon code météo WMO
    """
    if not weather_code:
        return "🌡️"

    weather_icons = {
        0: "☀️",      # Ciel clair
        1: "🌤️",     # Peu nuageux
        2: "⛅",     # Partiellement nuageux
        3: "☁️",     # Couvert
        45: "🌫️",   # Brouillard
        48: "🌫️",   # Brouillard givrant
        51: "🌦️",   # Bruine légère
        61: "🌧️",   # Pluie légère
        71: "🌨️",   # Neige légère
        80: "🌦️",   # Averses
        95: "⛈️",   # Orage
    }

    return weather_icons.get(weather_code, "🌡️")