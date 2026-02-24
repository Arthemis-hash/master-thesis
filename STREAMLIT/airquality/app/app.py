#!/usr/bin/env python3
"""
============================================================
APPLICATION STREAMLIT - QUALITÉ DE L'AIR GÉOLOCALISÉE
============================================================
Analyse de la qualité de l'air et de la météo pour des
localisations spécifiques avec visualisations interactives.
"""

# ============================================================
# IMPORTS - BIBLIOTHÈQUES STANDARDS
# ============================================================
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
import importlib.util
import threading
import time

# ============================================================
# IMPORTS - BIBLIOTHÈQUES TIERCES
# ============================================================
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# ============================================================
# CONFIGURATION DES CHEMINS ET ENVIRONNEMENT
# ============================================================

# Charger variables d'environnement
env_path = Path(__file__).parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Charger le config.py LOCAL (pas celui de Image-Analysis)
_config_path = Path(__file__).parent / "config.py"
_spec = importlib.util.spec_from_file_location("app_config", _config_path)
_config_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_config_module)

# ============================================================
# IMPORTS - FONCTIONS CONFIG
# ============================================================
download_air_quality_data = _config_module.download_air_quality_data
geocode_address = _config_module.geocode_address
get_sample_data = _config_module.get_sample_data
get_last_address = _config_module.get_last_address
DB_PATH = _config_module.DB_PATH

# ============================================================
# IMPORTS - MODULES LOCAUX
# ============================================================
# IMPORTANT: Utilisation de PostgreSQL via Prisma (wrapper synchrone)
from db_async_wrapper import AirQualityDB, WeatherDB, DatabaseManager
from auth import require_auth
from weather_ui import download_weather_data
from results_ui import display_results
from environment_downloader import EnvironmentDownloader

# ============================================================
# CONFIGURATION LOGGING
# ============================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# FONCTION : TÉLÉCHARGEMENT AUTOMATIQUE DES CARTES
# ============================================================
def download_environment_data_auto(address: str, lat: float, lon: float) -> bool:
    """
    Télécharge automatiquement les cartes satellites et Street View
    avec les options par défaut lors du clic sur "Analyser"

    Args:
        address: Adresse de la localisation
        lat: Latitude
        lon: Longitude

    Returns:
        True si succès
    """
    try:
        downloader = EnvironmentDownloader(address)
        downloader.lat = lat
        downloader.lon = lon
        downloader.formatted_address = address

        logger.info(f"🗺️ Téléchargement automatique des cartes pour: {address}")

        # Configuration par défaut pour les satellites
        satellite_config = {
            'radius_km': 0.5,
            'zoom_levels': [17, 18],
            'map_types': ['satellite', 'roadmap']
        }

        # Configuration par défaut pour Street View
        streetview_config = {
            'radius_m': 250,
            'max_photos': 12,
            'use_smart_filter': True
        }

        # Téléchargement satellites
        if not hasattr(st, 'session_state') or not getattr(st.session_state, 'background_download', False):
             # Mode NORMAL (UI)
            with st.spinner("🛰️ Téléchargement des cartes satellites..."):
                try:
                    sat_metadata = downloader.download_satellite_maps(**satellite_config)
                    total = sat_metadata.get('total_images', 0)
                    logger.info(f"✅ Cartes satellites: {total} images")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur satellites (ignorée): {e}")
                    st.warning("⚠️ Cartes satellites non disponibles")

            # Téléchargement Street View (skip si existant - géré dans le downloader)
            with st.spinner("📸 Téléchargement des images Street View..."):
                try:
                    sv_metadata = downloader.download_streetview_images(**streetview_config)
                    total = sv_metadata.get('total_photos', 0)
                    logger.info(f"✅ Street View: {total} photos")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur Street View (ignorée): {e}")
                    st.warning("⚠️ Images Street View non disponibles")

            st.success("✅ Cartes environnementales prêtes")
            
        return True

    except Exception as e:
        logger.error(f"❌ Erreur téléchargement cartes: {e}")
        if hasattr(st, 'session_state'):
             st.warning("⚠️ Module cartes temporairement indisponible")
        return False

def run_background_download(address, lat, lon):
    """Exécute le téléchargement en arrière-plan sans UI"""
    logger.info(f"🚀 Démarrage téléchargement ARRIÈRE-PLAN pour {address}")
    try:
        # Délai pour simuler "survie" à la déconnexion
        time.sleep(2) 
        
        downloader = EnvironmentDownloader(address)
        downloader.lat = lat
        downloader.lon = lon
        downloader.formatted_address = address
        
        # Configs par défaut
        satellite_config = {
            'radius_km': 0.5,
            'zoom_levels': [17, 18],
            'map_types': ['satellite', 'roadmap']
        }
        
        streetview_config = {
            'radius_m': 250,
            'max_photos': 12,
            'use_smart_filter': True
        }
        
        # Exécution sans UI
        try:
            downloader.download_satellite_maps(**satellite_config)
            logger.info("✅ BG: Satellites terminés")
        except Exception as e:
            logger.error(f"❌ BG: Erreur Satellites: {e}")
            
        try:
            downloader.download_streetview_images(**streetview_config)
            logger.info("✅ BG: StreetView terminé")
        except Exception as e:
            logger.error(f"❌ BG: Erreur StreetView: {e}")
            
        logger.info(f"🏁 Téléchargement arrière-plan TERMINÉ pour {address}")
        
    except Exception as e:
        logger.error(f"❌ CRASH Background Thread: {e}")


# ============================================================
# CONFIGURATION DE LA PAGE STREAMLIT
# ============================================================
st.set_page_config(
    page_title="Qualité de l'Air & Météo - Bruxelles",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# STYLES CSS PERSONNALISÉS
# ============================================================
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    </style>
""", unsafe_allow_html=True)


# ============================================================
# INITIALISATION DE LA SESSION STREAMLIT
# ============================================================
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'current_address' not in st.session_state:
    st.session_state.current_address = None
if 'geocode_results' not in st.session_state:
    st.session_state.geocode_results = None
if 'use_manual' not in st.session_state:
    st.session_state.use_manual = False
if 'manual_lat' not in st.session_state:
    st.session_state.manual_lat = 50.8503
if 'manual_lon' not in st.session_state:
    st.session_state.manual_lon = 4.3517
if 'manual_address' not in st.session_state:
    st.session_state.manual_address = ""
if 'selected_db' not in st.session_state:
    st.session_state.selected_db = None


# ============================================================
# FONCTION PRINCIPALE
# ============================================================
def main():
    """Fonction principale de l'application"""
    logger.info("=== Démarrage de l'application ===")

    # --------------------------------------------------------
    # AUTHENTIFICATION
    # --------------------------------------------------------
    require_auth()

    # --------------------------------------------------------
    # EN-TÊTE DE L'APPLICATION
    # --------------------------------------------------------
    st.markdown('<div class="main-header">🌍 Qualité de l\'Air & Météo - Analyse Géolocalisée</div>',
                unsafe_allow_html=True)

    # --------------------------------------------------------
    # BANDEAU D'INFORMATION - Analyse active
    # --------------------------------------------------------
    if st.session_state.data_loaded and st.session_state.current_address:
        col1, col2 = st.columns([4, 1])

        with col1:
            db_name = st.session_state.selected_db if st.session_state.selected_db else "Base par défaut"

            # Récupérer l'intervalle de dates
            try:
                if st.session_state.selected_db:
                    db = AirQualityDB(address=st.session_state.current_address)
                    db.db_path = st.session_state.selected_db
                else:
                    db = AirQualityDB(address=st.session_state.current_address)

                date_range = db.get_date_range(st.session_state.current_address)

                if date_range and date_range['start_date'] and date_range['end_date']:
                    start = pd.to_datetime(date_range['start_date']).strftime('%d/%m/%Y %H:%M')
                    end = pd.to_datetime(date_range['end_date']).strftime('%d/%m/%Y %H:%M')
                    st.success(f"📊 Analyse active : **{st.session_state.current_address}**\n\n"
                              f"📅 Période : `{start}` → `{end}` | Base : `{Path(db_name).name}`")
                else:
                    st.success(f"📊 Analyse active : **{st.session_state.current_address}** | "
                              f"Base : `{Path(db_name).name}`")
            except Exception as e:
                logger.error(f"Erreur récupération dates: {e}")
                st.success(f"📊 Analyse active : **{st.session_state.current_address}** | "
                          f"Base : `{Path(db_name).name}`")

        with col2:
            if st.button("🔄 Nouvelle analyse"):
                # Garder l'adresse pour pré-remplir le champ de recherche
                st.session_state.force_refresh = True
                st.session_state.data_loaded = False
                # NE PAS effacer current_address pour pré-remplir le champ
                st.session_state.selected_db = None
                st.session_state.refresh_dates = True  # Recalculer dates (15 derniers jours)
                st.rerun()

    # --------------------------------------------------------
    # DÉTECTION DONNÉES EXISTANTES
    # --------------------------------------------------------
    elif Path(DB_PATH).exists() and not st.session_state.data_loaded:
        last_address = get_last_address()
        if last_address:
            st.info(f"📊 Données existantes détectées pour : **{last_address}**")
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("📂 Charger ces données"):
                    st.session_state.data_loaded = True
                    st.session_state.current_address = last_address
                    st.rerun()
            with col2:
                st.caption("Ou entrez une nouvelle adresse dans la barre latérale 👈")

    # --------------------------------------------------------
    # MESSAGE DE DÉMARRAGE
    # --------------------------------------------------------
    elif not st.session_state.data_loaded:
        st.info("👋 Entrez une adresse dans la barre latérale pour commencer l'analyse")

    # --------------------------------------------------------
    # BARRE LATÉRALE - CONFIGURATION
    # --------------------------------------------------------
    with st.sidebar:
        st.header("🎯 Configuration")

        # Mode de saisie
        input_mode = st.radio(
            "Mode de saisie",
            ["🔍 Par adresse", "🔍 Coordonnées manuelles"],
            label_visibility="collapsed"
        )

        address_input = None

        # --------------------------------------------------------
        # MODE : RECHERCHE PAR ADRESSE
        # --------------------------------------------------------
        if input_mode == "🔍 Par adresse":
            # Pré-remplir avec l'adresse chargée depuis la DB si disponible
            default_address = st.session_state.get('current_address', '') or ''
            address_input = st.text_input(
                "🔍 Entrez votre adresse",
                value=default_address,
                placeholder="Ex: Avenue Louise, Bruxelles",
                help="Soyez précis pour de meilleurs résultats"
            )

            # Gestion résultats multiples
            if 'geocode_results' in st.session_state and st.session_state.geocode_results:
                st.warning("🔍 Plusieurs résultats trouvés. Choisissez :")

                options = []
                for i, loc in enumerate(st.session_state.geocode_results[:5]):
                    label = (f"{loc['name']}, {loc.get('admin1', '')}, {loc.get('country', '')} "
                            f"({loc['latitude']:.4f}, {loc['longitude']:.4f})")
                    options.append(label)

                selected = st.selectbox("Sélectionnez votre localisation", options)

                if st.button("✅ Confirmer la sélection", type="primary"):
                    idx = options.index(selected)
                    loc = st.session_state.geocode_results[idx]
                    st.session_state.manual_lat = loc['latitude']
                    st.session_state.manual_lon = loc['longitude']
                    st.session_state.manual_address = f"{loc['name']}, {loc.get('admin1', '')}, {loc.get('country', '')}"
                    st.session_state.geocode_results = None
                    st.session_state.use_manual = True
                    st.rerun()

        # --------------------------------------------------------
        # MODE : COORDONNÉES MANUELLES
        # --------------------------------------------------------
        else:
            st.info("📍 Entrez les coordonnées (format décimal)")
            manual_lat = st.number_input("Latitude", min_value=-90.0, max_value=90.0,
                                        value=50.8503, step=0.0001, format="%.6f")
            manual_lon = st.number_input("Longitude", min_value=-180.0, max_value=180.0,
                                        value=4.3517, step=0.0001, format="%.6f")
            manual_address_name = st.text_input("Nom du lieu (optionnel)", value="Bruxelles")

            if st.button("✅ Utiliser ces coordonnées", type="primary"):
                st.session_state.manual_lat = manual_lat
                st.session_state.manual_lon = manual_lon
                st.session_state.manual_address = (manual_address_name or
                                                   f"Point ({manual_lat:.4f}, {manual_lon:.4f})")
                st.session_state.use_manual = True

        # --------------------------------------------------------
        # SÉLECTION PÉRIODE
        # --------------------------------------------------------
        # Calculer automatiquement les 15 derniers jours
        # Si refresh_dates=True (après chargement DB), recalculer ; sinon garder sélection utilisateur
        if st.session_state.get('refresh_dates', True):
            end_date = datetime.now()
            start_date = end_date - timedelta(days=15)
            st.session_state.date_start = start_date.date()
            st.session_state.date_end = end_date.date()
            st.session_state.refresh_dates = False  # Reset flag
        else:
            # Utiliser dates existantes si disponibles
            start_date = datetime.combine(
                st.session_state.get('date_start', (datetime.now() - timedelta(days=15)).date()), 
                datetime.min.time()
            )
            end_date = datetime.combine(
                st.session_state.get('date_end', datetime.now().date()), 
                datetime.min.time()
            )
        
        date_range = st.date_input(
            "📅 Période d'analyse",
            value=(start_date.date(), end_date.date()),
            help="Sélectionnez la période de données (par défaut: 15 derniers jours)"
        )
        
        # Sauvegarder la sélection utilisateur
        if isinstance(date_range, tuple) and len(date_range) == 2:
            st.session_state.date_start = date_range[0]
            st.session_state.date_end = date_range[1]

        search_button = st.button("🔍 Analyser", type="primary", width="stretch")
        
        # Auto-trigger si force_refresh actif (après clic "Nouvelle analyse")
        if st.session_state.get('force_refresh', False) and st.session_state.get('current_address'):
            search_button = True  # Simulate button click
            st.session_state.force_refresh = False  # Reset flag

        st.divider()

        # --------------------------------------------------------
        # OPTIONS AVANCÉES
        # --------------------------------------------------------
        with st.expander("⚙️ Options avancées"):
            auto_refresh = st.checkbox("Rafraîchir automatiquement les données", value=False)
            st.session_state.show_raw_data = st.checkbox("Afficher les données brutes", value=False)
            
            # Checkbox pour téléchargement arrière-plan
            bg_download = st.checkbox("📥 Téléchargement en arrière-plan (Persistant)", 
                                     value=False,
                                     help="Si activé, les téléchargements continuent même si vous quittez la page ou êtes déconnecté.")
            st.session_state.background_download = bg_download

        # --------------------------------------------------------
        # GESTION DES BASES DE DONNÉES
        # --------------------------------------------------------
        st.divider()
        st.subheader("🗄️ Bases de données")

        # Lister toutes les bases disponibles
        available_dbs = DatabaseManager.list_all_databases('air_quality')

        if available_dbs:
            st.success(f"✅ {len(available_dbs)} base(s) disponible(s)")

            # Sélecteur de bases de données
            with st.expander("📂 Charger une base existante", expanded=False):
                st.caption("Sélectionnez une base de données historique à analyser")

                for idx, db_info in enumerate(available_dbs):
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.write(f"**{db_info['address'].replace('_', ' ').title()}**")
                        st.caption(f"📅 {db_info['date_range']}")
                        st.caption(f"📊 {db_info['records']} enregistrements • {db_info['size']:.2f} MB")
                        st.caption(f"🕒 Modifié: {pd.to_datetime(db_info['modified']).strftime('%d/%m/%Y %H:%M')}")

                    with col2:
                        if st.button("📥 Charger", key=f"load_db_{idx}"):
                            st.session_state.selected_db = db_info['path']
                            st.session_state.current_address = db_info['address'].replace('_', ' ').title()
                            st.session_state.data_loaded = True
                            st.session_state.refresh_dates = True  # Force recalcul dates (15 derniers jours)
                            st.success(f"✅ Base chargée: {Path(db_info['path']).name}")
                            st.rerun()

                    if idx < len(available_dbs) - 1:
                        st.divider()

            # Option de réinitialisation
            if Path(DB_PATH).exists():
                with st.expander("⚠️ Options de maintenance"):
                    if st.button("🔄 Réinitialiser la base par défaut", type="secondary"):
                        try:
                            Path(DB_PATH).unlink()
                            st.session_state.data_loaded = False
                            st.session_state.current_address = None
                            st.session_state.selected_db = None
                            st.success("Base par défaut réinitialisée !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur : {e}")
        else:
            st.info("🔭 Aucune base de données disponible")
            st.caption("Téléchargez des données pour une adresse pour créer votre première base.")

    # --------------------------------------------------------
    # TRAITEMENT : COORDONNÉES MANUELLES
    # --------------------------------------------------------
    if 'use_manual' in st.session_state and st.session_state.use_manual:
        logger.info(f"Recherche par coordonnées manuelles: {st.session_state.manual_address}")
        lat = st.session_state.manual_lat
        lon = st.session_state.manual_lon
        full_address = st.session_state.manual_address

        st.success(f"Coordonnées manuelles : {full_address}")
        st.info(f"Latitude: {lat:.6f}N, Longitude: {lon:.6f}E")
        st.markdown(f"[Vérifier sur Google Maps](https://www.google.com/maps?q={lat},{lon})")

        # Télécharger les données
        with st.spinner("Téléchargement des données..."):
            logger.info(f"Téléchargement air quality pour: {full_address}")
            success, info = download_air_quality_data(
                lat, lon, full_address,
                date_range[0].strftime("%Y-%m-%d"),
                date_range[1].strftime("%Y-%m-%d")
            )

        if success and info:
            st.success(f"{info['records']} enregistrements téléchargés")

            # Télécharger aussi la météo
            download_weather_data(full_address, lat, lon)

            # Télécharger automatiquement les cartes
            if st.session_state.get('background_download', False):
                st.info("🚀 Téléchargement d'images lancé en arrière-plan...")
                t = threading.Thread(target=run_background_download, args=(full_address, lat, lon), daemon=True)
                t.start()
            else:
                download_environment_data_auto(full_address, lat, lon)

            st.session_state.data_loaded = True
            st.session_state.current_address = full_address
            st.session_state.use_manual = False
            logger.info(f"Données chargées avec succès pour: {full_address}")
            st.rerun()

    # --------------------------------------------------------
    # TRAITEMENT : RECHERCHE PAR ADRESSE
    # --------------------------------------------------------
    if search_button:
        logger.info(f"Recherche par adresse: {address_input}")
        if not address_input:
            st.warning("Veuillez entrer une adresse")
        else:
            with st.spinner("Géolocalisation en cours..."):
                result = geocode_address(address_input)

            # Gérer les résultats multiples
            if result == ("MULTIPLE_RESULTS", None, None):
                logger.info("Géocodage: plusieurs résultats - attente sélection utilisateur")
                st.info("Plusieurs résultats trouvés. Sélectionnez votre localisation ci-dessus.")

            else:
                lat, lon, full_address = result

                if lat and lon:
                    st.success(f"Adresse trouvée : {full_address}")
                    st.info(f"Coordonnées : {lat:.6f}N, {lon:.6f}E")
                    st.markdown(f"[Vérifier sur Google Maps](https://www.google.com/maps?q={lat},{lon})")

                    # Télécharger les données de qualité de l'air
                    with st.spinner("Téléchargement des données de qualité de l'air..."):
                        logger.info(f"Téléchargement air quality pour: {full_address}")
                        success, info = download_air_quality_data(
                            lat, lon, full_address,
                            date_range[0].strftime("%Y-%m-%d"),
                            date_range[1].strftime("%Y-%m-%d")
                        )

                    if success and info:
                        st.success(f"{info['records']} enregistrements air quality téléchargés")

                        # Télécharger aussi la météo
                        download_weather_data(full_address, lat, lon)

                        # Télécharger automatiquement les cartes
                        if st.session_state.get('background_download', False):
                            st.info("🚀 Téléchargement d'images lancé en arrière-plan...")
                            t = threading.Thread(target=run_background_download, args=(full_address, lat, lon), daemon=True)
                            t.start()
                        else:
                            download_environment_data_auto(full_address, lat, lon)

                        st.session_state.data_loaded = True
                        st.session_state.current_address = full_address
                        logger.info(f"Données chargées avec succès pour: {full_address}")
                        st.rerun()
                    else:
                        logger.error(f"Échec téléchargement pour: {full_address}")
                else:
                    logger.warning(f"Adresse introuvable: {address_input}")
                    st.error("Adresse introuvable. Utilisez le mode 'Coordonnées manuelles' ci-dessus.")

    # --------------------------------------------------------
    # AFFICHAGE DES RÉSULTATS
    # --------------------------------------------------------
    if st.session_state.data_loaded and st.session_state.current_address:
        logger.info(f"Affichage résultats pour: {st.session_state.current_address}")
        display_results(st.session_state.current_address)

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------
    st.divider()
    st.markdown("""
        <div style='text-align: center; color: gray;'>
            Données fournies par Open-Meteo Air Quality API & Meteosource |
            Application développée avec Streamlit
        </div>
    """, unsafe_allow_html=True)


# ============================================================
# POINT D'ENTRÉE
# ============================================================
if __name__ == "__main__":
    main()
