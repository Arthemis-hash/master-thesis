#!/usr/bin/env python3
"""
Application Streamlit - Qualité de l'air + Météo Bruxelles
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging
import folium
from streamlit_folium import st_folium

from config import geocode_address, validate_config_on_startup
# Nouvelles API fonctionnelles
from api_irceline import IrcelineAPI
from api_irm import IRMWeatherAPI, get_weather_summary, get_weather_icon
from db_utils import BrusselsAirQualityDB, WeatherDB, list_all_databases
from data_validator import DataValidator, show_validation_ui
from scoring import calculate_global_aqi, get_health_recommendations
from visualization import (
    plot_pollutant_evolution, plot_multi_pollutants,
    plot_aqi_gauge, plot_comparison_radar, plot_heatmap_calendar
)
from comparison import show_comparison_ui

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_map(lat: float, lon: float, address: str, stations=None, radius_m=500):
    """
    Crée une carte Folium avec la localisation et les stations
    
    Args:
        lat, lon: Coordonnées du point recherché
        address: Adresse formatée
        stations: Liste de stations (optionnel)
        radius_m: Rayon en mètres
    """
    # Créer carte centrée sur l'adresse
    m = folium.Map(
        location=[lat, lon],
        zoom_start=14,
        tiles="OpenStreetMap"
    )
    
    # Marqueur principal (adresse recherchée)
    folium.Marker(
        [lat, lon],
        popup=f"<b>📍 {address}</b>",
        tooltip="Localisation recherchée",
        icon=folium.Icon(color='red', icon='home', prefix='fa')
    ).add_to(m)
    
    # Cercle de rayon
    folium.Circle(
        [lat, lon],
        radius=radius_m,
        popup=f"Rayon: {radius_m}m",
        color='blue',
        fill=True,
        fillOpacity=0.1
    ).add_to(m)
    
    # Ajouter stations si disponibles
    if stations:
        for station in stations:
            # Déterminer couleur selon type
            if hasattr(station, 'station_id'):
                # Station qualité air
                icon_color = 'green'
                icon_name = 'leaf'
                station_type = "Qualité air"
                popup_text = f"<b>{station.station_name}</b><br>"
                popup_text += f"ID: {station.station_id}<br>"
                if hasattr(station, 'distance_km') and station.distance_km:
                    popup_text += f"Distance: {station.distance_km}km<br>"
                
                # Ajouter valeurs polluants
                if hasattr(station, 'no2') and station.no2:
                    popup_text += f"NO2: {station.no2} µg/m³<br>"
                if hasattr(station, 'pm2_5') and station.pm2_5:
                    popup_text += f"PM2.5: {station.pm2_5} µg/m³<br>"
                if hasattr(station, 'pm10') and station.pm10:
                    popup_text += f"PM10: {station.pm10} µg/m³<br>"
                if hasattr(station, 'o3') and station.o3:
                    popup_text += f"O3: {station.o3} µg/m³<br>"
            else:
                # Station météo
                icon_color = 'blue'
                icon_name = 'cloud'
                station_type = "Météo"
                popup_text = f"<b>{station.station_name}</b><br>"
                popup_text += f"Code: {station.station_code}<br>"
                if hasattr(station, 'distance_km') and station.distance_km:
                    popup_text += f"Distance: {station.distance_km}km<br>"
                if hasattr(station, 'temperature') and station.temperature:
                    popup_text += f"Temp: {station.temperature}°C<br>"
            
            folium.Marker(
                [station.latitude, station.longitude],
                popup=popup_text,
                tooltip=f"{station_type}: {station.station_name}",
                icon=folium.Icon(color=icon_color, icon=icon_name, prefix='fa')
            ).add_to(m)
    
    return m

# Validation config
validate_config_on_startup()

st.set_page_config(
    page_title="Air Quality & Weather - Brussels",
    page_icon="🌍",
    layout="wide"
)

# ============================================================
# SESSION STATE
# ============================================================
if 'addresses' not in st.session_state:
    st.session_state.addresses = {}
if 'current_air_db' not in st.session_state:
    st.session_state.current_air_db = None
if 'current_weather_db' not in st.session_state:
    st.session_state.current_weather_db = None


# ============================================================
# SIDEBAR - CONFIGURATION
# ============================================================
st.sidebar.title("⚙️ Configuration")

# ========== MODE: NOUVELLE ANALYSE OU CHARGER EXISTANTE ==========
analysis_mode = st.sidebar.radio(
    "📂 Mode d'analyse",
    ["🔍 Nouvelle analyse", "📂 Charger données existantes"],
    help="Nouvelle analyse télécharge de nouvelles données. Charger utilise les bases de données existantes."
)

# ========== SI MODE CHARGER EXISTANTE ==========
if analysis_mode == "📂 Charger données existantes":
    st.sidebar.markdown("---")
    st.sidebar.info("💡 Chargement des données depuis les bases existantes")
    
    # Lister les bases de données disponibles
    existing_dbs = list_all_databases()
    
    if existing_dbs.empty:
        st.sidebar.warning("⚠️ Aucune base de données trouvée. Passez en mode 'Nouvelle analyse'.")
    else:
        # Filtrer uniquement les bases air_quality
        air_dbs = existing_dbs[existing_dbs['type'] == 'air_quality'].copy()
        
        if air_dbs.empty:
            st.sidebar.warning("⚠️ Aucune base de données de qualité d'air trouvée.")
        else:
            # Extraire les adresses depuis les noms de fichiers
            # Gérer les deux formats : brussels_air_{addr}_{timestamp}.db et air_quality_{addr}.db
            air_dbs['address'] = air_dbs['filename'].str.replace('brussels_air_', '').str.replace('air_quality_', '').str.replace('.db', '')
            # Enlever le timestamp si présent (format: _20251127_221847)
            air_dbs['address'] = air_dbs['address'].str.replace(r'_\d{8}_\d{6}$', '', regex=True)
            
            # Créer un mapping filename -> address lisible
            address_options = {}
            for idx, row in air_dbs.iterrows():
                readable = row['address'].replace('_', ' ').title()
                address_options[readable] = row['filename']
            
            selected_readable = st.sidebar.selectbox(
                "📍 Sélectionner une adresse",
                options=list(address_options.keys())
            )
            
            selected_filename = address_options[selected_readable]
            
            # Afficher infos de la base sélectionnée
            db_info = air_dbs[air_dbs['filename'] == selected_filename].iloc[0]
            st.sidebar.caption(f"📊 {db_info['records']} enregistrements")
            st.sidebar.caption(f"📅 {db_info['date_range']}")
            st.sidebar.caption(f"💾 {db_info['size_mb']} MB")
            
            if st.sidebar.button("📂 Charger cette base", type="primary", use_container_width=True):
                # Extraire l'adresse normalisée pour WeatherDB
                selected_address = db_info['address']
                
                # Charger la base sélectionnée
                air_db = BrusselsAirQualityDB(address=selected_address, force_new=False)
                weather_db = WeatherDB(address=selected_address)
                
                # Récupérer la vraie adresse depuis la base (pour les filtres)
                actual_air_address = air_db.get_actual_address_from_db()
                if actual_air_address:
                    air_db.current_address = actual_air_address
                    logger.info(f"✅ Adresse air récupérée depuis DB: {actual_air_address}")
                
                actual_weather_address = weather_db.get_actual_address_from_db()
                if actual_weather_address:
                    weather_db.current_address = actual_weather_address
                    logger.info(f"✅ Adresse météo récupérée depuis DB: {actual_weather_address}")
                
                # Stocker en session_state
                st.session_state.current_air_db = air_db
                st.session_state.current_weather_db = weather_db
                st.session_state.loaded_from_db = True  # Flag pour indiquer chargement depuis DB
                
                # Récupérer les coordonnées depuis la base
                summary = air_db.get_summary()
                if summary:
                    # Ajouter aux adresses si pas déjà présent
                    if 'addresses' not in st.session_state:
                        st.session_state.addresses = {}
                    
                    st.session_state.addresses[selected_address] = {
                        'lat': summary.get('latitude', 50.8503),  # Bruxelles par défaut si pas de coordonnées
                        'lon': summary.get('longitude', 4.3517),
                        'full_address': selected_readable
                    }
                
                st.sidebar.success(f"✅ Base chargée : {selected_readable}")
                st.rerun()

# ========== SECTION 1: LOCALISATION (Mode Nouvelle Analyse SEULEMENT) ==========
if analysis_mode == "🔍 Nouvelle analyse":
    st.sidebar.markdown("---")
    st.sidebar.subheader("📍 Localisation")
    
    # Choix du mode de recherche
    search_mode = st.sidebar.radio(
        "Mode de recherche",
        ["🏠 Par adresse", "🏢 Station prédéfinie"],
        horizontal=True
    )
    
    if search_mode == "🏠 Par adresse":
        address_input = st.sidebar.text_input(
            "Adresse",
            placeholder="Ex: Place Flagey, 1050 Ixelles"
        )
        
        radius = st.sidebar.slider(
            "📍 Rayon de recherche (mètres)",
            min_value=100,
            max_value=1000,
            value=500,
            step=100,
            help="Distance maximale pour chercher les stations (max 1km)"
        )
    else:
        # Sélection station prédéfinie
        from api_irm import STATIONS
        
        station_options = {
            f"{code} - {info['name']}": code 
            for code, info in STATIONS.items()
        }
        
        selected_station = st.sidebar.selectbox(
            "Station météo IRM",
            options=list(station_options.keys())
        )
        
        station_code = station_options[selected_station]
        station_info = STATIONS[station_code]
        
        # Utiliser coordonnées de la station
        address_input = station_info['name']
        radius = st.sidebar.slider(
            "📍 Rayon de recherche (km)",
            min_value=0.5,
            max_value=20.0,
            value=5.0,
            step=0.5
        )
        
        st.sidebar.info(f"📍 {station_info['name']}\n📊 Lat: {station_info['lat']}, Lon: {station_info['lon']}")
    
    # ========== SECTION 2: PÉRIODE ==========
    st.sidebar.subheader("📅 Période de données")
    
    # Raccourcis temporels
    time_presets = st.sidebar.radio(
        "Période rapide",
        ["📅 Personnalisée", "📆 Dernières 24h", "📆 7 derniers jours", "📆 30 derniers jours"],
        horizontal=False
    )
    
    if time_presets == "📆 Dernières 24h":
        start_date = (datetime.now() - timedelta(days=1)).date()
        end_date = datetime.now().date()
    elif time_presets == "📆 7 derniers jours":
        start_date = (datetime.now() - timedelta(days=7)).date()
        end_date = datetime.now().date()
    elif time_presets == "📆 30 derniers jours":
        start_date = (datetime.now() - timedelta(days=30)).date()
        end_date = datetime.now().date()
    else:
        col_date1, col_date2 = st.sidebar.columns(2)
        with col_date1:
            start_date = st.date_input(
                "Début",
                value=datetime.now() - timedelta(days=7),
                max_value=datetime.now().date()
            )
        with col_date2:
            end_date = st.date_input(
                "Fin",
                value=datetime.now().date(),
                max_value=datetime.now().date()
            )
    
    # Afficher durée
    if start_date <= end_date:
        days_diff = (end_date - start_date).days + 1
        st.sidebar.caption(f"📊 Durée: {days_diff} jour{'s' if days_diff > 1 else ''}")
    else:
        st.sidebar.error("❌ La date de début doit être antérieure à la date de fin")
    
    # ========== SECTION 3: SOURCES DE DONNÉES ==========
    st.sidebar.subheader("🔬 Sources de données")
    
    include_weather = st.sidebar.checkbox("☁️ Météo IRM", value=True, help="Inclure données météorologiques")
    include_air_quality = st.sidebar.checkbox("🌫️ Qualité de l'air IRCELINE", value=True, help="Inclure données de pollution")
    
    # Sélection des polluants
    if include_air_quality:
        with st.sidebar.expander("🔬 Polluants à récupérer"):
            pollutants = {
                'PM2.5': st.checkbox("PM2.5 - Particules fines", value=True),
                'PM10': st.checkbox("PM10 - Particules", value=True),
                'NO2': st.checkbox("NO₂ - Dioxyde d'azote", value=True),
                'O3': st.checkbox("O₃ - Ozone", value=True)
            }
            
            selected_pollutants = [k.lower().replace('₂', '2').replace('₃', '3').replace('.', '_') 
                                  for k, v in pollutants.items() if v]
            
            if not selected_pollutants:
                st.warning("⚠️ Sélectionnez au moins un polluant")
    else:
        selected_pollutants = ['pm2_5', 'pm10', 'no2', 'o3']
    
    # ========== SECTION 4: OPTIONS AVANCÉES ==========
    with st.sidebar.expander("⚙️ Options avancées"):
        max_stations_air = st.slider(
            "Nombre max de stations air",
            min_value=1,
            max_value=10,
            value=3,
            help="Nombre maximum de stations de qualité de l'air à interroger"
        )
        
        limit_records = st.slider(
            "Limite d'enregistrements",
            min_value=100,
            max_value=10000,
            value=1000,
            step=100,
            help="Nombre maximum d'enregistrements par polluant"
        )
        
        show_raw_data = st.checkbox(
            "📋 Afficher données brutes",
            value=st.session_state.get('show_raw_data', False),
            help="Afficher les tableaux de données brutes"
        )
        st.session_state.show_raw_data = show_raw_data
        
        enable_validation = st.checkbox(
            "✅ Validation des données",
            value=True,
            help="Activer la validation et correction automatique des données"
        )
        
        api_timeout = st.number_input(
            "Timeout API (secondes)",
            min_value=10,
            max_value=60,
            value=20,
            help="Délai maximum d'attente pour les requêtes API"
        )
    
    # ========== SECTION 5: VISUALISATION ==========
    with st.sidebar.expander("📊 Options de visualisation"):
        chart_theme = st.selectbox(
            "Thème des graphiques",
            ["plotly", "plotly_white", "plotly_dark", "ggplot2", "seaborn"]
        )
        
        show_interpolation = st.checkbox(
            "Interpolation des données",
            value=False,
            help="Interpoler les valeurs manquantes dans les graphiques"
        )
        
        aggregation_method = st.selectbox(
            "Méthode d'agrégation",
            ["Moyenne", "Médiane", "Maximum", "Minimum"],
            help="Méthode pour agréger les données de plusieurs stations"
        )
    
    # Validate date range
    if start_date > end_date:
        st.sidebar.error("❌ La date de début doit être antérieure à la date de fin")
    
    # BOUTON RECHERCHER (Mode Nouvelle Analyse)
    if st.sidebar.button("🔍 Rechercher", type="primary", use_container_width=True):
        # Vérifications préliminaires
        if not include_weather and not include_air_quality:
            st.sidebar.error("❌ Sélectionnez au moins une source de données")
        elif include_air_quality and not selected_pollutants:
            st.sidebar.error("❌ Sélectionnez au moins un polluant")
        elif not address_input:
            st.sidebar.error("❌ Entrez une adresse ou sélectionnez une station")
        else:
            # Géocodage
            if search_mode == "🏢 Station prédéfinie":
                lat = station_info['lat']
                lon = station_info['lon']
                full_address = station_info['name']
            else:
                with st.spinner("🔍 Géocodage..."):
                    lat, lon, full_address = geocode_address(address_input)

            if lat and lon and lat != "MULTIPLE_RESULTS":
                # Afficher carte de localisation
                st.subheader(f"📍 {full_address}")
                
                # Créer carte simple d'abord (sans stations)
                map_preview = create_map(lat, lon, full_address, stations=None, radius_m=radius)
                st_folium(map_preview, width=700, height=400)
                
                # Validate dates
                if start_date > end_date:
                    st.sidebar.error("❌ Corrigez la période sélectionnée")
                else:
                    # Calculate days range
                    days_range = (end_date - start_date).days + 1
                    st.sidebar.info(f"📊 Période: {days_range} jour{'s' if days_range > 1 else ''}")

                    # ========== QUALITÉ AIR ==========
                    pollutant_data = {}
                    current_air_data = None
                    
                    if include_air_quality:
                        api_air = IrcelineAPI(timeout=api_timeout)

                        with st.spinner(f"📡 Téléchargement qualité air ({start_date} → {end_date})..."):
                            # D'abord essayer données actuelles
                            try:
                                current_air_data = api_air.get_air_quality(
                                    lat, lon,
                                    radius_km=radius,
                                    max_stations=5
                                )
                                if current_air_data:
                                    st.sidebar.success(f"✅ {len(current_air_data)} stations actuelles trouvées")
                            except Exception as e:
                                logger.error(f"Erreur données actuelles: {e}")
                            
                            # Ensuite essayer données historiques
                            for pollutant in selected_pollutants:
                                try:
                                    df = api_air.get_historical_data(
                                        lat, lon,
                                        start_date=start_date,
                                        end_date=end_date,
                                        pollutant=pollutant,
                                        radius_km=radius
                                    )
                                    if not df.empty:
                                        pollutant_data[pollutant] = df.head(limit_records)
                                        st.sidebar.success(f"✅ {pollutant.upper()}: {len(df)} mesures")
                                    else:
                                        st.sidebar.warning(f"⚠️ {pollutant.upper()}: Pas de données historiques")
                                except Exception as e:
                                    logger.error(f"Erreur {pollutant}: {e}")
                                    st.sidebar.warning(f"⚠️ {pollutant.upper()}: Erreur récupération")

                    # Insérer données en DB
                    if pollutant_data or current_air_data:
                        # IMPORTANT: Utiliser full_address pour garantir l'unicité des bases de données
                        air_db = BrusselsAirQualityDB(address=full_address, force_new=False)

                        total_inserted = 0
                        
                        # Insérer données historiques
                        for pollutant, df in pollutant_data.items():
                            stats = air_db.insert_brussels_data(df, pollutant)
                            total_inserted += stats['inserted'] + stats['updated']
                        
                        # Insérer données actuelles si pas d'historique
                        if current_air_data and not pollutant_data:
                            import pandas as pd
                            
                            for station_data in current_air_data:
                                for pollutant in selected_pollutants:
                                    value = getattr(station_data, pollutant, None)
                                    if value is not None:
                                        # Créer DataFrame pour insertion
                                        df_current = pd.DataFrame([{
                                            'timestamp': station_data.timestamp,
                                            'value': value,
                                            'pollutant': pollutant,
                                            'unit': 'µg/m³',
                                            'station_id': station_data.station_id,
                                            'station_name': station_data.station_name,
                                            'latitude': station_data.latitude,
                                            'longitude': station_data.longitude
                                        }])
                                        
                                        stats = air_db.insert_brussels_data(df_current, pollutant)
                                        total_inserted += stats['inserted'] + stats['updated']

                        st.session_state.current_air_db = air_db
                        
                        if total_inserted > 0:
                            st.sidebar.success(f"✅ Air: {total_inserted} enregistrements")
                        else:
                            st.sidebar.info(f"ℹ️ Air: Base de données créée, données actuelles disponibles")

                        # Info capteur le plus proche
                        stations_data = current_air_data or api_air.get_air_quality(lat, lon, radius_km=radius, max_stations=1)
                        if stations_data:
                            nearest = stations_data[0]
                            info_text = f"📍 **Station air**: {nearest.station_name}"
                            
                            if nearest.distance_km:
                                info_text += f"\nDistance: {nearest.distance_km}km"
                            
                            # Afficher polluants disponibles
                            available = []
                            for pol in ['no2', 'o3', 'pm10', 'pm2_5']:
                                if getattr(nearest, pol, None) is not None:
                                    available.append(pol.upper())
                            
                            if available:
                                info_text += f"\nPolluants: {', '.join(available)}"
                            
                            st.sidebar.info(info_text)
                        else:
                            st.sidebar.warning(f"⚠️ Aucun capteur air dans {radius}m")

                    # ========== MÉTÉO ==========
                    if include_weather:
                        api_weather = IRMWeatherAPI(timeout=api_timeout)

                        with st.spinner(f"🌤️ Téléchargement météo ({start_date} → {end_date})..."):
                            weather_list = api_weather.get_historical_weather(
                                lat, lon,
                                start_date=start_date,
                                end_date=end_date,
                                station_name=full_address,
                                sample_hours=2  # Échantillonner toutes les 2h
                            )

                        if weather_list:
                            # IMPORTANT: Utiliser full_address pour garantir l'unicité des bases de données
                            weather_db = WeatherDB(address=full_address, force_new=False)

                            # Convertir WeatherData en dict
                            weather_dicts = [w.to_dict() for w in weather_list]
                            stats = weather_db.insert_multiple(weather_dicts)
                            st.session_state.current_weather_db = weather_db
                            st.sidebar.success(f"✅ Météo: {stats['inserted']} enregistrements")

                            if weather_list:
                                first_record = weather_list[0]
                                st.sidebar.info(
                                    f"🌡️ **Station météo IRM**: {first_record.station_name}\n"
                                    f"Température: {first_record.temperature}°C\n"
                                    f"Distance: {first_record.distance_km}km"
                                )
                        else:
                            st.sidebar.warning("⚠️ Données météo IRM indisponibles")

                    # Stocker infos adresse
                    # IMPORTANT: Utiliser full_address comme clé pour garantir l'unicité
                    st.session_state.addresses[full_address] = {
                        'lat': lat,
                        'lon': lon,
                        'full_address': full_address,
                        'radius': radius,
                        'start_date': start_date,
                        'end_date': end_date
                    }

# ============================================================
# MAIN CONTENT
# ============================================================
st.title("🌍 Qualité de l'Air & Météo - Bruxelles")

if not st.session_state.current_air_db:
    st.info("👈 Commencez par entrer une adresse dans le panneau latéral")

    # Afficher DBs existantes
    st.subheader("📂 Bases de données disponibles")
    existing_dbs = list_all_databases()

    if not existing_dbs.empty:
        st.dataframe(
            existing_dbs[['filename', 'type', 'records', 'date_range', 'size_mb']],
            use_container_width=True
        )
    else:
        st.info("Aucune base de données trouvée")

else:
    air_db = st.session_state.current_air_db
    weather_db = st.session_state.current_weather_db
    address = air_db.current_address

    # ============================================================
    # HEADER - MÉTÉO ACTUELLE + QUALITÉ AIR
    # ============================================================
    st.header(f"📍 {address}")

    col_weather, col_air = st.columns([1, 2])

    # ========== MÉTÉO ACTUELLE ==========
    with col_weather:
        if weather_db:
            latest_weather = weather_db.get_latest_weather()

            if latest_weather:
                weather_icon = get_weather_icon(latest_weather.get('weather_code'))
                weather_summary = get_weather_summary(latest_weather)

                st.markdown(f"### {weather_icon} Météo actuelle")
                st.metric(
                    "Température",
                    f"{latest_weather['temperature']}°C",
                    delta=f"Ressenti {latest_weather.get('feels_like')}°C"
                )

                col_w1, col_w2 = st.columns(2)
                with col_w1:
                    st.metric("💧 Humidité", f"{latest_weather.get('humidity')}%")
                with col_w2:
                    st.metric("💨 Vent", f"{latest_weather.get('wind_speed')} km/h")

                with st.expander("ℹ️ Détails météo"):
                    st.write(f"**Station**: {latest_weather['station_name']}")
                    st.write(f"**Direction vent**: {latest_weather.get('wind_direction_text', 'N/A')}")
                    st.write(f"**Pression**: {latest_weather.get('pressure')} hPa")
                    st.write(f"**Visibilité**: {latest_weather.get('visibility')} m")
                    st.write(f"**Horodatage**: {latest_weather['timestamp']}")
            else:
                st.info("Aucune donnée météo récente")
        else:
            st.info("☁️ Météo non chargée")

    # ========== QUALITÉ AIR ==========
    with col_air:
        summary = air_db.get_summary()

        if summary:
            st.markdown("### 🌡️ Qualité de l'air")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                pm25 = summary.get('avg_pm2_5')
                st.metric("PM2.5", f"{pm25:.1f}" if pm25 else "N/A", help="Particules fines")
            with col2:
                pm10 = summary.get('avg_pm10')
                st.metric("PM10", f"{pm10:.1f}" if pm10 else "N/A", help="Particules moyennes")
            with col3:
                no2 = summary.get('avg_no2')
                st.metric("NO₂", f"{no2:.1f}" if no2 else "N/A", help="Dioxyde azote")
            with col4:
                o3 = summary.get('avg_o3')
                st.metric("O₃", f"{o3:.1f}" if o3 else "N/A", help="Ozone")

            st.caption(f"📊 {summary['total_records']} mesures | {summary['num_stations']} stations")

    # ============================================================
    # ONGLETS PRINCIPAUX
    # ============================================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Vue d'ensemble",
        "📈 Évolution temporelle",
        "☁️ Météo détaillée",
        "⚖️ Comparaison"
    ])

    # ========== ONGLET 1: VUE D'ENSEMBLE ==========
    with tab1:
        st.subheader("Indice de qualité de l'air")

        # Calculer AQI
        latest_air = air_db.get_all_data(limit=1)

        if not latest_air.empty:
            from scoring import calculate_pollutant_score

            latest = latest_air.iloc[0]
            scores = {
                'pm2_5': calculate_pollutant_score('pm2_5', latest.get('pm2_5', 0))[0],
                'pm10': calculate_pollutant_score('pm10', latest.get('pm10', 0))[0],
                'no2': calculate_pollutant_score('no2', latest.get('nitrogen_dioxide', 0))[0],
                'o3': calculate_pollutant_score('o3', latest.get('ozone', 0))[0]
            }

            aqi_score = min([s for s in scores.values() if s > 0], default=50)
            category = 'excellent' if aqi_score >= 90 else 'good' if aqi_score >= 70 else 'moderate' if aqi_score >= 50 else 'poor'

            col_gauge, col_info = st.columns([1, 2])

            with col_gauge:
                fig_gauge = plot_aqi_gauge(aqi_score, category)
                st.plotly_chart(fig_gauge, use_container_width=True)

            with col_info:
                health_info = get_health_recommendations(category)
                st.markdown(f"### {health_info['message']}")
                st.info(health_info['advice'])

                st.markdown("**Détail par polluant:**")
                for pollutant, score in scores.items():
                    if score > 0:
                        st.progress(score / 100, text=f"{pollutant.upper()}: {score}/100")

    # ========== ONGLET 2: ÉVOLUTION ==========
    with tab2:
        st.subheader("Évolution des polluants")

        # Récupérer polluants disponibles dans la DB
        available_pollutants = []
        for poll in ['pm2_5', 'pm10', 'no2', 'o3']:
            df_test = air_db.get_pollutant_data(poll)
            if not df_test.empty:
                available_pollutants.append(poll)

        if not available_pollutants:
            st.warning("⚠️ Aucun polluant disponible dans la base de données")
        else:
            pollutant_choice = st.selectbox(
                "Choisir un polluant",
                available_pollutants,
                format_func=lambda x: x.upper()
            )

            df_plot = air_db.get_pollutant_data(pollutant_choice)

            if not df_plot.empty:
                df_plot = df_plot.rename(columns={'timestamp': 'timestamp', 'value': 'value'})
                df_plot['unit'] = 'µg/m³'

                # Graphique
                fig = plot_pollutant_evolution(df_plot, pollutant_choice, address)
                st.plotly_chart(fig, use_container_width=True)

                # Statistiques
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("🔻 Minimum", f"{df_plot['value'].min():.1f} µg/m³")
                with col2:
                    st.metric("📊 Moyenne", f"{df_plot['value'].mean():.1f} µg/m³")
                with col3:
                    st.metric("📈 Médiane", f"{df_plot['value'].median():.1f} µg/m³")
                with col4:
                    st.metric("🔺 Maximum", f"{df_plot['value'].max():.1f} µg/m³")
                
                # Statistiques avancées
                with st.expander("📊 Statistiques détaillées"):
                    col_s1, col_s2, col_s3 = st.columns(3)
                    
                    with col_s1:
                        st.write("**Distribution**")
                        st.write(f"Écart-type: {df_plot['value'].std():.2f}")
                        st.write(f"Variance: {df_plot['value'].var():.2f}")
                        st.write(f"Quartile 25%: {df_plot['value'].quantile(0.25):.2f}")
                        st.write(f"Quartile 75%: {df_plot['value'].quantile(0.75):.2f}")
                    
                    with col_s2:
                        st.write("**Données**")
                        st.write(f"Total mesures: {len(df_plot)}")
                        st.write(f"Stations: {df_plot['station_name'].nunique()}")
                        st.write(f"Période: {df_plot['timestamp'].min().date()} → {df_plot['timestamp'].max().date()}")
                    
                    with col_s3:
                        st.write("**Qualité**")
                        valeurs_nulles = df_plot['value'].isnull().sum()
                        pct_null = (valeurs_nulles / len(df_plot)) * 100
                        st.write(f"Valeurs nulles: {valeurs_nulles} ({pct_null:.1f}%)")
                        st.write(f"Taux complétude: {100-pct_null:.1f}%")

                # Données brutes (si option activée)
                if 'show_raw_data' in st.session_state and st.session_state.get('show_raw_data', False):
                    with st.expander("📋 Données brutes"):
                        st.dataframe(
                            df_plot[['timestamp', 'value', 'station_name', 'latitude', 'longitude']],
                            use_container_width=True,
                            height=400
                        )
                        
                        # Bouton téléchargement CSV
                        csv = df_plot.to_csv(index=False)
                        st.download_button(
                            label="⬇️ Télécharger CSV",
                            data=csv,
                            file_name=f"{pollutant_choice}_{address}_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
            else:
                st.warning("Aucune donnée disponible pour ce polluant")

    # ========== ONGLET 3: MÉTÉO DÉTAILLÉE ==========
    with tab3:
        if weather_db:
            st.subheader("☁️ Historique météo")

            df_weather = weather_db.get_all_data(limit=500)

            if not df_weather.empty:
                # Graphique température
                import plotly.graph_objects as go

                fig_temp = go.Figure()
                fig_temp.add_trace(go.Scatter(
                    x=df_weather['timestamp'],
                    y=df_weather['temperature'],
                    mode='lines',
                    name='Température',
                    line=dict(color='red', width=2)
                ))
                fig_temp.add_trace(go.Scatter(
                    x=df_weather['timestamp'],
                    y=df_weather['feels_like'],
                    mode='lines',
                    name='Ressenti',
                    line=dict(color='orange', width=1, dash='dash')
                ))

                fig_temp.update_layout(
                    title="Température",
                    xaxis_title="Date",
                    yaxis_title="°C",
                    hovermode='x unified'
                )

                st.plotly_chart(fig_temp, use_container_width=True)

                # Stats météo
                weather_summary = weather_db.get_summary()

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Temp. moyenne", f"{weather_summary.get('avg_temp')}°C")
                with col2:
                    st.metric("Temp. min", f"{weather_summary.get('min_temp')}°C")
                with col3:
                    st.metric("Temp. max", f"{weather_summary.get('max_temp')}°C")
                with col4:
                    st.metric("Précipitations", f"{weather_summary.get('total_precip', 0)}mm")

                # Données brutes
                if 'show_raw_data' in st.session_state and st.session_state.get('show_raw_data', False):
                    with st.expander("📋 Données brutes météo", expanded=False):
                        # Afficher colonnes principales
                        cols_to_show = ['timestamp', 'station_name', 'temperature', 'feels_like', 
                                       'humidity', 'wind_speed', 'wind_direction_text', 'pressure']
                        cols_available = [c for c in cols_to_show if c in df_weather.columns]
                        
                        st.dataframe(
                            df_weather[cols_available],
                            use_container_width=True,
                            height=400
                        )
                        
                        # Téléchargement CSV
                        csv_weather = df_weather.to_csv(index=False)
                        st.download_button(
                            label="⬇️ Télécharger CSV météo",
                            data=csv_weather,
                            file_name=f"meteo_{address}_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
            else:
                st.info("Aucune donnée météo historique")
        else:
            st.info("☁️ Météo non chargée pour cette adresse")

    # ========== ONGLET 4: COMPARAISON ==========
    # ========== ONGLET 4: COMPARAISON ==========
    with tab4:
     # Import du module comparaison
    
     # Affichage UI comparaison avancée
        show_comparison_ui(list(st.session_state.addresses.keys()))