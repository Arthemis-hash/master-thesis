#!/usr/bin/env python3
"""
Module UI pour la section Météo
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import logging
from datetime import datetime, timedelta

from db_async_wrapper import WeatherDB
from download_weather import WeatherDownloader

logger = logging.getLogger(__name__)


def download_weather_data(address: str, lat: float, lon: float) -> bool:
    """
    Télécharge données météo historiques (16 derniers jours)
    Utilise le nouveau système multi-adresses
    Returns: True si succès
    """
    try:
        # Utiliser le nouveau système avec adresse
        downloader = WeatherDownloader(address=address, force_new=False)

        end_date = datetime.now()
        start_date = end_date - timedelta(days=16)

        with st.spinner("🌤️ Téléchargement météo (16 jours)..."):
            success = downloader.download_and_save_historical(
                address=address,
                lat=lat,
                lon=lon,
                start_date=start_date,
                end_date=end_date
            )

        if success:
            logger.info(f"Meteo téléchargée: {address} -> {downloader.db.db_path}")
            st.success(f"✅ Données météo sauvegardées: {downloader.db.db_path}")
        else:
            logger.warning(f"⚠️ Échec météo: {address}")
            st.warning("⚠️ Données météo partiellement disponibles")

        return success

    except Exception as e:
        logger.error(f"❌ Erreur météo: {e}")
        st.warning("⚠️ Module météo temporairement indisponible")
        return False


@st.cache_data(ttl=600)  # Cache 10 minutes
def create_temperature_chart(df: pd.DataFrame) -> plt.Figure:
    """Graphique température sur 16 jours"""
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(df['date'], df['temperature'],
            label='Température réelle', color='#FF6B6B', linewidth=2.5)

    # Vérifier si la colonne 'feels_like' existe
    if 'feels_like' in df.columns:
        ax.plot(df['date'], df['feels_like'],
                label='Température ressentie', color='#FFA07A',
                linewidth=1.5, linestyle='--', alpha=0.7)

    ax.fill_between(df['date'], df['temperature'], alpha=0.15, color='#FF6B6B')

    ax.set_xlabel('Date', fontsize=12, fontweight='bold')
    ax.set_ylabel('Température (°C)', fontsize=12, fontweight='bold')
    ax.set_title('Évolution de la température (16 derniers jours)',
                 fontsize=14, fontweight='bold', pad=20)
    ax.legend(loc='best', frameon=True, shadow=True)
    ax.grid(True, alpha=0.3, linestyle='--')

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    return fig


@st.cache_data(ttl=600)  # Cache 10 minutes
def create_precipitation_wind_chart(df: pd.DataFrame) -> plt.Figure:
    """Graphique précipitations + vent"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # === PRÉCIPITATIONS ===
    has_precipitation = False
    
    # Pluie
    if 'rain' in df.columns and df['rain'].notna().any():
        rain_data = df['rain'].fillna(0)
        if rain_data.sum() > 0:
            ax1.bar(df['date'], rain_data,
                    color='#4ECDC4', alpha=0.7, label='Pluie', edgecolor='#3BBCB4', linewidth=0.5)
            has_precipitation = True
    
    # Neige
    if 'snowfall' in df.columns and df['snowfall'].notna().any():
        snow_data = df['snowfall'].fillna(0)
        if snow_data.sum() > 0:
            ax1.bar(df['date'], snow_data,
                    color='#A8E6CF', alpha=0.7, label='Neige', 
                    edgecolor='#88D6AF', linewidth=0.5, bottom=rain_data if has_precipitation else 0)
            has_precipitation = True
    
    # Si pas de précipitations, afficher un message
    if not has_precipitation:
        ax1.text(0.5, 0.5, 'Aucune précipitation sur la période',
                ha='center', va='center', transform=ax1.transAxes,
                fontsize=12, color='gray', style='italic')
        ax1.set_ylim(0, 1)
    
    ax1.set_ylabel('Précipitations (mm)', fontsize=11, fontweight='bold')
    ax1.set_title('Précipitations (16 derniers jours)', fontsize=13, fontweight='bold', pad=10)
    if has_precipitation:
        ax1.legend(loc='best', frameon=True, shadow=True)
    ax1.grid(True, alpha=0.3, linestyle='--')

    # === VENT ===
    if 'wind_speed' in df.columns:
        # Filtrer les valeurs nulles
        wind_data = df[df['wind_speed'].notna()].copy()
        
        if not wind_data.empty:
            # Vitesse du vent
            ax2.plot(wind_data['date'], wind_data['wind_speed'],
                     label='Vitesse vent', color='#95E1D3', linewidth=2.5, 
                     marker='o', markersize=3, markerfacecolor='#7FD1C3', 
                     markeredgecolor='white', markeredgewidth=0.5)
            
            # Remplissage sous la courbe
            ax2.fill_between(wind_data['date'], wind_data['wind_speed'], 
                            alpha=0.2, color='#95E1D3')
            
            # Rafales
            if 'wind_gusts' in df.columns and df['wind_gusts'].notna().any():
                gusts_data = df[df['wind_gusts'].notna()].copy()
                if not gusts_data.empty:
                    ax2.plot(gusts_data['date'], gusts_data['wind_gusts'],
                             label='Rafales', color='#FF6B9D', linewidth=2,
                             linestyle='--', alpha=0.8, marker='x', markersize=4)
        else:
            ax2.text(0.5, 0.5, 'Données de vent non disponibles',
                    ha='center', va='center', transform=ax2.transAxes,
                    fontsize=12, color='gray', style='italic')
            ax2.set_ylim(0, 1)
    
    ax2.set_xlabel('Date', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Vitesse (km/h)', fontsize=11, fontweight='bold')
    ax2.set_title('Vent (16 derniers jours)', fontsize=13, fontweight='bold', pad=10)
    ax2.legend(loc='best', frameon=True, shadow=True)
    ax2.grid(True, alpha=0.3, linestyle='--')

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    return fig


def display_weather_section(address: str, lat: float, lon: float):
    """
    Section météo complète dans Streamlit
    Affiche stats + graphiques sur 16 derniers jours
    """
    st.header("🌤️ Données Météorologiques")

    # Utiliser PostgreSQL pour récupérer les données météo
    try:
        weather_db = WeatherDB(address=address)
        weather_data = weather_db.get_hourly_forecast(address, hours=16*24)

    except Exception as e:
        logger.error(f"❌ Erreur lecture météo: {e}")
        st.warning("📦 Données météo non disponibles")
        if st.button("🔄 Télécharger les données météo (16 jours)", type="primary"):
            download_weather_data(address, lat, lon)
            st.rerun()
        return

    # Vérifier si données disponibles
    if weather_data is None or weather_data.empty:
        st.warning("🔭 Aucune donnée météo pour cette adresse")
        if st.button("🔄 Télécharger maintenant", type="primary"):
            download_weather_data(address, lat, lon)
            st.rerun()
        return

    # Convertir date en datetime si nécessaire
    if not pd.api.types.is_datetime64_any_dtype(weather_data['date']):
        weather_data['date'] = pd.to_datetime(weather_data['date'])

    # === MÉTRIQUES ===
    st.subheader("📊 Résumé des 16 derniers jours")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_temp = weather_data['temperature'].mean()
        min_temp = weather_data['temperature'].min()
        max_temp = weather_data['temperature'].max()
        st.metric("🌡️ Température",
                  f"{avg_temp:.1f}°C",
                  delta=f"Min: {min_temp:.1f}°C | Max: {max_temp:.1f}°C")

    with col2:
        total_rain = weather_data['rain'].sum() if 'rain' in weather_data else 0
        st.metric("🌧️ Précipitations", f"{total_rain:.1f} mm")

    with col3:
        avg_wind = weather_data['wind_speed'].mean()
        max_wind = weather_data['wind_speed'].max()
        st.metric("💨 Vent moyen",
                  f"{avg_wind:.1f} km/h",
                  delta=f"Max: {max_wind:.1f} km/h")

    with col4:
        if 'humidity' in weather_data.columns:
            avg_humidity = weather_data['humidity'].mean()
            st.metric("💧 Humidité", f"{avg_humidity:.0f}%")
        else:
            st.metric("💧 Humidité", "N/A")

    st.divider()

    # === GRAPHIQUES ===
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🌡️ Température")
        fig_temp = create_temperature_chart(weather_data)
        st.pyplot(fig_temp)
        plt.close(fig_temp)

    with col_right:
        st.subheader("🌧️ Précipitations & Vent")
        fig_precip = create_precipitation_wind_chart(weather_data)
        st.pyplot(fig_precip)
        plt.close(fig_precip)

    # === TABLEAU DÉTAILLÉ ===
    with st.expander("📋 Voir les données détaillées (agrégées par jour)"):
        # Grouper par jour
        weather_data['day'] = weather_data['date'].dt.date

        daily_agg = weather_data.groupby('day').agg({
            'temperature': ['mean', 'min', 'max'],
            'rain': 'sum',
            'wind_speed': 'mean',
            'humidity': 'mean'
        }).round(1)

        daily_agg.columns = ['T° Moy (°C)', 'T° Min (°C)', 'T° Max (°C)',
                             'Pluie (mm)', 'Vent (km/h)', 'Humidité (%)']
        daily_agg.index.name = 'Date'

        st.dataframe(daily_agg, width="stretch")

        # Export CSV
        csv = weather_data.to_csv(index=False)
        st.download_button(
            label="📥 Télécharger CSV complet (horaire)",
            data=csv,
            file_name=f"meteo_{address.replace(' ', '_')}.csv",
            mime="text/csv"
        )
