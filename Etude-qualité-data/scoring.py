#!/usr/bin/env python3
"""
Calcul des scores de qualité de l'air selon normes européennes
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple


# Seuils OMS et UE (µg/m³)
AIR_QUALITY_THRESHOLDS = {
    'pm2_5': {
        'excellent': 10,
        'good': 20,
        'moderate': 25,
        'poor': 50,
        'very_poor': 75
    },
    'pm10': {
        'excellent': 20,
        'good': 40,
        'moderate': 50,
        'poor': 100,
        'very_poor': 150
    },
    'no2': {
        'excellent': 40,
        'good': 90,
        'moderate': 120,
        'poor': 230,
        'very_poor': 340
    },
    'o3': {
        'excellent': 50,
        'good': 100,
        'moderate': 130,
        'poor': 240,
        'very_poor': 380
    }
}


def calculate_pollutant_score(pollutant: str, value: float) -> Tuple[int, str]:
    """
    Calcule score 0-100 et catégorie pour un polluant
    
    Returns:
        (score, catégorie) où score=100 est excellent
    """
    if pollutant not in AIR_QUALITY_THRESHOLDS or pd.isna(value):
        return 50, 'unknown'
    
    thresholds = AIR_QUALITY_THRESHOLDS[pollutant]
    
    if value <= thresholds['excellent']:
        score = 100
        category = 'excellent'
    elif value <= thresholds['good']:
        score = 80
        category = 'good'
    elif value <= thresholds['moderate']:
        score = 60
        category = 'moderate'
    elif value <= thresholds['poor']:
        score = 40
        category = 'poor'
    elif value <= thresholds['very_poor']:
        score = 20
        category = 'very_poor'
    else:
        score = 0
        category = 'hazardous'
    
    return score, category


def calculate_global_aqi(pollutant_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Calcule l'indice global de qualité de l'air (AQI)
    
    Args:
        pollutant_data: Dict {pollutant: DataFrame}
    
    Returns:
        DataFrame avec scores temporels
    """
    all_scores = []
    
    for pollutant, df in pollutant_data.items():
        if df.empty:
            continue
            
        df_scores = df.copy()
        df_scores['score'] = df_scores['value'].apply(
            lambda x: calculate_pollutant_score(pollutant, x)[0]
        )
        df_scores['category'] = df_scores['value'].apply(
            lambda x: calculate_pollutant_score(pollutant, x)[1]
        )
        
        all_scores.append(df_scores[['timestamp', 'pollutant', 'value', 'score', 'category']])
    
    if not all_scores:
        return pd.DataFrame()
    
    combined = pd.concat(all_scores, ignore_index=True)
    
    # Agrégation par timestamp (score = min des polluants présents)
    aqi = combined.groupby('timestamp').agg({
        'score': 'min',  # Le pire polluant détermine la qualité
        'category': lambda x: x.iloc[x.argmin()]
    }).reset_index()
    
    return aqi.sort_values('timestamp')


def get_health_recommendations(category: str) -> Dict[str, str]:
    """Recommandations santé selon catégorie"""
    
    recommendations = {
        'excellent': {
            'message': 'Qualité de l\'air excellente',
            'advice': 'Conditions idéales pour toutes activités extérieures.',
            'color': '#00e400'
        },
        'good': {
            'message': 'Qualité de l\'air bonne',
            'advice': 'Aucune restriction pour les activités extérieures.',
            'color': '#92d050'
        },
        'moderate': {
            'message': 'Qualité de l\'air modérée',
            'advice': 'Acceptable. Personnes sensibles: limitez efforts prolongés.',
            'color': '#ffff00'
        },
        'poor': {
            'message': 'Qualité de l\'air médiocre',
            'advice': 'Réduisez activités intenses. Groupes sensibles: restez à l\'intérieur.',
            'color': '#ff7e00'
        },
        'very_poor': {
            'message': 'Qualité de l\'air très médiocre',
            'advice': 'Évitez activités extérieures. Fermez les fenêtres.',
            'color': '#ff0000'
        },
        'hazardous': {
            'message': 'Qualité de l\'air dangereuse',
            'advice': 'Urgence sanitaire. Restez à l\'intérieur.',
            'color': '#99004c'
        }
    }
    
    return recommendations.get(category, recommendations['moderate'])