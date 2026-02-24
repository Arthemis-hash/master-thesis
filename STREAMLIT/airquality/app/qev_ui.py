#!/usr/bin/env python3
"""
============================================================
MODULE UI QeV - Qualité Environnementale de Vie
============================================================
Interface Streamlit pour l'affichage de l'indicateur QeV
============================================================
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Dict, Optional


def display_qev_section(qev_result: Dict):
    """
    Affiche la section QeV complète avec visualisations.

    Args:
        qev_result: Résultat du calcul QeV depuis qev_service
    """
    if not qev_result:
        st.warning("⚠️ Impossible de calculer le score QeV pour cette adresse")
        st.info("""
        Le calcul du score QeV nécessite:
        - ✅ Données de qualité de l'air
        - ⚠️ Données de trafic (estimées par défaut)
        - ⚠️ Données d'espaces verts (analyse YOLO + segmentation)
        """)
        return

    # ========== SECTION 1: SCORE PRINCIPAL ==========
    st.subheader("🎯 Score Global QeV")

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        # Jauge QeV
        fig_gauge = create_qev_gauge(qev_result['QeV'], qev_result['QeV_category'])
        st.plotly_chart(fig_gauge, width="stretch")

    with col2:
        st.metric(
            "Score QeV",
            f"{qev_result['QeV']:.3f}",
            help="Score entre 0 (très mauvais) et 1 (excellent)"
        )
        st.metric(
            "Catégorie",
            qev_result['QeV_category'],
            help="Classification qualitative du score"
        )

    with col3:
        st.metric(
            "Complétude",
            f"{qev_result['data_completeness']:.0%}",
            help="Pourcentage de données disponibles pour le calcul"
        )
        st.metric(
            "Confiance",
            f"{qev_result['confidence_level']:.0%}",
            help="Niveau de confiance dans le résultat"
        )

    # Interprétation
    with st.expander("📖 Interprétation du score", expanded=True):
        st.write(qev_result['interpretation'])

    st.divider()

    # ========== SECTION 2: SOUS-INDICATEURS ==========
    st.subheader("📊 Décomposition par Dimension")

    # Graphique radar des 3 dimensions
    fig_radar = create_radar_chart(qev_result)
    st.plotly_chart(fig_radar, width="stretch")

    # Détails des sous-scores
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 🌫️ Qualité de l'Air")
        s_air = qev_result['normalized_scores']['S_Air']
        st.progress(s_air, text=f"Score: {s_air:.2f}")

        with st.expander("Détails Air"):
            st.write(f"**Indice BelAQI**: {qev_result['sub_indices']['I_Air']:.1f}/10")
            st.write("**Sous-indices par polluant:**")

            air_details = qev_result['sub_indices']['I_Air_details']
            for pollutant, value in air_details.items():
                st.write(f"- {pollutant.upper()}: {value:.2f}")

            st.write(f"**Pondération**: {qev_result['weights']['air']:.0%}")

    with col2:
        st.markdown("### 🚗 Impact Trafic")
        s_traffic = qev_result['normalized_scores']['S_Trafic']
        st.progress(s_traffic, text=f"Score: {s_traffic:.2f}")

        with st.expander("Détails Trafic"):
            st.write(f"**Nuisance brute**: {qev_result['sub_indices']['I_Trafic']:.0f} unités")

            traffic_raw = qev_result['raw_indicators']['traffic']
            st.write("**Comptages (véhicules/h):**")
            st.write(f"- Voitures: {traffic_raw['light_vehicles']}")
            st.write(f"- Utilitaires: {traffic_raw['utility_vehicles']}")
            st.write(f"- Poids lourds: {traffic_raw['heavy_vehicles']}")

            st.write("**Coefficients EMEP/EEA:**")
            st.write("- Voiture: ×1.0")
            st.write("- Utilitaire: ×3.2")
            st.write("- Poids lourd: ×12.5")

            st.write(f"**Pondération**: {qev_result['weights']['traffic']:.0%}")

    with col3:
        st.markdown("### 🌳 Espaces Verts")
        s_green = qev_result['normalized_scores']['S_Vert']
        st.progress(s_green, text=f"Score: {s_green:.2f}")

        with st.expander("Détails Végétation"):
            st.write(f"**Indice 3-30-300**: {qev_result['sub_indices']['I_Vert']:.2f}")

            green_raw = qev_result['raw_indicators']['green']

            st.write("**Règle 3-30-300:**")
            st.write(f"- Arbres visibles: {green_raw.get('trees_visible_count', 0)} (min: 3)")
            st.write(f"- Couverture canopée: {green_raw.get('canopy_coverage_pct', 0):.1f}% (cible: 30%)")
            st.write(f"- Distance parc: {green_raw.get('distance_to_nearest_park_m', 999):.0f}m (max: 300m)")

            st.write(f"**Pondération**: {qev_result['weights']['green']:.0%}")

    st.divider()

    # ========== SECTION 3: GRAPHIQUES DÉTAILLÉS ==========
    st.subheader("📈 Analyse Détaillée")

    tab1, tab2, tab3 = st.tabs(["Contributions", "Évolution simulée", "Comparaison"])

    with tab1:
        # Graphique en barres des contributions
        fig_contributions = create_contributions_chart(qev_result)
        st.plotly_chart(fig_contributions, width="stretch")

        st.markdown("""
        **Lecture du graphique:**
        - Les barres vertes montrent la contribution positive de chaque dimension au score final
        - La hauteur dépend du score normalisé ET de la pondération
        - Air Quality a le plus de poids (50%) dans le score final
        """)

    with tab2:
        st.info("📊 Fonctionnalité à venir: Évolution temporelle du QeV si données historiques disponibles")

        # Placeholder pour évolution future
        # fig_evolution = create_evolution_chart(qev_history)
        # st.plotly_chart(fig_evolution, width="stretch")

    with tab3:
        st.info("📊 Fonctionnalité à venir: Comparaison avec d'autres quartiers de Bruxelles")

        # Placeholder pour benchmark
        # fig_benchmark = create_benchmark_chart(qev_result, brussels_avg)
        # st.plotly_chart(fig_benchmark, width="stretch")

    st.divider()

    # ========== SECTION 4: MÉTADONNÉES ==========
    with st.expander("🔍 Métadonnées et Sources de Données"):
        st.write(f"**Calculé le**: {qev_result['calculated_at']}")
        st.write(f"**Adresse**: {qev_result['address']}")
        st.write(f"**Coordonnées**: {qev_result['coordinates']['lat']:.4f}, {qev_result['coordinates']['lon']:.4f}")

        st.write("**Sources de données:**")
        st.write("- Air: BelAQI (IRCEL-CELINE) + Open-Meteo")
        st.write("- Trafic: Estimation par défaut (à améliorer avec données réelles)")
        st.write("- Végétation: Analyse YOLO + Segmentation satellite")

        st.write("**Méthode de calcul:**")
        st.write(f"- Algorithme: BelAQI (méthode du maximum) + EMEP/EEA + Règle 3-30-300")
        st.write(f"- Pondérations: Air {qev_result['weights']['air']:.0%}, Trafic {qev_result['weights']['traffic']:.0%}, Vert {qev_result['weights']['green']:.0%}")
        st.write(f"- Normalisation: Min-Max avec inversion pour facteurs négatifs")

    # ========== SECTION 5: RECOMMANDATIONS ==========
    st.subheader("💡 Recommandations")

    qev_score = qev_result['QeV']

    if qev_score >= 0.8:
        st.success("""
        ✅ **Environnement Excellent**

        Votre environnement présente des conditions optimales pour la santé:
        - Qualité de l'air excellente
        - Faible impact du trafic
        - Espaces verts accessibles et abondants

        **Conseils:**
        - Profitez des espaces verts pour activités physiques régulières
        - Maintenez ces bonnes conditions (participation citoyenne)
        """)
    elif qev_score >= 0.6:
        st.success("""
        🟡 **Environnement Bon**

        Votre environnement est globalement favorable à la santé avec quelques marges d'amélioration.

        **Conseils:**
        - Continuez à profiter des espaces verts disponibles
        - Privilégiez les modes de transport doux
        - Surveillez les pics de pollution
        """)
    elif qev_score >= 0.4:
        st.warning("""
        🟠 **Environnement Modéré**

        Certains facteurs de risque sont présents dans votre environnement.

        **Conseils:**
        - Limitez l'exposition lors des pics de pollution
        - Recherchez des espaces verts dans un rayon de 300m
        - Privilégiez les transports en commun
        - Aérez votre logement tôt le matin ou tard le soir
        """)
    elif qev_score >= 0.2:
        st.warning("""
        🔴 **Environnement Médiocre**

        Votre environnement présente plusieurs facteurs de risque pour la santé.

        **Conseils:**
        - Consultez quotidiennement la qualité de l'air
        - Évitez les activités intenses à l'extérieur lors des pics
        - Utilisez un purificateur d'air intérieur si possible
        - Recherchez activement des espaces verts accessibles
        - Portez un masque lors des pics de pollution
        """)
    else:
        st.error("""
        ⛔ **Environnement Très Mauvais**

        Votre environnement présente des risques sanitaires significatifs.

        **Actions urgentes recommandées:**
        - Consultez un médecin si symptômes respiratoires
        - Investissez dans un purificateur d'air HEPA
        - Évitez les sorties lors des pics de pollution
        - Portez un masque FFP2 à l'extérieur
        - Envisagez un déménagement si possible
        - Contactez les autorités locales pour signaler les problèmes
        """)


# ============================================================
# FONCTIONS DE VISUALISATION
# ============================================================

def create_qev_gauge(qev_score: float, category: str) -> go.Figure:
    """
    Crée une jauge circulaire pour le score QeV.

    Args:
        qev_score: Score QeV (0-1)
        category: Catégorie textuelle

    Returns:
        Figure Plotly
    """
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=qev_score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Score QeV", 'font': {'size': 24}},
        delta={'reference': 0.6, 'increasing': {'color': "green"}},
        gauge={
            'axis': {'range': [0, 1], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "darkblue"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 0.2], 'color': '#ffcccc'},
                {'range': [0.2, 0.4], 'color': '#ffe6cc'},
                {'range': [0.4, 0.6], 'color': '#ffffcc'},
                {'range': [0.6, 0.8], 'color': '#ccffcc'},
                {'range': [0.8, 1.0], 'color': '#99ff99'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 0.6
            }
        }
    ))

    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        font={'color': "darkblue", 'family': "Arial"}
    )

    return fig


def create_radar_chart(qev_result: Dict) -> go.Figure:
    """
    Crée un graphique radar des 3 dimensions QeV.

    Args:
        qev_result: Résultat QeV

    Returns:
        Figure Plotly
    """
    categories = ['Qualité Air', 'Impact Trafic', 'Espaces Verts']

    scores = [
        qev_result['normalized_scores']['S_Air'],
        qev_result['normalized_scores']['S_Trafic'],
        qev_result['normalized_scores']['S_Vert']
    ]

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=scores,
        theta=categories,
        fill='toself',
        name='Score QeV',
        line_color='rgba(0, 123, 255, 0.8)',
        fillcolor='rgba(0, 123, 255, 0.3)'
    ))

    # Ajouter une ligne de référence à 0.6 (seuil "Bon")
    fig.add_trace(go.Scatterpolar(
        r=[0.6, 0.6, 0.6],
        theta=categories,
        fill='none',
        name='Seuil "Bon" (0.6)',
        line=dict(color='green', dash='dash'),
        showlegend=True
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1]
            )
        ),
        showlegend=True,
        title="Profil QeV par Dimension",
        height=400
    )

    return fig


def create_contributions_chart(qev_result: Dict) -> go.Figure:
    """
    Crée un graphique en barres des contributions pondérées.

    Args:
        qev_result: Résultat QeV

    Returns:
        Figure Plotly
    """
    dimensions = ['Air Quality', 'Traffic Impact', 'Green Spaces']

    # Contributions = score normalisé × pondération
    contributions = [
        qev_result['normalized_scores']['S_Air'] * qev_result['weights']['air'],
        qev_result['normalized_scores']['S_Trafic'] * qev_result['weights']['traffic'],
        qev_result['normalized_scores']['S_Vert'] * qev_result['weights']['green']
    ]

    colors = ['#3498db', '#e74c3c', '#2ecc71']

    fig = go.Figure(data=[
        go.Bar(
            x=dimensions,
            y=contributions,
            marker_color=colors,
            text=[f"{c:.3f}" for c in contributions],
            textposition='auto',
        )
    ])

    fig.update_layout(
        title="Contribution de chaque dimension au score QeV final",
        yaxis_title="Contribution pondérée",
        xaxis_title="Dimension",
        height=400,
        showlegend=False
    )

    # Ajouter une ligne horizontale pour le score moyen
    avg_contribution = qev_result['QeV'] / 3
    fig.add_hline(
        y=avg_contribution,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"Moyenne: {avg_contribution:.3f}"
    )

    return fig


# ============================================================
# EXPORT
# ============================================================

__all__ = ['display_qev_section']
