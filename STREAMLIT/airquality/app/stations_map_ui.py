#!/usr/bin/env python3
"""
============================================================
INTERFACE STATIONS - Visualisation des stations de mesure
============================================================
Carte interactive affichant toutes les stations de qualité
de l'air et météorologiques avec leurs informations.
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from typing import Optional, List, Dict
import logging
from datetime import datetime

from db_async_wrapper import StationManager

logger = logging.getLogger(__name__)


def get_station_icon_color(station: Dict) -> str:
    """
    Détermine la couleur de l'icône en fonction du type de station

    Args:
        station: Dictionnaire contenant les infos de la station

    Returns:
        Couleur pour l'icône Folium
    """
    if station['station_type'] == 'air_quality':
        if station.get('last_measurement'):
            return 'blue'  # Station active
        return 'lightblue'  # Station sans données récentes
    elif station['station_type'] == 'weather':
        if station.get('last_measurement'):
            return 'green'  # Station active
        return 'lightgreen'  # Station sans données récentes
    return 'gray'


def get_station_icon(station: Dict) -> str:
    """
    Détermine l'icône en fonction du type de station

    Args:
        station: Dictionnaire contenant les infos de la station

    Returns:
        Nom de l'icône Font Awesome
    """
    if station['station_type'] == 'air_quality':
        return 'wind'
    elif station['station_type'] == 'weather':
        return 'cloud'
    return 'info-sign'


def create_station_popup_html(station: Dict) -> str:
    """
    Crée le contenu HTML du popup de la station

    Args:
        station: Dictionnaire contenant les infos de la station

    Returns:
        HTML formaté pour le popup
    """
    station_type_label = {
        'air_quality': '🌬️ Qualité de l\'air',
        'weather': '🌤️ Météo'
    }.get(station['station_type'], '📍 Station')

    last_measurement = station.get('last_measurement')
    if last_measurement:
        if isinstance(last_measurement, str):
            last_measurement = datetime.fromisoformat(last_measurement)
        last_measurement_str = last_measurement.strftime('%d/%m/%Y %H:%M')
    else:
        last_measurement_str = 'Aucune mesure'

    html = f"""
    <div style="font-family: Arial, sans-serif; min-width: 250px;">
        <h4 style="margin: 0 0 10px 0; color: #2c3e50;">
            {station_type_label}
        </h4>
        <table style="width: 100%; font-size: 13px;">
            <tr>
                <td style="font-weight: bold; padding: 3px;">Station:</td>
                <td style="padding: 3px;">{station['station_name']}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; padding: 3px;">Code:</td>
                <td style="padding: 3px; font-family: monospace;">{station['station_code']}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; padding: 3px;">Latitude:</td>
                <td style="padding: 3px;">{station['latitude']:.6f}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; padding: 3px;">Longitude:</td>
                <td style="padding: 3px;">{station['longitude']:.6f}</td>
            </tr>
    """

    if station.get('elevation'):
        html += f"""
            <tr>
                <td style="font-weight: bold; padding: 3px;">Altitude:</td>
                <td style="padding: 3px;">{station['elevation']}m</td>
            </tr>
        """

    html += f"""
            <tr>
                <td style="font-weight: bold; padding: 3px;">Statut:</td>
                <td style="padding: 3px;">
                    <span style="color: {'green' if station['is_active'] else 'red'};">
                        {'✓ Active' if station['is_active'] else '✗ Inactive'}
                    </span>
                </td>
            </tr>
            <tr>
                <td style="font-weight: bold; padding: 3px;">Dernière mesure:</td>
                <td style="padding: 3px;">{last_measurement_str}</td>
            </tr>
    """

    if station['station_type'] == 'air_quality':
        html += f"""
            <tr>
                <td style="font-weight: bold; padding: 3px;">Mesures air:</td>
                <td style="padding: 3px;">{station.get('air_quality_records', 0):,}</td>
            </tr>
        """
    else:
        html += f"""
            <tr>
                <td style="font-weight: bold; padding: 3px;">Mesures météo:</td>
                <td style="padding: 3px;">{station.get('weather_records', 0):,}</td>
            </tr>
        """

    html += """
        </table>
    </div>
    """

    return html


def create_stations_map(
    stations: List[Dict],
    center_lat: float = 50.8503,
    center_lon: float = 4.3517,
    zoom_start: int = 10,
    highlight_station: Optional[str] = None
) -> folium.Map:
    """
    Crée une carte Folium avec toutes les stations

    Args:
        stations: Liste des stations à afficher
        center_lat: Latitude du centre de la carte
        center_lon: Longitude du centre de la carte
        zoom_start: Niveau de zoom initial
        highlight_station: Code de la station à mettre en évidence

    Returns:
        Carte Folium
    """
    # Créer la carte de base
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles='OpenStreetMap'
    )

    # Ajouter les tuiles alternatives
    folium.TileLayer('CartoDB positron', name='CartoDB Positron').add_to(m)
    folium.TileLayer('CartoDB dark_matter', name='CartoDB Dark').add_to(m)

    # Créer des groupes de marqueurs par type
    air_quality_group = folium.FeatureGroup(name='🌬️ Stations Qualité de l\'air')
    weather_group = folium.FeatureGroup(name='🌤️ Stations Météo')

    for station in stations:
        color = get_station_icon_color(station)
        icon_name = get_station_icon(station)

        # Mettre en évidence la station sélectionnée
        if highlight_station and station['station_code'] == highlight_station:
            color = 'red'
            icon_name = 'star'

        popup_html = create_station_popup_html(station)

        marker = folium.Marker(
            location=[station['latitude'], station['longitude']],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{station['station_name']} ({station['station_code']})",
            icon=folium.Icon(color=color, icon=icon_name, prefix='fa')
        )

        # Ajouter au bon groupe
        if station['station_type'] == 'air_quality':
            marker.add_to(air_quality_group)
        else:
            marker.add_to(weather_group)

    # Ajouter les groupes à la carte
    air_quality_group.add_to(m)
    weather_group.add_to(m)

    # Ajouter le contrôle des couches
    folium.LayerControl().add_to(m)

    # Ajouter échelle
    folium.plugins.MeasureControl(position='bottomleft').add_to(m)

    return m


def display_stations_map_ui(current_location: Optional[Dict] = None):
    """
    Affiche l'interface de visualisation des stations

    Args:
        current_location: Dictionnaire avec 'latitude', 'longitude' et 'address' optionnels
                         pour centrer la carte sur une position spécifique
    """
    st.header("🗺️ Carte des Stations de Mesure")

    # Initialiser le gestionnaire de stations
    station_mgr = StationManager()

    # Paramètres de filtrage dans la sidebar
    with st.sidebar:
        st.subheader("🔧 Filtres de Visualisation")

        station_type_filter = st.selectbox(
            "Type de stations",
            ["Toutes", "Qualité de l'air", "Météo"],
            key="station_type_filter"
        )

        active_only = st.checkbox("Stations actives uniquement", value=True, key="active_only")

        # Recherche de stations à proximité
        if current_location and 'latitude' in current_location and 'longitude' in current_location:
            st.divider()
            st.subheader("📍 Stations à proximité")

            show_nearby = st.checkbox("Afficher uniquement les stations proches", value=False)

            if show_nearby:
                radius_km = st.slider(
                    "Rayon de recherche (km)",
                    min_value=1.0,
                    max_value=50.0,
                    value=10.0,
                    step=1.0
                )

    # Conversion du filtre de type
    station_type = None
    if station_type_filter == "Qualité de l'air":
        station_type = "air_quality"
    elif station_type_filter == "Météo":
        station_type = "weather"

    # Récupérer les stations
    try:
        with st.spinner("📥 Chargement des stations..."):
            if current_location and show_nearby if 'show_nearby' in locals() else False:
                stations = station_mgr.get_stations_near_location(
                    latitude=current_location['latitude'],
                    longitude=current_location['longitude'],
                    radius_km=radius_km if 'radius_km' in locals() else 10.0,
                    station_type=station_type
                )
            else:
                stations = station_mgr.get_all_stations(
                    station_type=station_type,
                    active_only=active_only
                )

        if not stations:
            st.warning("⚠️ Aucune station trouvée avec les filtres sélectionnés.")
            return

        # Statistiques rapides
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Stations", len(stations))

        with col2:
            air_stations = [s for s in stations if s['station_type'] == 'air_quality']
            st.metric("Qualité de l'air", len(air_stations))

        with col3:
            weather_stations = [s for s in stations if s['station_type'] == 'weather']
            st.metric("Météo", len(weather_stations))

        with col4:
            active_stations = [s for s in stations if s['is_active']]
            st.metric("Actives", len(active_stations))

        # Déterminer le centre de la carte
        if current_location and 'latitude' in current_location:
            center_lat = current_location['latitude']
            center_lon = current_location['longitude']
            zoom = 12
        else:
            # Centrer sur la moyenne des positions des stations
            center_lat = sum(s['latitude'] for s in stations) / len(stations)
            center_lon = sum(s['longitude'] for s in stations) / len(stations)
            zoom = 10

        # Créer et afficher la carte
        st.subheader("🗺️ Carte Interactive")

        stations_map = create_stations_map(
            stations=stations,
            center_lat=center_lat,
            center_lon=center_lon,
            zoom_start=zoom
        )

        # Afficher la carte
        st_folium(stations_map, width=1000, height=600)

        # Table des stations
        st.subheader("📋 Liste des Stations")

        # Préparer le DataFrame
        df_data = []
        for station in stations:
            df_data.append({
                'Code': station['station_code'],
                'Nom': station['station_name'],
                'Type': '🌬️ Air' if station['station_type'] == 'air_quality' else '🌤️ Météo',
                'Latitude': f"{station['latitude']:.6f}",
                'Longitude': f"{station['longitude']:.6f}",
                'Altitude (m)': station.get('elevation', '-'),
                'Statut': '✓ Active' if station['is_active'] else '✗ Inactive',
                'Mesures': station.get('air_quality_records', 0) + station.get('weather_records', 0),
                'Distance (km)': f"{station['distance_km']:.2f}" if 'distance_km' in station else '-'
            })

        df = pd.DataFrame(df_data)

        # Filtres de recherche dans le tableau
        search_query = st.text_input("🔍 Rechercher une station", "")

        if search_query:
            df = df[
                df['Code'].str.contains(search_query, case=False, na=False) |
                df['Nom'].str.contains(search_query, case=False, na=False)
            ]

        # Afficher le tableau
        st.dataframe(
            df,
            width="stretch",
            hide_index=True
        )

        # Bouton d'export
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger la liste (CSV)",
            data=csv,
            file_name=f"stations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement des stations: {e}")
        st.error(f"Erreur lors du chargement des stations: {e}")

        import traceback
        with st.expander("🔍 Détails de l'erreur"):
            st.code(traceback.format_exc())


def display_station_details(station_code: str):
    """
    Affiche les détails d'une station spécifique

    Args:
        station_code: Code de la station
    """
    station_mgr = StationManager()

    try:
        station = station_mgr.get_station_by_code(station_code)

        if not station:
            st.error(f"❌ Station '{station_code}' non trouvée")
            return

        st.header(f"📊 {station['station_name']}")

        # Informations générales
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("ℹ️ Informations")
            st.write(f"**Code:** `{station['station_code']}`")
            st.write(f"**Type:** {station['station_type']}")
            st.write(f"**Statut:** {'✓ Active' if station['is_active'] else '✗ Inactive'}")
            st.write(f"**Latitude:** {station['latitude']:.6f}")
            st.write(f"**Longitude:** {station['longitude']:.6f}")
            if station.get('elevation'):
                st.write(f"**Altitude:** {station['elevation']}m")

        with col2:
            st.subheader("📈 Statistiques")
            st.metric("Mesures qualité de l'air", f"{station.get('air_quality_records', 0):,}")
            st.metric("Mesures météo", f"{station.get('weather_records', 0):,}")

            if station.get('last_measurement'):
                last = station['last_measurement']
                if isinstance(last, str):
                    last = datetime.fromisoformat(last)
                st.write(f"**Dernière mesure:** {last.strftime('%d/%m/%Y %H:%M')}")

        # Métadonnées
        if station.get('metadata'):
            with st.expander("🔍 Métadonnées"):
                st.json(station['metadata'])

        # Carte de localisation
        st.subheader("📍 Localisation")
        station_map = create_stations_map(
            stations=[station],
            center_lat=station['latitude'],
            center_lon=station['longitude'],
            zoom_start=14,
            highlight_station=station_code
        )
        st_folium(station_map, width=700, height=400)

    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement de la station: {e}")
        st.error(f"Erreur: {e}")
