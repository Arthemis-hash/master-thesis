#!/usr/bin/env python3
"""
Module de comparaison avancée multi-adresses - Version améliorée UI
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Optional
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import io

from db_utils import BrusselsAirQualityDB, WeatherDB


class AddressComparator:
    """Comparaison intelligente entre adresses avec UI améliorée"""
    
    def __init__(self, addresses: List[str], addresses_coords: Optional[Dict] = None):
        self.addresses = addresses
        self.addresses_coords = addresses_coords or {}
        self.air_dbs = {addr: BrusselsAirQualityDB(addr, force_new=False) for addr in addresses}
        self.weather_dbs = {addr: WeatherDB(addr, force_new=False) for addr in addresses}
        self.colors = ['red', 'blue', 'green', 'purple', 'orange', 'pink', 'darkred', 'lightblue']
    
    def create_comparison_map(self) -> Optional[folium.Map]:
        """Crée une carte avec toutes les adresses comparées"""
        if not self.addresses_coords:
            return None
        
        lats = [coords['lat'] for coords in self.addresses_coords.values()]
        lons = [coords['lon'] for coords in self.addresses_coords.values()]
        center_lat, center_lon = sum(lats) / len(lats), sum(lons) / len(lons)
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="OpenStreetMap")
        
        for idx, (addr, coords) in enumerate(self.addresses_coords.items()):
            summary = self.air_dbs[addr].get_summary()
            pm25 = summary.get('avg_pm2_5') if summary else None
            pm10 = summary.get('avg_pm10') if summary else None
            no2 = summary.get('avg_no2') if summary else None
            
            # Convertir None en 0 pour l'affichage
            pm25_val = pm25 if pm25 is not None else 0.0
            pm10_val = pm10 if pm10 is not None else 0.0
            no2_val = no2 if no2 is not None else 0.0
            
            color = self.colors[idx % len(self.colors)]
            
            popup_html = f"""<div style="font-family: Arial; width: 250px;">
                <h4 style="color: {color};">📍 Adresse {idx + 1}</h4>
                <p><b>{addr[:50]}</b></p><hr>
                <p><b>Qualité Air:</b></p>
                <p>PM2.5: <b>{pm25_val:.1f}</b> µg/m³</p>
                <p>PM10: <b>{pm10_val:.1f}</b> µg/m³</p>
                <p>NO₂: <b>{no2_val:.1f}</b> µg/m³</p>
                </div>"""
            
            folium.Marker(
                [coords['lat'], coords['lon']],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"Adresse {idx + 1}: {addr[:30]}...",
                icon=folium.Icon(color=color, icon='home', prefix='fa')
            ).add_to(m)
        
        return m
    
    def export_to_excel(self) -> io.BytesIO:
        """Exporter toutes les données de comparaison vers Excel"""
        try:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_air = self.compare_air_quality()
                if not df_air.empty:
                    df_air.to_excel(writer, sheet_name='Qualité Air', index=False)
                df_weather = self.compare_weather()
                if not df_weather.empty:
                    df_weather.to_excel(writer, sheet_name='Météo', index=False)
            output.seek(0)
            return output
        except ImportError as e:
            # Si openpyxl n'est pas installé, créer un fichier CSV zippé en alternative
            import zipfile
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zipf:
                df_air = self.compare_air_quality()
                if not df_air.empty:
                    zipf.writestr('qualite_air.csv', df_air.to_csv(index=False, encoding='utf-8-sig'))
                df_weather = self.compare_weather()
                if not df_weather.empty:
                    zipf.writestr('meteo.csv', df_weather.to_csv(index=False, encoding='utf-8-sig'))
            output.seek(0)
            return output
    
    def compare_air_quality(self) -> pd.DataFrame:
        """Comparaison qualité air entre adresses"""
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
                    'Mesures': summary['total_records'],
                    'Stations': summary['num_stations']
                })
        
        return pd.DataFrame(comparison)
    
    def compare_weather(self) -> pd.DataFrame:
        """Comparaison météo entre adresses"""
        comparison = []
        
        for addr in self.addresses:
            summary = self.weather_dbs[addr].get_summary()
            
            if summary and summary.get('total_records', 0) > 0:
                def safe_round(value, decimals=1):
                    return round(value, decimals) if value is not None else 0.0
                
                comparison.append({
                    'Adresse': addr[:30] + '...' if len(addr) > 30 else addr,
                    'Temp. moy (°C)': safe_round(summary.get('avg_temp')),
                    'Temp. min (°C)': safe_round(summary.get('min_temp')),
                    'Temp. max (°C)': safe_round(summary.get('max_temp')),
                    'Vent moy (km/h)': safe_round(summary.get('avg_wind')),
                    'Humidité (%)': safe_round(summary.get('avg_humidity')),
                    'Mesures': summary['total_records']
                })
        
        return pd.DataFrame(comparison)
    
    def plot_pollutant_comparison(self, pollutant: str) -> go.Figure:
        """Graphique comparatif évolution temporelle d'un polluant"""
        fig = go.Figure()
        
        for idx, addr in enumerate(self.addresses):
            df = self.air_dbs[addr].get_pollutant_data(pollutant)
            
            if not df.empty:
                df_daily = df.set_index('timestamp').resample('D')['value'].mean().reset_index()
                
                fig.add_trace(go.Scatter(
                    x=df_daily['timestamp'],
                    y=df_daily['value'],
                    mode='lines+markers',
                    name=f"Adresse {idx+1}: {addr[:20]}...",
                    line=dict(width=2),
                    marker=dict(size=4),
                    visible=True
                ))
        
        fig.update_layout(
            title=f"Comparaison {pollutant.upper()} - Évolution journalière",
            xaxis_title="Date",
            yaxis_title="Concentration (µg/m³)",
            hovermode='x unified',
            template='plotly_white',
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
            height=500
        )
        
        return fig
    
    def plot_radar_comparison(self) -> go.Figure:
        """Radar chart normalisé multi-adresses"""
        fig = go.Figure()
        
        for idx, addr in enumerate(self.addresses):
            summary = self.air_dbs[addr].get_summary()
            
            if not summary or summary.get('total_records', 0) == 0:
                continue
            
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
                name=f"Adresse {idx+1}"
            ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], ticksuffix='', tickmode='linear', tick0=0, dtick=20)
            ),
            showlegend=True,
            title="Score qualité air normalisé (100 = excellent)",
            height=500
        )
        
        return fig
    
    def plot_temperature_comparison(self) -> go.Figure:
        """Graphique comparatif température"""
        fig = go.Figure()
        
        for idx, addr in enumerate(self.addresses):
            df = self.weather_dbs[addr].get_all_data(limit=500)
            
            if not df.empty:
                df_daily = df.set_index('timestamp').resample('D')['temperature'].mean().reset_index()
                
                fig.add_trace(go.Scatter(
                    x=df_daily['timestamp'],
                    y=df_daily['temperature'],
                    mode='lines',
                    name=f"Adresse {idx+1}: {addr[:20]}...",
                    line=dict(width=2)
                ))
        
        fig.update_layout(
            title="Comparaison température - Moyenne journalière",
            xaxis_title="Date",
            yaxis_title="Température (°C)",
            hovermode='x unified',
            template='plotly_white',
            height=500
        )
        
        return fig
    
    def get_ranking(self) -> Dict[str, List[tuple]]:
        """Classement adresses par critère"""
        rankings = {
            'PM2.5': [],
            'PM10': [],
            'NO₂': [],
            'O₃': [],
            'Température': []
        }
        
        for addr in self.addresses:
            summary = self.air_dbs[addr].get_summary()
            
            if summary and summary.get('total_records', 0) > 0:
                rankings['PM2.5'].append((addr, summary.get('avg_pm2_5', float('inf'))))
                rankings['PM10'].append((addr, summary.get('avg_pm10', float('inf'))))
                rankings['NO₂'].append((addr, summary.get('avg_no2', float('inf'))))
                rankings['O₃'].append((addr, summary.get('avg_o3', float('inf'))))
        
        for addr in self.addresses:
            summary = self.weather_dbs[addr].get_summary()
            
            if summary and summary.get('total_records', 0) > 0:
                rankings['Température'].append((addr, summary.get('avg_temp', 0)))
        
        for key in ['PM2.5', 'PM10', 'NO₂']:
            rankings[key].sort(key=lambda x: x[1])
        
        rankings['O₃'].sort(key=lambda x: abs(x[1] - 100))
        rankings['Température'].sort(key=lambda x: abs(x[1] - 20))
        
        return rankings


def show_comparison_ui(addresses: List[str]):
    """Interface Streamlit comparaison multi-adresses - UI AMÉLIORÉE"""
    
    # Section d'ajout d'adresses (toujours visible)
    st.markdown("### ➕ Gestion des Adresses")
    
    # Afficher les adresses actuelles
    if addresses:
        st.markdown(f"**📍 Adresses actuellement sélectionnées ({len(addresses)}/4):**")
        for idx, addr in enumerate(addresses, 1):
            col_info, col_remove = st.columns([5, 1])
            with col_info:
                st.text(f"{idx}. {addr}")
            with col_remove:
                if st.button("🗑️", key=f"remove_{idx}", help="Supprimer cette adresse"):
                    if 'addresses' in st.session_state and addr in st.session_state.addresses:
                        del st.session_state.addresses[addr]
                        st.rerun()
    
    # Formulaire d'ajout (si moins de 4 adresses)
    if len(addresses) < 4:
        with st.expander("➕ Ajouter une nouvelle adresse", expanded=len(addresses) < 2):
            from db_utils import list_all_databases
            from geopy.geocoders import Nominatim
            
            # Choix: Nouvelle collecte ou charger depuis DB
            mode_ajout = st.radio(
                "Mode d'ajout",
                ["🆕 Nouvelle collecte de données", "💾 Charger depuis base existante"],
                key="mode_ajout_comparison",
                horizontal=True
            )
            
            if mode_ajout == "🆕 Nouvelle collecte de données":
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    new_address = st.text_input(
                        "Adresse à ajouter",
                        placeholder="Ex: 151 Boulevard du Triomphe, 1050 Bruxelles",
                        key="quick_add_address_new"
                    )
                
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("➕ Ajouter", type="primary", use_container_width=True, key="btn_add_new"):
                        if new_address:
                            try:
                                geolocator = Nominatim(user_agent="air_quality_app")
                                location = geolocator.geocode(new_address, timeout=10)
                                
                                if location:
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
            
            else:  # Charger depuis DB
                available_dbs_df = list_all_databases()
                
                if not available_dbs_df.empty:
                    # Extraire la liste des noms de fichiers
                    available_dbs = available_dbs_df['filename'].tolist()
                else:
                    available_dbs = []
                
                if available_dbs:
                    st.info(f"📊 {len(available_dbs)} base(s) de données disponible(s)")
                    
                    selected_db = st.selectbox(
                        "Sélectionner une base existante",
                        available_dbs,
                        key="select_existing_db_comparison"
                    )
                    
                    if st.button("💾 Charger cette base", type="primary", use_container_width=True, key="btn_load_db"):
                        if selected_db:
                            # Extraire l'adresse du nom de la base
                            # Format: brussels_air_quality_<adresse>.db
                            if selected_db.startswith('brussels_air_quality_'):
                                addr_from_db = selected_db.replace('brussels_air_quality_', '').replace('.db', '').replace('_', ' ')
                                
                                # Essayer de géocoder pour obtenir les coordonnées
                                try:
                                    geolocator = Nominatim(user_agent="air_quality_app")
                                    location = geolocator.geocode(addr_from_db, timeout=10)
                                    
                                    if location:
                                        if 'addresses' not in st.session_state:
                                            st.session_state.addresses = {}
                                        
                                        if addr_from_db not in st.session_state.addresses:
                                            st.session_state.addresses[addr_from_db] = {
                                                'lat': location.latitude,
                                                'lon': location.longitude
                                            }
                                            st.success(f"✅ Base chargée : {addr_from_db}")
                                            st.rerun()
                                        else:
                                            st.warning("⚠️ Cette adresse est déjà dans la liste")
                                    else:
                                        st.warning(f"⚠️ Impossible de géocoder '{addr_from_db}'. Ajout sans coordonnées.")
                                        if 'addresses' not in st.session_state:
                                            st.session_state.addresses = {}
                                        
                                        if addr_from_db not in st.session_state.addresses:
                                            st.session_state.addresses[addr_from_db] = {
                                                'lat': 50.8503,  # Bruxelles par défaut
                                                'lon': 4.3517
                                            }
                                            st.success(f"✅ Base chargée : {addr_from_db}")
                                            st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erreur : {e}")
                else:
                    st.warning("⚠️ Aucune base de données disponible. Créez d'abord des données via l'onglet principal.")
    else:
        st.info("🔒 **Limite atteinte** : Maximum 4 adresses. Supprimez-en une pour en ajouter une autre.")
    
    st.markdown("---")
    
    # Vérifier le nombre minimum d'adresses
    if len(addresses) < 2:
        st.warning("⚠️ **Ajoutez au moins 2 adresses** pour activer la comparaison.")
        return
    
    # Récupérer les coordonnées des adresses
    addresses_coords = {}
    if 'addresses' in st.session_state:
        for addr in addresses:
            if addr in st.session_state.addresses:
                addresses_coords[addr] = st.session_state.addresses[addr]
    
    comparator = AddressComparator(addresses, addresses_coords)
    
    # ========== HEADER SECTION ==========
    st.markdown("## ⚖️ Comparaison Multi-Adresses")
    st.markdown(f"**{len(addresses)} adresses** en comparaison | Analyse complète qualité air + météo")
    
    # Dashboard récapitulatif
    with st.container():
        st.markdown("### 📊 Dashboard Récapitulatif")
        
        col_summary1, col_summary2, col_summary3 = st.columns(3)
        
        with col_summary1:
            total_records = sum([
                db.get_summary().get('total_records', 0) 
                for db in comparator.air_dbs.values() 
                if db.get_summary()
            ])
            st.metric("📈 Total mesures air", f"{total_records:,}")
        
        with col_summary2:
            total_stations = sum([
                db.get_summary().get('num_stations', 0) 
                for db in comparator.air_dbs.values() 
                if db.get_summary()
            ])
            st.metric("🏭 Stations utilisées", total_stations)
        
        with col_summary3:
            total_weather = sum([
                db.get_summary().get('total_records', 0) 
                for db in comparator.weather_dbs.values() 
                if db.get_summary()
            ])
            st.metric("☁️ Total mesures météo", f"{total_weather:,}")
    
    # Carte comparative
    if addresses_coords:
        st.markdown("---")
        st.markdown("### 🗺️ Localisation des Adresses")
        
        comparison_map = comparator.create_comparison_map()
        if comparison_map:
            st_folium(comparison_map, width=None, height=400)
    
    # Bouton export Excel
    st.markdown("---")
    col_export1, col_export2, col_export3 = st.columns([1, 1, 2])
    
    with col_export1:
        if st.button("📥 Exporter vers Excel", type="secondary", use_container_width=True):
            excel_data = comparator.export_to_excel()
            st.download_button(
                label="⬇️ Télécharger Excel",
                data=excel_data,
                file_name=f"comparaison_adresses_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    
    st.markdown("---")
    
    # ========== ONGLETS ==========
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Tableaux Comparatifs",
        "📈 Évolution Temporelle",
        "🎯 Analyse Radar",
        "🏆 Classements"
    ])
    
    # ========== TAB 1: TABLEAUX COMPARATIFS ==========
    with tab1:
        st.markdown("### 🌫️ Qualité de l'Air - Tableau Comparatif")
        
        df_air = comparator.compare_air_quality()
        
        if not df_air.empty:
            # Tableau avec gradient de couleur
            st.dataframe(
                df_air.style.background_gradient(
                    subset=['PM2.5 (µg/m³)', 'PM10 (µg/m³)', 'NO₂ (µg/m³)', 'O₃ (µg/m³)'],
                    cmap='RdYlGn_r'
                ).format({
                    'PM2.5 (µg/m³)': '{:.1f}',
                    'PM10 (µg/m³)': '{:.1f}',
                    'NO₂ (µg/m³)': '{:.1f}',
                    'O₃ (µg/m³)': '{:.1f}'
                }),
                use_container_width=True,
                height=min(400, len(df_air) * 50 + 50)
            )
            
            # Cartes détaillées par adresse - AMÉLIORATION VISUELLE
            st.markdown("---")
            st.markdown("### 📍 Détails par Adresse - Qualité Air")
            
            for idx, addr in enumerate(addresses):
                # Utiliser expander pour chaque adresse avec couleur
                color = comparator.colors[idx % len(comparator.colors)]
                
                with st.expander(f"🏠 **Adresse {idx+1}** - {addr}", expanded=idx==0):
                    addr_data = df_air[df_air['Adresse'].str.contains(addr[:20], case=False, na=False)]
                    
                    if not addr_data.empty:
                        row = addr_data.iloc[0]
                        
                        # Layout en colonnes pour les métriques
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            pm25_val = row['PM2.5 (µg/m³)']
                            pm25_color = '🟢' if pm25_val < 12 else '��' if pm25_val < 35 else '🟠' if pm25_val < 55 else '🔴'
                            st.metric("PM2.5", f"{pm25_val:.1f} µg/m³", help=f"Indicateur: {pm25_color}")
                        
                        with col2:
                            pm10_val = row['PM10 (µg/m³)']
                            pm10_color = '🟢' if pm10_val < 20 else '🟡' if pm10_val < 50 else '🟠' if pm10_val < 100 else '🔴'
                            st.metric("PM10", f"{pm10_val:.1f} µg/m³", help=f"Indicateur: {pm10_color}")
                        
                        with col3:
                            no2_val = row['NO₂ (µg/m³)']
                            no2_color = '🟢' if no2_val < 40 else '��' if no2_val < 90 else '🟠' if no2_val < 120 else '🔴'
                            st.metric("NO₂", f"{no2_val:.1f} µg/m³", help=f"Indicateur: {no2_color}")
                        
                        with col4:
                            o3_val = row['O₃ (µg/m³)']
                            o3_color = '🟢' if o3_val < 60 else '🟡' if o3_val < 120 else '🟠' if o3_val < 180 else '🔴'
                            st.metric("O₃", f"{o3_val:.1f} µg/m³", help=f"Indicateur: {o3_color}")
                        
                        # Informations supplémentaires
                        st.markdown(f"""
                        **📊 Statistiques:**
                        - {row['Stations']} station(s) utilisée(s)
                        - {row['Mesures']} mesures enregistrées
                        """)
                    else:
                        st.info("Pas de données disponibles")
        else:
            st.warning("Aucune donnée qualité air disponible")
        
        st.markdown("---")
        st.markdown("### ☁️ Météo - Tableau Comparatif")
        
        df_weather = comparator.compare_weather()
        
        if not df_weather.empty:
            st.dataframe(
                df_weather.style.background_gradient(
                    subset=['Temp. moy (°C)', 'Vent moy (km/h)', 'Humidité (%)'],
                    cmap='coolwarm'
                ).format({
                    'Temp. moy (°C)': '{:.1f}',
                    'Temp. min (°C)': '{:.1f}',
                    'Temp. max (°C)': '{:.1f}',
                    'Vent moy (km/h)': '{:.1f}',
                    'Humidité (%)': '{:.1f}'
                }),
                use_container_width=True,
                height=min(400, len(df_weather) * 50 + 50)
            )
            
            # Cartes détaillées par adresse - Météo
            st.markdown("---")
            st.markdown("### 📍 Détails par Adresse - Météo")
            
            for idx, addr in enumerate(addresses):
                with st.expander(f"🌡️ **Adresse {idx+1}** - {addr}", expanded=idx==0):
                    addr_weather = df_weather[df_weather['Adresse'].str.contains(addr[:20], case=False, na=False)]
                    
                    if not addr_weather.empty:
                        row = addr_weather.iloc[0]
                        
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Temp. Moyenne", f"{row['Temp. moy (°C)']:.1f}°C")
                        
                        with col2:
                            st.metric("Temp. Min", f"{row['Temp. min (°C)']:.1f}°C")
                        
                        with col3:
                            st.metric("Temp. Max", f"{row['Temp. max (°C)']:.1f}°C")
                        
                        with col4:
                            st.metric("Vent Moyen", f"{row['Vent moy (km/h)']:.1f} km/h")
                        
                        st.markdown(f"""
                        **📊 Statistiques:**
                        - Humidité moyenne: {row['Humidité (%)']:.0f}%
                        - {row['Mesures']} mesures enregistrées
                        """)
                    else:
                        st.info("Pas de données disponibles")
        else:
            st.warning("Aucune donnée météo disponible")
    
    # ========== TAB 2: ÉVOLUTION TEMPORELLE ==========
    with tab2:
        st.markdown("### 📈 Évolution Temporelle - Comparaison")
        
        pollutant = st.selectbox(
            "Choisir un polluant",
            ['pm2_5', 'pm10', 'no2', 'o3'],
            format_func=lambda x: {'pm2_5': 'PM2.5', 'pm10': 'PM10', 'no2': 'NO₂', 'o3': 'O₃'}[x],
            key='compare_pollutant'
        )
        
        fig_evolution = comparator.plot_pollutant_comparison(pollutant)
        st.plotly_chart(fig_evolution, use_container_width=True)
        
        # Statistiques par adresse
        st.markdown("---")
        st.markdown("#### 📊 Statistiques Détaillées par Adresse")
        
        cols = st.columns(len(addresses))
        
        for idx, addr in enumerate(addresses):
            with cols[idx]:
                st.markdown(f"**Adresse {idx+1}**")
                st.caption(addr[:30] + "..." if len(addr) > 30 else addr)
                
                df_addr = comparator.air_dbs[addr].get_pollutant_data(pollutant)
                
                if not df_addr.empty:
                    st.metric("Min", f"{df_addr['value'].min():.1f} µg/m³")
                    st.metric("Moy", f"{df_addr['value'].mean():.1f} µg/m³")
                    st.metric("Max", f"{df_addr['value'].max():.1f} µg/m³")
                    st.caption(f"�� {len(df_addr)} mesures")
                else:
                    st.info("Pas de données")
        
        # Température
        st.markdown("---")
        st.markdown("### 🌡️ Température - Comparaison")
        fig_temp = comparator.plot_temperature_comparison()
        st.plotly_chart(fig_temp, use_container_width=True)
    
    # ========== TAB 3: ANALYSE RADAR ==========
    with tab3:
        st.markdown("### 🎯 Analyse Radar - Qualité Air")
        
        fig_radar = comparator.plot_radar_comparison()
        st.plotly_chart(fig_radar, use_container_width=True)
        
        st.info("""
        **📖 Interprétation:**
        - Plus la surface est grande et proche du bord extérieur, meilleure est la qualité de l'air
        - Un score de 100 représente une qualité excellente
        - Un score de 0 représente une qualité très mauvaise
        """)
    
    # ========== TAB 4: CLASSEMENTS ==========
    with tab4:
        st.markdown("### 🏆 Classement des Adresses")
        
        rankings = comparator.get_ranking()
        
        # Podium
        st.markdown("#### 🥇 Podium par Polluant")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("**🌫️ PM2.5**")
            for i, (addr, val) in enumerate(rankings['PM2.5'][:3], 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
                color = "🟢" if val < 12 else "🟡" if val < 35 else "🟠"
                st.markdown(f"{emoji} {addr[:15]}...")
                st.caption(f"{color} {val:.1f} µg/m³")
        
        with col2:
            st.markdown("**💨 PM10**")
            for i, (addr, val) in enumerate(rankings['PM10'][:3], 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
                color = "🟢" if val < 20 else "🟡" if val < 50 else "🟠"
                st.markdown(f"{emoji} {addr[:15]}...")
                st.caption(f"{color} {val:.1f} µg/m³")
        
        with col3:
            st.markdown("**🚗 NO₂**")
            for i, (addr, val) in enumerate(rankings['NO₂'][:3], 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
                color = "🟢" if val < 40 else "🟡" if val < 90 else "🟠"
                st.markdown(f"{emoji} {addr[:15]}...")
                st.caption(f"{color} {val:.1f} µg/m³")
        
        with col4:
            st.markdown("**☀️ O₃**")
            for i, (addr, val) in enumerate(rankings['O₃'][:3], 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "��"
                color = "🟢" if val < 60 else "🟡" if val < 120 else "🟠"
                st.markdown(f"{emoji} {addr[:15]}...")
                st.caption(f"{color} {val:.1f} µg/m³")
        
        # Classement complet avec score global
        st.markdown("---")
        st.markdown("#### 📋 Classement Complet - Score Global")
        
        classement_data = []
        for addr in addresses:
            summary = comparator.air_dbs[addr].get_summary()
            if summary and summary.get('total_records', 0) > 0:
                scores = []
                pm25 = summary.get('avg_pm2_5', 0)
                if pm25 > 0:
                    scores.append(max(0, 100 - (pm25 / 75 * 100)))
                
                pm10 = summary.get('avg_pm10', 0)
                if pm10 > 0:
                    scores.append(max(0, 100 - (pm10 / 150 * 100)))
                
                no2 = summary.get('avg_no2', 0)
                if no2 > 0:
                    scores.append(max(0, 100 - (no2 / 340 * 100)))
                
                score_global = sum(scores) / len(scores) if scores else 0
                
                # Déterminer la qualité selon le score
                if score_global >= 80:
                    qualite = 'Excellente'
                elif score_global >= 60:
                    qualite = 'Bonne'
                elif score_global >= 40:
                    qualite = 'Moyenne'
                else:
                    qualite = 'Médiocre'
                
                classement_data.append({
                    'Adresse': addr[:30] + "..." if len(addr) > 30 else addr,
                    'Score Global': score_global,
                    'PM2.5 (µg/m³)': pm25,
                    'PM10 (µg/m³)': pm10,
                    'NO₂ (µg/m³)': no2,
                    'Qualité': qualite
                })
        
        if classement_data:
            df_classement = pd.DataFrame(classement_data)
            df_classement = df_classement.sort_values('Score Global', ascending=False).reset_index(drop=True)
            df_classement.index += 1
            df_classement.index.name = 'Rang'
            
            st.dataframe(
                df_classement.style.background_gradient(
                    subset=['Score Global'],
                    cmap='RdYlGn',
                    vmin=0,
                    vmax=100
                ).format({
                    'Score Global': '{:.1f}',
                    'PM2.5 (µg/m³)': '{:.1f}',
                    'PM10 (µg/m³)': '{:.1f}',
                    'NO₂ (µg/m³)': '{:.1f}'
                }),
                use_container_width=True
            )
            
            # Recommandation
            st.markdown("---")
            st.markdown("#### 💡 Recommandation")
            
            meilleure_addr = df_classement.iloc[0]
            st.success(f"""
            **🏆 Meilleure adresse : {meilleure_addr['Adresse']}**
            
            - Score global : **{meilleure_addr['Score Global']:.1f}/100**
            - Qualité : **{meilleure_addr['Qualité']}**
            - PM2.5 : {meilleure_addr['PM2.5 (µg/m³)']:.1f} µg/m³
            - PM10 : {meilleure_addr['PM10 (µg/m³)']:.1f} µg/m³
            - NO₂ : {meilleure_addr['NO₂ (µg/m³)']:.1f} µg/m³
            """)
        else:
            st.info("Pas assez de données pour établir un classement")
