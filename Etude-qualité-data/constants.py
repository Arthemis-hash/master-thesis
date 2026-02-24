#!/usr/bin/env python3
"""
Constantes et configurations globales
Centralisation pour faciliter maintenance et modification
"""

# ============================================================
# API ENDPOINTS
# ============================================================

# IRCELINE - Qualité de l'air
IRCELINE_BASE_URL = "https://geo.irceline.be/sos/api/v1"

# IRM - Météo
IRM_WFS_URL = "https://opendata.meteo.be/service/wfs"

# ============================================================
# PHÉNOMÈNES IRCELINE
# ============================================================

POLLUTANT_CODES = {
    'pm10': '5',
    'pm2_5': '6001',
    'no2': '8',
    'o3': '7',
    'so2': '1',
    'co': '391'
}

POLLUTANT_NAMES = {
    'pm10': 'PM10',
    'pm2_5': 'PM2.5',
    'no2': 'NO₂',
    'o3': 'O₃',
    'so2': 'SO₂',
    'co': 'CO'
}

POLLUTANT_UNITS = {
    'pm10': 'µg/m³',
    'pm2_5': 'µg/m³',
    'no2': 'µg/m³',
    'o3': 'µg/m³',
    'so2': 'µg/m³',
    'co': 'mg/m³'
}

# ============================================================
# STATIONS MÉTÉO IRM
# ============================================================

WEATHER_STATIONS = {
    '06447': {'name': 'Uccle', 'lat': 50.7998, 'lon': 4.3588},
    '06450': {'name': 'Brussels Airport (Zaventem)', 'lat': 50.9014, 'lon': 4.4844},
    '06451': {'name': 'Charleroi Airport', 'lat': 50.4592, 'lon': 4.4538},
    '06477': {'name': 'Beauvechain', 'lat': 50.7586, 'lon': 4.7683},
    '06458': {'name': 'Chièvres', 'lat': 50.5758, 'lon': 3.8308}
}

# ============================================================
# SEUILS DE QUALITÉ AIR (µg/m³)
# ============================================================

AIR_QUALITY_THRESHOLDS = {
    'pm2_5': {
        'excellent': 12,
        'good': 35,
        'moderate': 55,
        'poor': 150,
        'dangerous': 250
    },
    'pm10': {
        'excellent': 20,
        'good': 50,
        'moderate': 100,
        'poor': 200,
        'dangerous': 300
    },
    'no2': {
        'excellent': 40,
        'good': 90,
        'moderate': 120,
        'poor': 230,
        'dangerous': 340
    },
    'o3': {
        'excellent': 60,
        'good': 120,
        'moderate': 180,
        'poor': 240,
        'dangerous': 300
    }
}

# ============================================================
# COULEURS QUALITÉ AIR
# ============================================================

AQI_COLORS = {
    'excellent': '#00E400',    # Vert
    'good': '#FFFF00',          # Jaune
    'moderate': '#FF7E00',      # Orange
    'poor': '#FF0000',          # Rouge
    'dangerous': '#99004C',     # Marron foncé
    'hazardous': '#7E0023'      # Marron très foncé
}

# ============================================================
# TIMEOUTS & LIMITES
# ============================================================

DEFAULT_TIMEOUT = 20  # secondes
DEFAULT_RADIUS_KM = 5.0
DEFAULT_MAX_STATIONS = 3
DEFAULT_HISTORICAL_DAYS = 7

# ============================================================
# BASE DE DONNÉES
# ============================================================

DB_FOLDER_NAME = "databases"
DEFAULT_DB_NAME = "air_quality.db"

# ============================================================
# PARAMÈTRES UI
# ============================================================

RADIUS_MIN = 100      # mètres
RADIUS_MAX = 1000     # mètres (1km max)
RADIUS_DEFAULT = 500  # mètres
RADIUS_STEP = 100     # mètres

HISTORY_DAYS_MIN = 1
HISTORY_DAYS_MAX = 30
HISTORY_DAYS_DEFAULT = 7

# ============================================================
# MESSAGES
# ============================================================

NO_DATA_MESSAGE = "Aucune donnée disponible"
API_ERROR_MESSAGE = "Erreur de connexion à l'API"
LOADING_MESSAGE = "Chargement des données..."

# ============================================================
# FORMAT DATES
# ============================================================

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DISPLAY_DATE_FORMAT = "%d/%m/%Y"
DISPLAY_DATETIME_FORMAT = "%d/%m/%Y %H:%M"
