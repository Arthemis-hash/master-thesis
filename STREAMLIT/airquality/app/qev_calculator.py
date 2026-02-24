#!/usr/bin/env python3
"""
============================================================
CALCULATEUR QeV - Qualité Environnementale de Vie
============================================================
Implémentation conforme aux spécifications Qev-tech.md
Méthodologie: BelAQI + EMEP/EEA + Règle 3-30-300
============================================================
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import math

logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES SCIENTIFIQUES (Qev-tech.md)
# ============================================================

# Seuils BelAQI pour polluants (µg/m³) → Index 1-10
BELAQI_BREAKPOINTS = {
    "NO2": [
        (0, 10, 1), (10, 20, 2), (20, 30, 3), (30, 40, 4), (40, 50, 5),
        (50, 70, 6), (70, 100, 7), (100, 150, 8), (150, 200, 9), (200, float('inf'), 10)
    ],
    "PM25": [
        (0, 5, 1), (5, 10, 2), (10, 15, 3), (15, 20, 4), (20, 25, 5),
        (25, 35, 6), (35, 50, 7), (50, 70, 8), (70, 100, 9), (100, float('inf'), 10)
    ],
    "PM10": [
        (0, 10, 1), (10, 20, 2), (20, 30, 3), (30, 40, 4), (40, 50, 5),
        (50, 70, 6), (70, 100, 7), (100, 150, 8), (150, 200, 9), (200, float('inf'), 10)
    ],
    "O3": [
        (0, 25, 1), (25, 50, 2), (50, 70, 3), (70, 90, 4), (90, 110, 5),
        (110, 145, 6), (145, 180, 7), (180, 240, 8), (240, 300, 9), (300, float('inf'), 10)
    ],
    "SO2": [
        (0, 25, 1), (25, 50, 2), (50, 75, 3), (75, 100, 4), (100, 150, 5),
        (150, 200, 6), (200, 300, 7), (300, 400, 8), (400, 500, 9), (500, float('inf'), 10)
    ]
}

# Coefficients EMEP/EEA 2019 pour trafic (facteurs d'émission équivalent-nuisance)
TRAFFIC_WEIGHTS = {
    'light': 1.0,       # Voitures particulières (référence)
    'utility': 3.2,     # Utilitaires légers (diesel ancien prédominant)
    'heavy': 12.5       # Poids lourds (bruit logarithmique + NOx massif)
}

# Pondérations globales QeV (Sciensano 2018, EEA 2020)
QEV_WEIGHTS = {
    'air': 0.50,        # 50% - Premier facteur de risque (60-70% DALYs environnementaux)
    'traffic': 0.25,    # 25% - Nuisances non-chimiques (bruit, stress)
    'green': 0.25       # 25% - Facteur protecteur/atténuateur
}

# Bornes de normalisation (min, max) pour calcul Min-Max
NORMALIZATION_BOUNDS = {
    'air_index': (1, 10),           # BelAQI range
    'traffic_nuisance': (0, 5000),  # Unités de nuisance (à ajuster selon contexte)
    'green_index': (0, 1)           # Déjà normalisé 0-1
}


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class AirQualityData:
    """Données de qualité de l'air pour le calcul"""
    no2: Optional[float] = None          # µg/m³
    pm25: Optional[float] = None         # µg/m³
    pm10: Optional[float] = None         # µg/m³
    o3: Optional[float] = None           # µg/m³
    so2: Optional[float] = None          # µg/m³


@dataclass
class TrafficData:
    """Données de trafic pour le calcul"""
    light_vehicles: int = 0              # Voitures/heure
    utility_vehicles: int = 0            # Utilitaires/heure
    heavy_vehicles: int = 0              # Poids lourds/heure


@dataclass
class GreenSpaceData:
    """Données espaces verts pour règle 3-30-300"""
    trees_visible: int = 0                      # Nombre d'arbres visibles
    canopy_coverage_pct: float = 0.0           # % couverture canopée
    distance_to_green_space_m: float = 999.0   # Distance au parc (m)


@dataclass
class QeVResult:
    """Résultat complet du calcul QeV"""
    # Scores bruts
    raw_air_index: float
    raw_air_sub_indices: Dict[str, float]
    raw_traffic_nuisance: float
    raw_green_index: float

    # Scores normalisés (0-1)
    normalized_air_score: float
    normalized_traffic_score: float
    normalized_green_score: float

    # Score final
    qev_score: float
    qev_category: str

    # Métadonnées
    weights: Dict[str, float]
    data_completeness: float
    confidence_level: float
    calculation_timestamp: str

    def to_dict(self) -> Dict:
        """Convertit en dictionnaire pour stockage DB"""
        return asdict(self)


# ============================================================
# FONCTIONS DE CALCUL - QUALITÉ DE L'AIR (BelAQI)
# ============================================================

def interpolate_to_index(concentration: float, breakpoints: list) -> float:
    """
    Interpole linéairement la concentration vers un sous-indice BelAQI.
    Méthode US EPA / EEA standard.

    Args:
        concentration: Valeur mesurée en µg/m³
        breakpoints: Liste de tuples (min, max, index)

    Returns:
        Sous-indice interpolé (valeur continue 1-10)
    """
    if concentration is None or math.isnan(concentration):
        return 1.0  # Valeur par défaut si données manquantes

    for low, high, index in breakpoints:
        if low <= concentration < high:
            # Interpolation linéaire dans l'intervalle
            if high == float('inf'):
                return 10.0
            fraction = (concentration - low) / (high - low)
            return index - 1 + fraction  # Index continu

    return 10.0  # Valeur max si hors limites


def calculate_air_index(air_data: AirQualityData) -> Tuple[float, Dict[str, float]]:
    """
    Calcule l'indice de qualité de l'air selon BelAQI.

    Principe: L'indice global = MAX de tous les sous-indices polluants (facteur limitant).
    Justification: Évite qu'un polluant faible masque un polluant dangereux.

    Args:
        air_data: Données de qualité de l'air

    Returns:
        (index_global, dict_sous_indices)
        - index_global: Index 1-10 (1=Excellent, 10=Extrêmement mauvais)
        - dict_sous_indices: Sous-indices pour chaque polluant
    """
    sub_indices = {}

    # Calculer sous-indices pour chaque polluant
    if air_data.no2 is not None:
        sub_indices['no2'] = interpolate_to_index(air_data.no2, BELAQI_BREAKPOINTS['NO2'])

    if air_data.pm25 is not None:
        sub_indices['pm25'] = interpolate_to_index(air_data.pm25, BELAQI_BREAKPOINTS['PM25'])

    if air_data.pm10 is not None:
        sub_indices['pm10'] = interpolate_to_index(air_data.pm10, BELAQI_BREAKPOINTS['PM10'])

    if air_data.o3 is not None:
        sub_indices['o3'] = interpolate_to_index(air_data.o3, BELAQI_BREAKPOINTS['O3'])

    if air_data.so2 is not None:
        sub_indices['so2'] = interpolate_to_index(air_data.so2, BELAQI_BREAKPOINTS['SO2'])

    # Méthode du maximum (facteur limitant)
    if sub_indices:
        global_index = max(sub_indices.values())
    else:
        global_index = 1.0  # Pas de données = meilleur cas par défaut

    return global_index, sub_indices


# ============================================================
# FONCTIONS DE CALCUL - TRAFIC (EMEP/EEA)
# ============================================================

def calculate_traffic_index(traffic_data: TrafficData) -> float:
    """
    Calcule l'indice de charge de trafic en Unités de Nuisance.

    Facteurs de pondération EMEP/EEA 2019:
    - Voiture particulière: 1.0 (référence)
    - Utilitaire léger: 3.2 (diesel ancien dominant)
    - Poids lourd: 12.5 (bruit logarithmique + NOx massif)

    Args:
        traffic_data: Données de comptages véhicules

    Returns:
        Score de nuisance total (unités arbitraires)
    """
    nuisance = (
        traffic_data.light_vehicles * TRAFFIC_WEIGHTS['light'] +
        traffic_data.utility_vehicles * TRAFFIC_WEIGHTS['utility'] +
        traffic_data.heavy_vehicles * TRAFFIC_WEIGHTS['heavy']
    )

    return nuisance


# ============================================================
# FONCTIONS DE CALCUL - VÉGÉTATION (Règle 3-30-300)
# ============================================================

def calculate_green_index(green_data: GreenSpaceData) -> Tuple[float, Dict[str, float]]:
    """
    Calcule l'indice de verdure selon la règle 3-30-300 (Konijnendijk 2022).

    Trois composantes à poids égaux:
    1. Visibilité: 3 arbres minimum (santé mentale)
    2. Canopée: 30% couverture (régulation thermique)
    3. Accessibilité: 300m max vers espace vert (activité physique)

    Args:
        green_data: Données espaces verts

    Returns:
        (score_global, dict_composantes)
        - score_global: Score entre 0 et 1
        - dict_composantes: Scores des 3 composantes
    """
    # Composante 1: Visibilité (binaire avec seuil à 3)
    score_visibility = 1.0 if green_data.trees_visible >= 3 else 0.0

    # Composante 2: Canopée (saturé à 30%)
    score_canopy = min(green_data.canopy_coverage_pct / 30.0, 1.0)

    # Composante 3: Distance (binaire, seuil 300m)
    score_distance = 1.0 if green_data.distance_to_green_space_m <= 300 else 0.0

    # Moyenne des trois composantes
    global_score = (score_visibility + score_canopy + score_distance) / 3.0

    components = {
        'visibility': score_visibility,
        'canopy': score_canopy,
        'accessibility': score_distance
    }

    return global_score, components


# ============================================================
# NORMALISATION DES SCORES
# ============================================================

def normalize_score(
    value: float,
    min_val: float,
    max_val: float,
    is_negative: bool = False
) -> float:
    """
    Normalise une valeur brute vers [0, 1].

    Args:
        value: Valeur brute
        min_val: Minimum observé/théorique
        max_val: Maximum observé/théorique
        is_negative: True si valeur haute = mauvais (pollution, trafic)

    Returns:
        Score normalisé [0, 1] où 1 = optimal
    """
    # Normalisation Min-Max standard
    if max_val == min_val:
        normalized = 0.5  # Valeur neutre si pas de variation
    else:
        normalized = (value - min_val) / (max_val - min_val)

    # Clamp [0, 1]
    normalized = max(0.0, min(1.0, normalized))

    # Inversion pour indicateurs négatifs
    if is_negative:
        return 1.0 - normalized

    return normalized


# ============================================================
# AGRÉGATION FINALE - SCORE QeV
# ============================================================

def calculate_qev(
    air_data: AirQualityData,
    traffic_data: TrafficData,
    green_data: GreenSpaceData,
    custom_weights: Optional[Dict[str, float]] = None,
    custom_bounds: Optional[Dict[str, Tuple[float, float]]] = None
) -> QeVResult:
    """
    Calcule le score QeV final.

    Pondérations basées sur le Fardeau Environnemental de la Maladie (Sciensano 2018):
    - Air: 50% (premier facteur de risque, 60-70% des DALYs environnementaux)
    - Trafic: 25% (nuisances non-chimiques: bruit, stress)
    - Végétation: 25% (facteur protecteur/atténuateur)

    Args:
        air_data: Données qualité de l'air
        traffic_data: Données trafic
        green_data: Données espaces verts
        custom_weights: Pondérations personnalisées (optionnel)
        custom_bounds: Bornes de normalisation personnalisées (optionnel)

    Returns:
        QeVResult avec tous les scores et métadonnées
    """
    # Utiliser les poids par défaut ou personnalisés
    weights = custom_weights or QEV_WEIGHTS
    bounds = custom_bounds or NORMALIZATION_BOUNDS

    # ========== CALCUL DES SOUS-INDICATEURS BRUTS ==========
    raw_air_index, air_sub_indices = calculate_air_index(air_data)
    raw_traffic_nuisance = calculate_traffic_index(traffic_data)
    raw_green_index, green_components = calculate_green_index(green_data)

    # ========== NORMALISATION DES SCORES ==========
    # Air: Normaliser de [1, 10] vers [0, 1] puis inverser (1 = bon)
    s_air = normalize_score(
        raw_air_index,
        bounds['air_index'][0],
        bounds['air_index'][1],
        is_negative=True
    )

    # Trafic: Normaliser et inverser (1 = faible trafic = bon)
    s_traffic = normalize_score(
        raw_traffic_nuisance,
        bounds['traffic_nuisance'][0],
        bounds['traffic_nuisance'][1],
        is_negative=True
    )

    # Végétation: Déjà normalisé [0, 1] où 1 = bon
    s_green = raw_green_index

    # ========== AGRÉGATION PONDÉRÉE FINALE ==========
    qev_score = (
        weights['air'] * s_air +
        weights['traffic'] * s_traffic +
        weights['green'] * s_green
    )

    # ========== CATÉGORISATION ==========
    qev_category = interpret_qev_score(qev_score)

    # ========== MÉTADONNÉES ==========
    # Calculer complétude des données
    data_completeness = calculate_data_completeness(air_data, traffic_data, green_data)

    # Calculer niveau de confiance
    confidence_level = calculate_confidence_level(air_data, traffic_data, green_data)

    # ========== RÉSULTAT FINAL ==========
    return QeVResult(
        raw_air_index=raw_air_index,
        raw_air_sub_indices=air_sub_indices,
        raw_traffic_nuisance=raw_traffic_nuisance,
        raw_green_index=raw_green_index,
        normalized_air_score=s_air,
        normalized_traffic_score=s_traffic,
        normalized_green_score=s_green,
        qev_score=qev_score,
        qev_category=qev_category,
        weights=weights,
        data_completeness=data_completeness,
        confidence_level=confidence_level,
        calculation_timestamp=datetime.now().isoformat()
    )


def interpret_qev_score(qev: float) -> str:
    """
    Interprète le score QeV en catégorie qualitative.

    Args:
        qev: Score QeV (0-1)

    Returns:
        Catégorie textuelle
    """
    if qev >= 0.8:
        return "Excellent"
    elif qev >= 0.6:
        return "Bon"
    elif qev >= 0.4:
        return "Modéré"
    elif qev >= 0.2:
        return "Médiocre"
    else:
        return "Très mauvais"


def calculate_data_completeness(
    air_data: AirQualityData,
    traffic_data: TrafficData,
    green_data: GreenSpaceData
) -> float:
    """
    Calcule le % de données disponibles.

    Returns:
        Complétude entre 0 et 1
    """
    total_fields = 0
    available_fields = 0

    # Air quality (5 polluants)
    air_fields = [air_data.no2, air_data.pm25, air_data.pm10, air_data.o3, air_data.so2]
    total_fields += len(air_fields)
    available_fields += sum(1 for f in air_fields if f is not None)

    # Traffic (3 catégories)
    traffic_fields = [
        traffic_data.light_vehicles,
        traffic_data.utility_vehicles,
        traffic_data.heavy_vehicles
    ]
    total_fields += len(traffic_fields)
    available_fields += sum(1 for f in traffic_fields if f > 0)

    # Green (3 métriques)
    green_fields = [
        green_data.trees_visible,
        green_data.canopy_coverage_pct,
        green_data.distance_to_green_space_m
    ]
    total_fields += len(green_fields)
    available_fields += sum(1 for f in green_fields if f is not None and f != 999.0)

    return available_fields / total_fields if total_fields > 0 else 0.0


def calculate_confidence_level(
    air_data: AirQualityData,
    traffic_data: TrafficData,
    green_data: GreenSpaceData
) -> float:
    """
    Calcule le niveau de confiance global (0-1).
    Basé sur la complétude et la cohérence des données.

    Returns:
        Niveau de confiance entre 0 et 1
    """
    # Pour l'instant, utiliser la complétude comme proxy
    # Peut être enrichi avec des métriques de qualité des données
    return calculate_data_completeness(air_data, traffic_data, green_data)


# ============================================================
# EXPORT
# ============================================================

__all__ = [
    'AirQualityData',
    'TrafficData',
    'GreenSpaceData',
    'QeVResult',
    'calculate_qev',
    'calculate_air_index',
    'calculate_traffic_index',
    'calculate_green_index',
    'interpret_qev_score',
    'BELAQI_BREAKPOINTS',
    'TRAFFIC_WEIGHTS',
    'QEV_WEIGHTS',
    'NORMALIZATION_BOUNDS'
]
