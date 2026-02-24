#!/usr/bin/env python3
"""
Utilitaires communs - Fonctions partagées
Centralisation pour éviter doublons et améliorer maintenabilité
"""

from math import radians, sin, cos, sqrt, atan2
from typing import Optional, Dict, Union
from dataclasses import is_dataclass, asdict


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule distance haversine entre deux points géographiques
    
    Args:
        lat1, lon1: Coordonnées point 1
        lat2, lon2: Coordonnées point 2
        
    Returns:
        Distance en mètres
    """
    R = 6371000  # Rayon terrestre en mètres
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c


def wind_direction_to_text(degrees: Optional[int]) -> str:
    """
    Convertit direction vent (degrés) en texte cardinal
    
    Args:
        degrees: Direction en degrés (0-360)
        
    Returns:
        Direction textuelle (N, NE, E, etc.)
    """
    if degrees is None:
        return "N/A"
    
    directions = [
        "N", "NNE", "NE", "ENE", 
        "E", "ESE", "SE", "SSE",
        "S", "SSO", "SO", "OSO", 
        "O", "ONO", "NO", "NNO"
    ]
    index = round(degrees / 22.5) % 16
    return directions[index]


def safe_to_dict(obj: Union[Dict, object]) -> Dict:
    """
    Conversion sécurisée en dictionnaire
    
    Args:
        obj: Objet à convertir (dict, dataclass, ou autre)
        
    Returns:
        Dictionnaire
    """
    if isinstance(obj, dict):
        return obj
    
    if is_dataclass(obj):
        return asdict(obj)
    
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    
    # Fallback: attributs publics
    return {
        k: v for k, v in vars(obj).items() 
        if not k.startswith('_')
    }


def format_optional_value(value: Optional[float], unit: str = "", decimals: int = 1) -> str:
    """
    Formate valeur optionnelle avec unité
    
    Args:
        value: Valeur à formater
        unit: Unité (optionnel)
        decimals: Nombre de décimales
        
    Returns:
        Valeur formatée ou "N/A"
    """
    if value is None:
        return "N/A"
    
    if isinstance(value, (int, float)):
        formatted = f"{value:.{decimals}f}"
        return f"{formatted} {unit}".strip()
    
    return str(value)


def safe_float_conversion(value, default: float = 0.0) -> float:
    """
    Conversion sécurisée vers float
    
    Args:
        value: Valeur à convertir
        default: Valeur par défaut si conversion échoue
        
    Returns:
        Valeur float
    """
    if value is None:
        return default
    
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def truncate_string(text: Optional[str], max_length: int = 50) -> str:
    """
    Tronque chaîne de caractères avec ellipse
    
    Args:
        text: Texte à tronquer
        max_length: Longueur maximale
        
    Returns:
        Texte tronqué
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."


def get_color_by_value(value: float, thresholds: Dict[str, float]) -> str:
    """
    Détermine couleur selon seuils de valeurs
    
    Args:
        value: Valeur à évaluer
        thresholds: Dict avec 'good', 'moderate', 'bad', 'dangerous'
        
    Returns:
        Code couleur hex
    """
    if value <= thresholds.get('good', 0):
        return "#00E400"  # Vert
    elif value <= thresholds.get('moderate', 50):
        return "#FFFF00"  # Jaune
    elif value <= thresholds.get('bad', 100):
        return "#FF7E00"  # Orange
    elif value <= thresholds.get('dangerous', 150):
        return "#FF0000"  # Rouge
    else:
        return "#99004C"  # Marron foncé


def validate_coordinates(lat: float, lon: float) -> bool:
    """
    Valide coordonnées géographiques
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        True si valides
    """
    return -90 <= lat <= 90 and -180 <= lon <= 180


def calculate_percentage_change(old_value: float, new_value: float) -> Optional[float]:
    """
    Calcule variation en pourcentage
    
    Args:
        old_value: Ancienne valeur
        new_value: Nouvelle valeur
        
    Returns:
        Variation en % ou None si impossible
    """
    if old_value == 0:
        return None
    
    return ((new_value - old_value) / old_value) * 100
