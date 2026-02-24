#!/usr/bin/env python3
"""
============================================================
CONFIGURATION - API ET TÉLÉCHARGEMENT DE DONNÉES
============================================================
Configuration et fonctions de téléchargement pour l'application Streamlit
"""

# ============================================================
# IMPORTS
# ============================================================
import sqlite3
import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import streamlit as st
import os
import requests
import warnings
from dotenv import load_dotenv
from pathlib import Path

# ============================================================
# CONFIGURATION ENVIRONNEMENT
# ============================================================

# Charger variables d'environnement
env_path = Path(__file__).parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Ignorer warnings de cache asyncio
warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*coroutine.*')

# ============================================================
# CONFIGURATION GLOBALE
# ============================================================

# Chemin base de données par défaut (dans databases/)
DB_PATH = str(Path(__file__).parent / 'databases' / 'bruxelles_air_quality.db')
CACHE_DIR = '.cache'

# Clés API depuis variables d'environnement
GEOCODING_API_KEY = os.getenv("GEOCODING_API_KEY")
STREET_VIEW_API_KEY = os.getenv("STREET_VIEW_API_KEY")
MAP_STATIC_API_KEY = os.getenv("MAP_STATIC_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GEOCODING_API_KEY")


# ============================================================
# CLIENT OPEN-METEO
# ============================================================

@st.cache_resource
def get_openmeteo_client():
    """Initialise le client Open-Meteo avec cache et retry"""
    cache_session = requests_cache.CachedSession(CACHE_DIR, expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    return openmeteo_requests.Client(session=retry_session)


# ============================================================
# FONCTIONS DE GÉOCODAGE
# ============================================================

def geocode_with_nominatim(address):
    """Géocodage avec Nominatim (OpenStreetMap) - Méthode principale - MONDIAL"""
    try:
        geolocator = Nominatim(user_agent="air_quality_streamlit_v1.0", timeout=15)
        
        # Recherche mondiale sans restriction géographique
        location = geolocator.geocode(address, exactly_one=True)
        
        if location:
            return location.latitude, location.longitude, location.address
        
        return None, None, None
        
    except GeocoderTimedOut:
        st.warning("⏱️ Nominatim : timeout, passage à la méthode suivante...")
        return None, None, None
    except GeocoderServiceError as e:
        st.warning(f"⚠️ Nominatim temporairement indisponible : {e}")
        return None, None, None
    except Exception as e:
        st.warning(f"⚠️ Erreur Nominatim : {e}")
        return None, None, None

def geocode_with_openmeteo(address):
    """Géocodage avec Open-Meteo API - Solution de secours robuste"""
    geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
    
    # Essayer avec plusieurs paramètres
    search_params = [
        {"name": address, "count": 10, "language": "fr", "format": "json"},
        {"name": address, "count": 10, "language": "en", "format": "json"},
        {"name": f"{address} Belgium", "count": 10, "language": "fr", "format": "json"},
    ]
    
    for params in search_params:
        try:
            resp = requests.get(geocode_url, params=params, timeout=15).json()
            
            if "results" in resp and len(resp["results"]) > 0:
                results = resp["results"]
                
                # Afficher les résultats pour que l'utilisateur choisisse
                st.info(f"🔍 {len(results)} résultat(s) trouvé(s) pour '{address}'")
                
                # Retourner tous les résultats pour sélection
                return results
        
        except Exception as e:
            continue
    
    return None

def geocode_address(address):
    """
    Géocodage intelligent avec fallback automatique et choix utilisateur
    Retourne: (latitude, longitude, adresse_complète) OU (None, None, None) si échec
    """
    if not address or len(address.strip()) < 2:
        st.error("❌ Adresse trop courte")
        return None, None, None
    
    # Nettoyer l'adresse
    address = address.strip()
    
    # Méthode 1 : Nominatim (OpenStreetMap)
    with st.spinner("🔍 Recherche avec Nominatim (OpenStreetMap)..."):
        lat, lon, full_address = geocode_with_nominatim(address)
        
        if lat and lon:
            st.success(f"✅ Trouvé via Nominatim : {full_address}")
            return lat, lon, full_address
    
    # Méthode 2 : Open-Meteo (fallback avec choix)
    with st.spinner("🔄 Tentative avec Open-Meteo Geocoding API..."):
        results = geocode_with_openmeteo(address)
        
        if results and isinstance(results, list):
            # Stocker les résultats dans session state pour sélection
            st.session_state.geocode_results = results
            return "MULTIPLE_RESULTS", None, None
    
    # Si tout échoue
    st.error("❌ Aucun résultat trouvé")
    st.info("💡 Suggestions :")
    st.markdown("""
    - Essayez avec le nom de la ville seul (ex: "Bruxelles")
    - Ajoutez le pays (ex: "Ixelles, Belgium")
    - Soyez plus précis (ex: "Avenue Louise, 1050 Bruxelles")
    - Utilisez la saisie manuelle ci-dessous
    """)
    
    return None, None, None


# ============================================================
# TÉLÉCHARGEMENT DES DONNÉES AIR QUALITY
# ============================================================

def download_air_quality_data(latitude, longitude, address, start_date, end_date):
    """
    Télécharge les données de qualité de l'air avec TOUTES les variables
    Version complète avec pollens, UV, etc.
    Utilise le nouveau système de bases multi-adresses
    """
    try:
        from db_async_wrapper import AirQualityDB
        
        client = get_openmeteo_client()
        
        # URL et paramètres API (version complète)
        url = "https://air-quality-api.open-meteo.com/v1/air-quality"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": [
                "pm10", "pm2_5", "carbon_monoxide", "carbon_dioxide", 
                "nitrogen_dioxide", "uv_index", "uv_index_clear_sky", 
                "alder_pollen", "birch_pollen", "ozone", "sulphur_dioxide", 
                "methane", "ammonia", "dust", "aerosol_optical_depth", 
                "ragweed_pollen", "olive_pollen", "mugwort_pollen", "grass_pollen"
            ],
            "domains": "cams_europe",
            "timeformat": "unixtime",
            "start_date": start_date,
            "end_date": end_date,
        }
        
        # Requête API
        responses = client.weather_api(url, params=params)
        response = responses[0]
        
        # Traitement des données horaires
        hourly = response.Hourly()
        
        hourly_data = {
            "date": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left"
            ),
            "pm10": hourly.Variables(0).ValuesAsNumpy(),
            "pm2_5": hourly.Variables(1).ValuesAsNumpy(),
            "carbon_monoxide": hourly.Variables(2).ValuesAsNumpy(),
            "carbon_dioxide": hourly.Variables(3).ValuesAsNumpy(),
            "nitrogen_dioxide": hourly.Variables(4).ValuesAsNumpy(),
            "uv_index": hourly.Variables(5).ValuesAsNumpy(),
            "uv_index_clear_sky": hourly.Variables(6).ValuesAsNumpy(),
            "alder_pollen": hourly.Variables(7).ValuesAsNumpy(),
            "birch_pollen": hourly.Variables(8).ValuesAsNumpy(),
            "ozone": hourly.Variables(9).ValuesAsNumpy(),
            "sulphur_dioxide": hourly.Variables(10).ValuesAsNumpy(),
            "methane": hourly.Variables(11).ValuesAsNumpy(),
            "ammonia": hourly.Variables(12).ValuesAsNumpy(),
            "dust": hourly.Variables(13).ValuesAsNumpy(),
            "aerosol_optical_depth": hourly.Variables(14).ValuesAsNumpy(),
            "ragweed_pollen": hourly.Variables(15).ValuesAsNumpy(),
            "olive_pollen": hourly.Variables(16).ValuesAsNumpy(),
            "mugwort_pollen": hourly.Variables(17).ValuesAsNumpy(),
            "grass_pollen": hourly.Variables(18).ValuesAsNumpy(),
        }
        
        df = pd.DataFrame(data=hourly_data)
        df['latitude'] = latitude
        df['longitude'] = longitude
        df['address'] = address
        
        # Filtrer pour garder seulement les données toutes les 4 heures
        df = df[df['date'].dt.hour % 4 == 0].reset_index(drop=True)
        
        # Informations de réponse
        info = {
            'latitude': response.Latitude(),
            'longitude': response.Longitude(),
            'elevation': response.Elevation(),
            'records': len(df),
            'db_path': None  # Sera rempli après sauvegarde
        }
        
        # Utiliser le nouveau système de base multi-adresses
        db = AirQualityDB(address=address, force_new=False)
        force_update = st.session_state.get('force_refresh', False)
        if db.insert_data(df, lat=latitude, lon=longitude, force_update=force_update):
            info['db_path'] = db.db_path
            st.success(f"✅ Données air quality sauvegardées")
            
            # Sauvegarder les pollens dans la table dédiée
            if db.insert_pollen_data(df, lat=latitude, lon=longitude):
                st.success(f"✅ Données pollens sauvegardées")
            
            # Reset force_refresh flag après utilisation
            if force_update:
                st.session_state.force_refresh = False
                logger.info("🔄 Mode force_refresh désactivé après mise à jour")
        
        return True, info
        
    except Exception as e:
        st.error(f"❌ Erreur lors du téléchargement : {e}")
        return False, None


# ============================================================
# UTILITAIRES BASE DE DONNÉES
# ============================================================

def get_sample_data():
    """Récupère un échantillon de données pour vérification"""
    try:
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT date, address, latitude, longitude, 
                   pm10, pm2_5, nitrogen_dioxide, ozone
            FROM air_quality 
            ORDER BY date DESC 
            LIMIT 10
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.warning(f"Impossible de lire les données : {e}")
        return pd.DataFrame()

def get_last_address():
    """Récupère la dernière adresse stockée dans la base"""
    try:
        if not Path(DB_PATH).exists():
            return None

        conn = sqlite3.connect(DB_PATH)
        query = "SELECT DISTINCT address FROM air_quality ORDER BY created_at DESC LIMIT 1"
        result = pd.read_sql_query(query, conn)
        conn.close()

        if not result.empty:
            return result['address'].iloc[0]
        return None
    except Exception as e:
        return None

def init_database():
    """
    Initialise la base de données si elle n'existe pas
    Note: Avec le nouveau système (db_utils.py), les bases sont créées automatiquement
    """
    return True