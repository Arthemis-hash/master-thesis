#!/usr/bin/env python3
"""
============================================================
SERVICE QeV - Orchestration des calculs
============================================================
Couche d'intégration entre calculateur QeV et base de données
============================================================
"""

import logging
from typing import Dict, Optional
from datetime import datetime
import pandas as pd

from qev_calculator import (
    AirQualityData,
    TrafficData,
    GreenSpaceData,
    QeVResult,
    calculate_qev
)
from green_space_analyzer import calculate_330_rule_metrics, estimate_traffic_from_osm

logger = logging.getLogger(__name__)


# ============================================================
# SERVICE PRINCIPAL
# ============================================================

class QeVService:
    """Service pour calculer et stocker les scores QeV"""

    def __init__(self):
        """Initialise le service QeV"""
        pass

    def calculate_qev_for_address(
        self,
        address: str,
        latitude: float,
        longitude: float,
        air_quality_df: Optional[pd.DataFrame] = None,
        traffic_data: Optional[Dict] = None
    ) -> Dict:
        """
        Calcule le score QeV complet pour une adresse.

        Args:
            address: Adresse à analyser
            latitude: Latitude
            longitude: Longitude
            air_quality_df: DataFrame avec données air quality (optionnel)
            traffic_data: Dict avec données trafic (optionnel)

        Returns:
            Dict avec tous les résultats QeV
        """
        logger.info("=" * 60)
        logger.info(f"🎯 CALCUL QeV pour: {address}")
        logger.info(f"   📍 Coordonnées: ({latitude:.6f}, {longitude:.6f})")
        logger.info("=" * 60)

        # ========== COLLECTE DES DONNÉES ==========

        # 1. Données qualité de l'air
        logger.info("── [1/4] Qualité de l'air ──")
        air_data = self._prepare_air_quality_data(air_quality_df)
        logger.info(f"   NO2={air_data.no2}, PM2.5={air_data.pm25}, PM10={air_data.pm10}, "
                     f"O3={air_data.o3}, SO2={air_data.so2}")

        # 2. Données trafic - estimer via OSM si non fournies
        logger.info("── [2/4] Estimation trafic (Overpass OSM) ──")
        if traffic_data is None:
            traffic_data = self._estimate_traffic_from_osm(latitude, longitude)
        traffic = self._prepare_traffic_data(traffic_data)
        logger.info(f"   Légers={traffic.light_vehicles}/h, Utilitaires={traffic.utility_vehicles}/h, "
                     f"Lourds={traffic.heavy_vehicles}/h")

        # 3. Données espaces verts (règle 3-30-300)
        logger.info("── [3/4] Espaces verts (règle 3-30-300) ──")
        green_metrics = calculate_330_rule_metrics(address, latitude, longitude)
        logger.info(f"   🌳 Arbres visibles: {green_metrics.get('trees_visible_count', 0)} "
                     f"(min requis: 3)")
        logger.info(f"   🌿 Canopée: {green_metrics.get('canopy_coverage_pct', 0):.1f}% "
                     f"(objectif: 30%)")
        logger.info(f"   🏞️ Parc le plus proche: {green_metrics.get('nearest_park_name', '?')} "
                     f"à {green_metrics.get('distance_to_nearest_park_m', 999):.0f}m "
                     f"(seuil: 300m)")
        green = GreenSpaceData(
            trees_visible=green_metrics.get('trees_visible_count', 0),
            canopy_coverage_pct=green_metrics.get('canopy_coverage_pct', 0.0),
            distance_to_green_space_m=green_metrics.get('distance_to_nearest_park_m', 999.0)
        )

        # ========== CALCUL QeV ==========
        logger.info("── [4/4] Calcul score final QeV ──")
        qev_result = calculate_qev(air_data, traffic, green)

        # ========== PRÉPARATION RÉSULTAT ==========
        result = {
            'address': address,
            'coordinates': {'lat': latitude, 'lon': longitude},
            'calculated_at': datetime.now().isoformat(),

            # Données brutes
            'raw_indicators': {
                'air': self._air_data_to_dict(air_data),
                'traffic': self._traffic_data_to_dict(traffic),
                'green': green_metrics
            },

            # Sous-indices
            'sub_indices': {
                'I_Air': qev_result.raw_air_index,
                'I_Air_details': qev_result.raw_air_sub_indices,
                'I_Trafic': qev_result.raw_traffic_nuisance,
                'I_Vert': qev_result.raw_green_index
            },

            # Scores normalisés
            'normalized_scores': {
                'S_Air': qev_result.normalized_air_score,
                'S_Trafic': qev_result.normalized_traffic_score,
                'S_Vert': qev_result.normalized_green_score
            },

            # Score final
            'QeV': qev_result.qev_score,
            'QeV_category': qev_result.qev_category,

            # Métadonnées
            'weights': qev_result.weights,
            'data_completeness': qev_result.data_completeness,
            'confidence_level': qev_result.confidence_level,

            # Interprétation
            'interpretation': self._get_interpretation(qev_result.qev_score)
        }

        logger.info(f"   S_Air={qev_result.normalized_air_score:.3f}, "
                     f"S_Trafic={qev_result.normalized_traffic_score:.3f}, "
                     f"S_Vert={qev_result.normalized_green_score:.3f}")
        logger.info(f"✅ QeV = {qev_result.qev_score:.3f} ({qev_result.qev_category}) "
                     f"[confiance: {qev_result.confidence_level}]")
        logger.info("=" * 60)

        return result

    # ========== MÉTHODES PRIVÉES ==========

    def _prepare_air_quality_data(
        self,
        air_quality_df: Optional[pd.DataFrame]
    ) -> AirQualityData:
        """
        Prépare les données air quality à partir du DataFrame.

        Args:
            air_quality_df: DataFrame avec colonnes pm10, pm2_5, nitrogen_dioxide, ozone, sulphur_dioxide

        Returns:
            AirQualityData
        """
        if air_quality_df is None or air_quality_df.empty:
            logger.warning("Pas de données air quality, utilisation valeurs par défaut")
            return AirQualityData()

        # Calculer moyennes des polluants
        return AirQualityData(
            no2=air_quality_df['nitrogen_dioxide'].mean() if 'nitrogen_dioxide' in air_quality_df else None,
            pm25=air_quality_df['pm2_5'].mean() if 'pm2_5' in air_quality_df else None,
            pm10=air_quality_df['pm10'].mean() if 'pm10' in air_quality_df else None,
            o3=air_quality_df['ozone'].mean() if 'ozone' in air_quality_df else None,
            so2=air_quality_df['sulphur_dioxide'].mean() if 'sulphur_dioxide' in air_quality_df else None
        )

    def _estimate_traffic_from_osm(self, latitude: float, longitude: float) -> Optional[Dict]:
        """
        Estime le trafic via l'API Overpass (type de route OSM).

        Args:
            latitude: Latitude
            longitude: Longitude

        Returns:
            Dict avec light_vehicles, utility_vehicles, heavy_vehicles ou None
        """
        try:
            result = estimate_traffic_from_osm(latitude, longitude)
            if result:
                logger.info(f"Trafic estimé via OSM: route {result.get('road_type', '?')}")
                return result
        except Exception as e:
            logger.warning(f"Erreur estimation trafic OSM: {e}")

        return None

    def _prepare_traffic_data(self, traffic_data: Optional[Dict]) -> TrafficData:
        """
        Prépare les données trafic.

        Args:
            traffic_data: Dict avec light_vehicles, utility_vehicles, heavy_vehicles

        Returns:
            TrafficData
        """
        if traffic_data is None:
            logger.warning("Pas de données trafic (OSM et manuelles indisponibles), utilisation estimation par défaut")
            # Fallback si Overpass aussi a échoué
            return TrafficData(
                light_vehicles=100,   # 100 voitures/h
                utility_vehicles=20,  # 20 utilitaires/h
                heavy_vehicles=5      # 5 poids lourds/h
            )

        return TrafficData(
            light_vehicles=traffic_data.get('light_vehicles', 0),
            utility_vehicles=traffic_data.get('utility_vehicles', 0),
            heavy_vehicles=traffic_data.get('heavy_vehicles', 0)
        )

    def _air_data_to_dict(self, air_data: AirQualityData) -> Dict:
        """Convertit AirQualityData en dict"""
        return {
            'no2': air_data.no2,
            'pm25': air_data.pm25,
            'pm10': air_data.pm10,
            'o3': air_data.o3,
            'so2': air_data.so2
        }

    def _traffic_data_to_dict(self, traffic_data: TrafficData) -> Dict:
        """Convertit TrafficData en dict"""
        return {
            'light_vehicles': traffic_data.light_vehicles,
            'utility_vehicles': traffic_data.utility_vehicles,
            'heavy_vehicles': traffic_data.heavy_vehicles
        }

    def _get_interpretation(self, qev_score: float) -> str:
        """
        Fournit une interprétation détaillée du score QeV.

        Args:
            qev_score: Score QeV (0-1)

        Returns:
            Texte d'interprétation
        """
        if qev_score >= 0.8:
            return (
                "🟢 Excellent - Environnement très favorable à la santé. "
                "Qualité de l'air optimale, faible impact du trafic, et espaces verts accessibles."
            )
        elif qev_score >= 0.6:
            return (
                "🟡 Bon - Qualité environnementale satisfaisante. "
                "Environnement globalement sain avec quelques marges d'amélioration."
            )
        elif qev_score >= 0.4:
            return (
                "🟠 Modéré - Certains facteurs de risque présents. "
                "Impact modéré sur la santé, recommandé d'améliorer certaines dimensions."
            )
        elif qev_score >= 0.2:
            return (
                "🔴 Médiocre - Environnement défavorable à la santé. "
                "Exposition significative à des facteurs de risque environnementaux."
            )
        else:
            return (
                "⛔ Très mauvais - Risques sanitaires significatifs. "
                "Environnement fortement dégradé nécessitant des actions urgentes."
            )


# ============================================================
# EXPORT
# ============================================================

__all__ = ['QeVService']
