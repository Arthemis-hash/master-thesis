#!/usr/bin/env python3
"""
Configuration centralisée - APIs et téléchargement de données
Support API Brussels + Open-Meteo + Géocodage
"""

import os
import sqlite3
import pandas as pd
import warnings
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
from dotenv import load_dotenv

# Geopy pour géocodage
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# Streamlit pour UI
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

logger = logging.getLogger(__name__)

# ============================================================
# CHARGEMENT ENVIRONNEMENT
# ============================================================

env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"

load_dotenv(dotenv_path=env_path)

warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*coroutine.*')


# ============================================================
# CONFIGURATION GLOBALE
# ============================================================

# Dossier bases de données (via db_utils)
DB_FOLDER = Path(__file__).parent / "databases"
DB_FOLDER.mkdir(exist_ok=True)

# Cache API
CACHE_DIR = Path(__file__).parent / '.cache'
CACHE_DIR.mkdir(exist_ok=True)

# APIs externes
GEOCODING_API_KEY = os.getenv("GEOCODING_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GEOCODING_API_KEY")  # Alias
BRUSSELS_API_BASE = os.getenv("BRUSSELS_API_BASE", "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets")

# Limites et timeouts
DEFAULT_GEOCODING_TIMEOUT = 15
DEFAULT_API_TIMEOUT = 20
MAX_RETRIES = 3


# ============================================================
# CLASSE: GESTIONNAIRE CONFIGURATION
# ============================================================

class ConfigManager:
    """Gestionnaire centralisé configuration et validation"""
    
    @staticmethod
    def validate_environment() -> Dict[str, bool]:
        """
        Valide la présence des variables d'environnement critiques
        Retourne dict avec statut de chaque API
        """
        status = {
            'geocoding': GEOCODING_API_KEY is not None,
            'brussels_api': True,  # Pas besoin de clé
            'database_folder': DB_FOLDER.exists(),
            'cache_folder': CACHE_DIR.exists()
        }
        
        return status
    
    @staticmethod
    def get_missing_keys() -> list:
        """Liste des clés manquantes (non-critiques signalées)"""
        missing = []
        
        if not GEOCODING_API_KEY:
            missing.append("GEOCODING_API_KEY (géocodage Google)")
        
        return missing
    
    @staticmethod
    def display_env_status():
        """Affiche statut environnement dans Streamlit"""
        if not STREAMLIT_AVAILABLE:
            return
        
        status = ConfigManager.validate_environment()
        
        with st.expander("🔧 Statut Configuration"):
            for service, is_ok in status.items():
                icon = "✅" if is_ok else "❌"
                st.write(f"{icon} {service.replace('_', ' ').title()}")
            
            missing = ConfigManager.get_missing_keys()
            if missing:
                st.warning("⚠️ Clés API optionnelles manquantes:\n" + "\n".join(f"- {k}" for k in missing))


# ============================================================
# GÉOCODAGE
# ============================================================

def geocode_with_nominatim(address: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Géocodage avec Nominatim (OpenStreetMap) - Méthode principale
    Retourne (lat, lon, adresse_complète)
    """
    try:
        geolocator = Nominatim(
            user_agent="brussels_air_quality_v2.0",
            timeout=DEFAULT_GEOCODING_TIMEOUT
        )
        
        # Essai 1: Adresse exacte
        location = geolocator.geocode(address, exactly_one=True)
        
        if location:
            return location.latitude, location.longitude, location.address
        
        # Essai 2: Avec "Belgium"
        if "belgium" not in address.lower() and "belgique" not in address.lower():
            location = geolocator.geocode(f"{address}, Belgium", exactly_one=True)
            if location:
                return location.latitude, location.longitude, location.address
        
        # Essai 3: Avec "Brussels"
        if "brussels" not in address.lower() and "bruxelles" not in address.lower():
            location = geolocator.geocode(f"{address}, Brussels, Belgium", exactly_one=True)
            if location:
                return location.latitude, location.longitude, location.address
        
        return None, None, None
        
    except GeocoderTimedOut:
        logger.warning("⏱️ Nominatim timeout")
        return None, None, None
    except GeocoderServiceError as e:
        logger.warning(f"⚠️ Nominatim service error: {e}")
        return None, None, None
    except Exception as e:
        logger.error(f"❌ Erreur Nominatim: {e}")
        return None, None, None


def geocode_with_google(address: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Géocodage avec Google Maps API (fallback si clé disponible)
    """
    if not GEOCODING_API_KEY:
        return None, None, None
    
    import requests
    
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        'address': address,
        'key': GEOCODING_API_KEY,
        'region': 'be',  # Belgique
        'language': 'fr'
    }
    
    try:
        response = requests.get(url, params=params, timeout=DEFAULT_GEOCODING_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        if data['status'] == 'OK' and data['results']:
            result = data['results'][0]
            location = result['geometry']['location']
            formatted_address = result['formatted_address']
            
            return location['lat'], location['lng'], formatted_address
        
        return None, None, None
        
    except Exception as e:
        logger.error(f"❌ Erreur Google Geocoding: {e}")
        return None, None, None


def geocode_address(address: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Géocodage intelligent avec fallback automatique
    Retourne (latitude, longitude, adresse_complète)
    """
    if not address or len(address.strip()) < 2:
        if STREAMLIT_AVAILABLE:
            st.error("❌ Adresse trop courte")
        return None, None, None
    
    address = address.strip()
    
    # Méthode 1: Nominatim (gratuit, pas de clé)
    if STREAMLIT_AVAILABLE:
        with st.spinner("🔍 Géocodage avec Nominatim..."):
            lat, lon, full_address = geocode_with_nominatim(address)
    else:
        lat, lon, full_address = geocode_with_nominatim(address)
    
    if lat and lon:
        if STREAMLIT_AVAILABLE:
            st.success(f"✅ Trouvé: {full_address}")
        logger.info(f"✅ Géocodage réussi: {full_address}")
        return lat, lon, full_address
    
    # Méthode 2: Google Maps (si clé disponible)
    if GEOCODING_API_KEY:
        if STREAMLIT_AVAILABLE:
            with st.spinner("🔄 Tentative Google Maps..."):
                lat, lon, full_address = geocode_with_google(address)
        else:
            lat, lon, full_address = geocode_with_google(address)
        
        if lat and lon:
            if STREAMLIT_AVAILABLE:
                st.success(f"✅ Trouvé via Google: {full_address}")
            logger.info(f"✅ Géocodage Google réussi: {full_address}")
            return lat, lon, full_address
    
    # Échec total
    if STREAMLIT_AVAILABLE:
        st.error("❌ Adresse introuvable")
        st.info("""
        💡 **Suggestions:**
        - Utilisez le format complet: "Avenue Louise 500, 1050 Bruxelles"
        - Essayez juste le nom de quartier: "Ixelles"
        - Vérifiez l'orthographe
        """)
    
    logger.warning(f"❌ Géocodage échoué pour: {address}")
    return None, None, None


# ============================================================
# UTILITAIRES BASE DE DONNÉES
# ============================================================

def get_db_stats(db_path: str) -> Optional[Dict]:
    """Récupère statistiques d'une base de données"""
    if not Path(db_path).exists():
        return None
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Compter enregistrements
        cursor.execute("SELECT COUNT(*) FROM air_quality")
        total_records = cursor.fetchone()[0]
        
        # Plage de dates
        cursor.execute("SELECT MIN(date), MAX(date) FROM air_quality")
        start_date, end_date = cursor.fetchone()
        
        # Taille fichier
        file_size = Path(db_path).stat().st_size / (1024 * 1024)  # MB
        
        conn.close()
        
        return {
            'total_records': total_records,
            'start_date': start_date,
            'end_date': end_date,
            'file_size_mb': round(file_size, 2)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur lecture DB stats: {e}")
        return None


def list_available_databases() -> pd.DataFrame:
    """Liste toutes les bases disponibles dans databases/"""
    from db_utils import DatabaseManager
    
    dbs = DatabaseManager.list_all_databases('air_quality')
    
    if not dbs:
        return pd.DataFrame()
    
    return pd.DataFrame(dbs)


# ============================================================
# VALIDATION CONFIGURATION AU DÉMARRAGE
# ============================================================

def validate_config_on_startup():
    """Validation config au démarrage de l'application"""
    logger.info("🔧 Validation configuration...")
    
    status = ConfigManager.validate_environment()
    
    # Vérifications critiques
    if not status['database_folder']:
        logger.error("❌ Dossier databases/ manquant")
        DB_FOLDER.mkdir(exist_ok=True)
        logger.info("✅ Dossier databases/ créé")
    
    if not status['cache_folder']:
        CACHE_DIR.mkdir(exist_ok=True)
        logger.info("✅ Dossier cache/ créé")
    
    # Warnings non-critiques
    missing = ConfigManager.get_missing_keys()
    if missing:
        logger.warning(f"⚠️ Clés API manquantes (non-critique): {', '.join(missing)}")
    
    logger.info("✅ Configuration validée")
    
    return status


# Exécuter validation au chargement du module
if __name__ != "__main__":
    validate_config_on_startup()