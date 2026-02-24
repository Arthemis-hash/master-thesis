#!/usr/bin/env python3
"""
Module UI pour l'affichage des résultats d'analyse
"""

import streamlit as st
from streamlit_folium import st_folium
import pandas as pd
import matplotlib.pyplot as plt
import logging

from db_async_wrapper import AirQualityDB
from air_quality_map import AirQualityMapper
from weather_ui import display_weather_section
# Import lazy de environment_ui pour éviter conflits de config

logger = logging.getLogger(__name__)


def display_results(address):
    """Affiche les résultats pour l'adresse"""
    # Utiliser la base sélectionnée si disponible, sinon chercher/créer pour l'adresse
    if st.session_state.get('selected_db'):
        # Charger directement la base sélectionnée
        db_path = st.session_state.selected_db
        # Créer une instance temporaire pour utiliser ce fichier spécifique
        db = AirQualityDB(address=address)
        db.db_path = db_path  # Forcer l'utilisation de la base sélectionnée
        mapper = AirQualityMapper(address=address)
        mapper.db.db_path = db_path  # Forcer aussi pour le mapper
    else:
        # Utiliser le nouveau système avec adresse
        mapper = AirQualityMapper(address=address)
        db = AirQualityDB(address=address)

    # Debug : afficher l'adresse recherchée
    st.info(f"🔍 Recherche des données pour : {address}")

    # Essayer de récupérer les données avec plusieurs méthodes
    summary = db.get_location_summary(address)

    # Si échec, essayer avec juste le premier mot (ex: "Bruxelles" au lieu de "Bruxelles, Region...")
    if not summary:
        first_word = address.split(',')[0].strip()
        st.warning(f"⚠️ Aucun résultat pour '{address}', tentative avec '{first_word}'...")
        summary = db.get_location_summary(first_word)

    # Si toujours échec, essayer avec toutes les adresses disponibles
    if not summary:
        st.error("⚠️ Aucune donnée disponible pour cette adresse")
        st.caption("💡 Astuce : Vérifiez que vous avez bien téléchargé les données pour cette adresse")
        return


    # Métriques principales
    st.header("📊 Indicateurs Clés")

    # Calculer le score QeV
    qev_result = None
    try:
        qev_result = db.get_qev_score(address)
    except Exception as e:
        logger.warning(f"Impossible de calculer QeV: {e}")

    # Afficher 5 colonnes si QeV disponible, sinon 4
    if qev_result:
        col1, col2, col3, col4, col5 = st.columns(5)
    else:
        col1, col2, col3, col4 = st.columns(4)

    aqi_label, aqi_color = mapper.get_air_quality_index(summary['avg_pm2_5'])
    color_map = {'green': '🟢', 'yellow': '🟡', 'orange': '🟠', 'red': '🔴', 'gray': '⚪'}

    with col1:
        st.metric(
            "Qualité de l'air",
            f"{color_map.get(aqi_color, '⚪')} {aqi_label}",
            delta=None
        )

    with col2:
        st.metric("PM2.5 moyen", f"{summary['avg_pm2_5']:.1f} μg/m³")

    with col3:
        st.metric("Alertes pollution", f"{summary['pollution_alert_pct']:.1f}%")

    with col4:
        st.metric("Mesures", f"{summary['total_records']}")

    # Nouvelle KPI Card QeV
    if qev_result:
        with col5:
            qev_score = qev_result['QeV']
            qev_category = qev_result['QeV_category']

            # Emojis par catégorie
            qev_emoji_map = {
                'Excellent': '🟢',
                'Bon': '🟡',
                'Modéré': '🟠',
                'Médiocre': '🔴',
                'Très mauvais': '⛔'
            }

            st.metric(
                "Score QeV",
                f"{qev_emoji_map.get(qev_category, '⚪')} {qev_score:.2f}",
                delta=f"{qev_category}",
                help="Qualité Environnementale de Vie (0-1): Indicateur composite (Air 50%, Trafic 25%, Espaces verts 25%)"
            )

    # Carte interactive
    st.header("🗺️ Carte Interactive")
    map_obj, _ = mapper.create_location_map(address)

    if map_obj:
        st_folium(map_obj, width=1200, height=500)

    # Graphiques
    st.header("📈 Analyses Détaillées")

    # Créer les onglets avec ou sans QeV
    if qev_result:
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
            "🔄 Évolution temporelle",
            "📊 Statistiques",
            "🌼 Pollens & UV",
            "🌤️ Météo (16j)",
            "🛰️ Cartes & Images",
            "🔬 Analyse Environnementale",
            "📊 Score QeV",
            "📋 Données brutes"
        ])
    else:
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "🔄 Évolution temporelle",
            "📊 Statistiques",
            "🌼 Pollens & UV",
            "🌤️ Météo (16j)",
            "🛰️ Cartes & Images",
            "🔬 Analyse Environnementale",
            "📋 Données brutes"
        ])

    with tab1:
        try:
            fig = mapper.create_data_visualization(address)
            if fig is not None:
                st.pyplot(fig)
                plt.close(fig)  # Fermer la figure pour libérer la mémoire
            else:
                st.warning("⚠️ Impossible de générer la visualisation des données")
                st.info("Vérifiez que les données sont disponibles pour cette adresse")
        except Exception as e:
            st.error(f"❌ Erreur lors de la génération du graphique : {e}")
            logger.error(f"Erreur create_data_visualization: {e}", exc_info=True)

    with tab2:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Moyennes des polluants")
            pollutants_data = {
                'Polluant': ['PM2.5', 'PM10', 'NO₂', 'O₃', 'SO₂', 'CO'],
                'Concentration (μg/m³)': [
                    summary['avg_pm2_5'],
                    summary['avg_pm10'],
                    summary['avg_no2'],
                    summary['avg_o3'],
                    summary['avg_so2'],
                    summary['avg_co']
                ]
            }
            st.dataframe(pollutants_data, width="stretch")

        with col2:
            st.subheader("Pics de pollution")
            peaks_data = {
                'Polluant': ['PM2.5 max', 'PM10 max'],
                'Valeur (μg/m³)': [summary['max_pm2_5'], summary['max_pm10']]
            }
            st.dataframe(peaks_data, width="stretch")

    with tab3:
        st.subheader("🌼 Données Pollens et UV")

        # Récupérer les données pollens depuis la table dédiée
        pollen_data_df = db.get_pollen_data(address)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Concentrations de pollens**")
            
            if not pollen_data_df.empty:
                # Pollens disponibles dans la table dédiée
                pollen_cols = ['grass_pollen', 'birch_pollen', 'alder_pollen', 'hazel_pollen',
                              'cypress_pollen', 'oak_pollen', 'mugwort_pollen', 'ragweed_pollen',
                              'plane_pollen', 'nettle_pollen', 'total_pollen']
                available_pollens = [col for col in pollen_cols if col in pollen_data_df.columns]
                
                if available_pollens:
                    pollen_display = {}
                    has_any_pollen = False
                    
                    for col in available_pollens:
                        col_data = pollen_data_df[col].dropna()
                        if len(col_data) > 0:
                            avg_val = col_data.mean()
                            if avg_val > 0:
                                has_any_pollen = True
                            # Noms lisibles
                            display_name = col.replace('_pollen', '').title()
                            if display_name == 'Total':
                                display_name = 'Total (tous types)'
                            pollen_display[display_name] = f"{avg_val:.2f} grains/m³"
                    
                    if pollen_display:
                        st.json(pollen_display)
                        st.caption(f"📊 Basé sur {len(pollen_data_df)} mesures")
                        
                        if not has_any_pollen:
                            st.info("ℹ️ Concentrations nulles - normal en hiver/automne")
                    else:
                        st.warning("⚠️ Colonnes pollens vides dans la base")
                else:
                    st.warning("⚠️ Format des données pollens non reconnu")
            else:
                # Pas de données dans la table pollen_records
                st.info("ℹ️ Aucune donnée pollen dans la base pour cette adresse")
                st.caption("Les données pollens proviennent d'IRCELINE (Belgique) ou CAMS Europe")

        with col2:
            st.write("**Indice UV**")
            # Note: UV n'est pas stocké dans les enregistrements météo actuels
            # TODO: Ajouter récupération UV depuis Open-Meteo API 
            st.info("ℹ️ Données UV non disponibles")
            st.caption("L'indice UV sera disponible prochainement")

    with tab4:
        try:
            display_weather_section(
                address=address,
                lat=summary['latitude'],
                lon=summary['longitude']
            )
        except Exception as e:
            logger.error(f"Erreur météo: {e}")
            st.error("⚠️ Module météo temporairement indisponible")

    with tab5:
        try:
            # Import dynamique pour éviter conflits de config
            from environment_ui import display_environment_section
            
            display_environment_section(
                address=address,
                lat=summary['latitude'],
                lon=summary['longitude']
            )
        except Exception as e:
            logger.error(f"Erreur environnement: {e}")
            st.error("⚠️ Module environnement temporairement indisponible")

    with tab6:
        try:
            # Import dynamique pour éviter conflits
            from environmental_analysis_ui import display_environmental_analysis

            display_environmental_analysis(address=address)
        except Exception as e:
            logger.error(f"Erreur analyse environnementale: {e}")
            st.error("⚠️ Module d'analyse environnementale temporairement indisponible")

    # Onglet 7: QeV (si disponible) ou Données brutes (sinon)
    with tab7:
        if qev_result:
            # Afficher le score QeV
            try:
                from qev_ui import display_qev_section
                display_qev_section(qev_result)
            except Exception as e:
                logger.error(f"Erreur affichage QeV: {e}")
                st.error(f"⚠️ Erreur lors de l'affichage du score QeV: {e}")
                # Affichage fallback en cas d'erreur
                st.json(qev_result)
        else:
            # Afficher les données brutes (pas de QeV)
            show_raw = st.session_state.get('show_raw_data', False)
            if show_raw:
                location_data = db.get_location_data(address)
                st.dataframe(location_data, width="stretch")

                # Téléchargement CSV
                csv = location_data.to_csv(index=False)
                st.download_button(
                    label="📥 Télécharger les données (CSV)",
                    data=csv,
                    file_name=f"air_quality_{address.replace(' ', '_')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("Activez 'Afficher les données brutes' dans les options avancées")

    # Onglet 8: Données brutes (uniquement si QeV disponible)
    if qev_result:
        with tab8:
            show_raw = st.session_state.get('show_raw_data', False)
            if show_raw:
                location_data = db.get_location_data(address)
                st.dataframe(location_data, width="stretch")

                # Téléchargement CSV
                csv = location_data.to_csv(index=False)
                st.download_button(
                    label="📥 Télécharger les données (CSV)",
                    data=csv,
                    file_name=f"air_quality_{address.replace(' ', '_')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("Activez 'Afficher les données brutes' dans les options avancées")

    # Recommandations
    st.header("💡 Recommandations")
    if summary['avg_pm2_5'] <= 10:
        st.success("✅ **Qualité de l'air excellente** - Aucune précaution particulière")
    elif summary['avg_pm2_5'] <= 20:
        st.warning("⚠️ **Qualité de l'air modérée** - Évitez les activités intenses à l'extérieur")
    else:
        st.error("🚨 **Qualité de l'air mauvaise** - Limitez les sorties, portez un masque si nécessaire")
