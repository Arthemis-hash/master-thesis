#!/usr/bin/env python3
"""
Module de comparaison avancée multi-adresses
"""

import pandas as pd
import streamlit as st
from typing import Dict, List
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from db_utils import BrusselsAirQualityDB, WeatherDB


class AddressComparator:
    """Comparaison intelligente entre adresses"""
    
    def __init__(self, addresses: List[str]):
        self.addresses = addresses
        self.air_dbs = {addr: BrusselsAirQualityDB(addr, force_new=False) for addr in addresses}
        self.weather_dbs = {addr: WeatherDB(addr, force_new=False) for addr in addresses}
    
    def compare_air_quality(self) -> pd.DataFrame:
        """
        Comparaison qualité air entre adresses
        """
        comparison = []
        
        for addr in self.addresses:
            summary = self.air_dbs[addr].get_summary()
            
            if summary and summary.get('total_records', 0) > 0:
                comparison.append({
                    'Adresse': addr[:30] + '...' if len(addr) > 30 else addr,
                    'PM2.5 (µg/m³)': round(summary.get('avg_pm2_5', 0), 1),
                    'PM10 (µg/m³)': round(summary.get('avg_pm10', 0), 1),
                    'NO₂ (µg/m³)': round(summary.get('avg_no2', 0), 1),
                    'O₃ (µg/m³)': round(summary.get('avg_o3', 0), 1),
                    'Records': summary['total_records'],
                    'Stations': summary['num_stations']
                })
        
        return pd.DataFrame(comparison)
    
    def compare_weather(self) -> pd.DataFrame:
        """
        Comparaison météo entre adresses
        """
        comparison = []
        
        for addr in self.addresses:
            summary = self.weather_dbs[addr].get_summary()
            
            if summary and summary.get('total_records', 0) > 0:
                # Fonction helper pour arrondir seulement si non-None
                def safe_round(value, decimals=1):
                    return round(value, decimals) if value is not None else 0.0
                
                comparison.append({
                    'Adresse': addr[:30] + '...' if len(addr) > 30 else addr,
                    'Temp. moy (°C)': safe_round(summary.get('avg_temp')),
                    'Temp. min (°C)': safe_round(summary.get('min_temp')),
                    'Temp. max (°C)': safe_round(summary.get('max_temp')),
                    'Vent moy (km/h)': safe_round(summary.get('avg_wind')),
                    'Humidité (%)': safe_round(summary.get('avg_humidity')),
                    'Records': summary['total_records']
                })
        
        return pd.DataFrame(comparison)
    
    def plot_pollutant_comparison(self, pollutant: str) -> go.Figure:
        """
        Graphique comparatif évolution temporelle d'un polluant
        """
        fig = go.Figure()
        
        for addr in self.addresses:
            df = self.air_dbs[addr].get_pollutant_data(pollutant)
            
            if not df.empty:
                # Agréger par jour pour lisibilité
                df_daily = df.set_index('timestamp').resample('D')['value'].mean().reset_index()
                
                fig.add_trace(go.Scatter(
                    x=df_daily['timestamp'],
                    y=df_daily['value'],
                    mode='lines+markers',
                    name=addr[:20] + '...' if len(addr) > 20 else addr,
                    line=dict(width=2),
                    marker=dict(size=4)
                ))
        
        fig.update_layout(
            title=f"Comparaison {pollutant.upper()} - Moyenne journalière",
            xaxis_title="Date",
            yaxis_title="Concentration (µg/m³)",
            hovermode='x unified',
            template='plotly_white',
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )
        
        return fig
    
    def plot_radar_comparison(self) -> go.Figure:
        """
        Radar chart normalisé multi-adresses
        """
        fig = go.Figure()
        
        for addr in self.addresses:
            summary = self.air_dbs[addr].get_summary()
            
            if not summary or summary.get('total_records', 0) == 0:
                continue
            
            # Normalisation 0-100 (100 = meilleur)
            scores = {
                'PM2.5': max(0, 100 - (summary.get('avg_pm2_5', 0) / 75 * 100)),
                'PM10': max(0, 100 - (summary.get('avg_pm10', 0) / 150 * 100)),
                'NO₂': max(0, 100 - (summary.get('avg_no2', 0) / 340 * 100)),
                'O₃': max(0, 100 - (summary.get('avg_o3', 0) / 380 * 100))
            }
            
            fig.add_trace(go.Scatterpolar(
                r=list(scores.values()),
                theta=list(scores.keys()),
                fill='toself',
                name=addr[:20] + '...' if len(addr) > 20 else addr
            ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    ticksuffix='',
                    tickmode='linear',
                    tick0=0,
                    dtick=20
                )
            ),
            showlegend=True,
            title="Score qualité air normalisé (100 = excellent)"
        )
        
        return fig
    
    def plot_temperature_comparison(self) -> go.Figure:
        """
        Graphique comparatif température
        """
        fig = go.Figure()
        
        for addr in self.addresses:
            df = self.weather_dbs[addr].get_all_data(limit=500)
            
            if not df.empty:
                # Agréger par jour
                df_daily = df.set_index('timestamp').resample('D')['temperature'].mean().reset_index()
                
                fig.add_trace(go.Scatter(
                    x=df_daily['timestamp'],
                    y=df_daily['temperature'],
                    mode='lines',
                    name=addr[:20] + '...' if len(addr) > 20 else addr,
                    line=dict(width=2)
                ))
        
        fig.update_layout(
            title="Comparaison température - Moyenne journalière",
            xaxis_title="Date",
            yaxis_title="Température (°C)",
            hovermode='x unified',
            template='plotly_white'
        )
        
        return fig
    
    def get_ranking(self) -> Dict[str, List[tuple]]:
        """
        Classement adresses par critère
        Retourne dict {critère: [(adresse, valeur), ...]}
        """
        rankings = {
            'PM2.5': [],
            'PM10': [],
            'NO₂': [],
            'O₃': [],
            'Température': []
        }
        
        # Qualité air
        for addr in self.addresses:
            summary = self.air_dbs[addr].get_summary()
            
            if summary and summary.get('total_records', 0) > 0:
                rankings['PM2.5'].append((addr, summary.get('avg_pm2_5', float('inf'))))
                rankings['PM10'].append((addr, summary.get('avg_pm10', float('inf'))))
                rankings['NO₂'].append((addr, summary.get('avg_no2', float('inf'))))
                rankings['O₃'].append((addr, summary.get('avg_o3', float('inf'))))
        
        # Météo
        for addr in self.addresses:
            summary = self.weather_dbs[addr].get_summary()
            
            if summary and summary.get('total_records', 0) > 0:
                rankings['Température'].append((addr, summary.get('avg_temp', 0)))
        
        # Trier (du meilleur au pire)
        for key in ['PM2.5', 'PM10', 'NO₂']:
            rankings[key].sort(key=lambda x: x[1])  # Croissant = meilleur
        
        rankings['O₃'].sort(key=lambda x: abs(x[1] - 100))  # Proche de 100 = meilleur
        rankings['Température'].sort(key=lambda x: abs(x[1] - 20))  # Proche de 20°C
        
        return rankings


def show_comparison_ui(addresses: List[str]):
    """
    Interface Streamlit comparaison multi-adresses
    """
    st.subheader("⚖️ Comparaison Multi-Adresses")
    
    # Section d'ajout rapide d'adresses
    with st.expander("➕ Ajouter une adresse à comparer", expanded=len(addresses) < 2):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            new_address = st.text_input(
                "Adresse à ajouter",
                placeholder="Ex: Place de la Monnaie, Bruxelles",
                key="quick_add_address"
            )
        
        with col2:
            st.write("")  # Espacement
            st.write("")  # Espacement
            if st.button("➕ Ajouter", type="primary", use_container_width=True):
                if new_address:
                    # Géocoder l'adresse
                    from geopy.geocoders import Nominatim
                    try:
                        geolocator = Nominatim(user_agent="air_quality_app")
                        location = geolocator.geocode(new_address, timeout=10)
                        
                        if location:
                            # Ajouter à session_state
                            if 'addresses' not in st.session_state:
                                st.session_state.addresses = {}
                            
                            if new_address not in st.session_state.addresses:
                                st.session_state.addresses[new_address] = {
                                    'lat': location.latitude,
                                    'lon': location.longitude
                                }
                                st.success(f"✅ Adresse ajoutée : {new_address}")
                                st.rerun()
                            else:
                                st.warning("⚠️ Cette adresse est déjà dans la liste")
                        else:
                            st.error("❌ Adresse non trouvée")
                    except Exception as e:
                        st.error(f"❌ Erreur : {e}")
                else:
                    st.warning("⚠️ Veuillez entrer une adresse")
    
    # Vérifier le nombre d'adresses
    if len(addresses) < 2:
        st.info("ℹ️ Ajoutez au moins 2 adresses pour activer la comparaison")
        return
    
    comparator = AddressComparator(addresses)
    
    st.markdown(f"**{len(addresses)} adresses** en comparaison")
    
    # Onglets comparaison
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Tableaux",
        "📈 Évolution",
        "🎯 Radar",
        "🏆 Classements"
    ])
    
    # ========== TAB 1: TABLEAUX ==========
    with tab1:
        st.markdown("### Qualité de l'air")
        df_air = comparator.compare_air_quality()
        
        if not df_air.empty:
            st.dataframe(
                df_air.style.background_gradient(
                    subset=['PM2.5 (µg/m³)', 'PM10 (µg/m³)', 'NO₂ (µg/m³)'],
                    cmap='RdYlGn_r'
                ),
                use_container_width=True
            )
        else:
            st.warning("Aucune donnée qualité air disponible")
        
        st.markdown("### Météo")
        df_weather = comparator.compare_weather()
        
        if not df_weather.empty:
            st.dataframe(df_weather, use_container_width=True)
        else:
            st.warning("Aucune donnée météo disponible")
    
    # ========== TAB 2: ÉVOLUTION ==========
    with tab2:
        pollutant = st.selectbox(
            "Choisir un polluant",
            ['pm2_5', 'pm10', 'no2', 'o3'],
            key='compare_pollutant'
        )
        
        fig_evolution = comparator.plot_pollutant_comparison(pollutant)
        st.plotly_chart(fig_evolution, use_container_width=True)
        
        st.markdown("### Température")
        fig_temp = comparator.plot_temperature_comparison()
        st.plotly_chart(fig_temp, use_container_width=True)
    
    # ========== TAB 3: RADAR ==========
    with tab3:
        fig_radar = comparator.plot_radar_comparison()
        st.plotly_chart(fig_radar, use_container_width=True)
        
        st.info("""
        **Interprétation**: Plus la surface est grande et proche du bord extérieur, 
        meilleure est la qualité de l'air. Un score de 100 représente une qualité excellente.
        """)
    
    # ========== TAB 4: CLASSEMENTS ==========
    with tab4:
        rankings = comparator.get_ranking()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🥇 Meilleure qualité PM2.5")
            for i, (addr, val) in enumerate(rankings['PM2.5'][:3], 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
                st.write(f"{emoji} {addr[:30]}: **{val:.1f} µg/m³**")
        
        with col2:
            st.markdown("### 🥇 Meilleure qualité NO₂")
            for i, (addr, val) in enumerate(rankings['NO₂'][:3], 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
                st.write(f"{emoji} {addr[:30]}: **{val:.1f} µg/m³**")