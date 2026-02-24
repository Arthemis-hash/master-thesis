#!/usr/bin/env python3
"""
============================================================
ANALYSEUR ESPACES VERTS - Règle 3-30-300
============================================================
Analyse YOLO + Segmentation + OSM pour métriques végétation
Implémente la règle 3-30-300 (Konijnendijk 2022)
============================================================
"""

import logging
import json
import os
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import math
import re

logger = logging.getLogger(__name__)

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",  # Alternative server
]

OVERPASS_MAX_RETRIES = 2          # 2 essais par serveur (4 serveurs = 8 essais max)
OVERPASS_RETRY_DELAY_S = 3        # Délai initial entre retries
OVERPASS_TOTAL_TIMEOUT_S = 45     # Timeout total pour tous les serveurs combinés

# Circuit breaker: évite de réessayer Overpass si tous les serveurs ont échoué récemment
_overpass_circuit_open = False
_overpass_last_failure_time = 0
OVERPASS_CIRCUIT_RESET_S = 120    # Réessayer après 2 minutes



def _overpass_request(query: str, timeout: int = 15) -> dict:
    """
    Envoie une requête Overpass avec retry et fallback sur serveurs alternatifs.
    Timeout total de 45s pour éviter de bloquer le flux de recherche.
    Utilise un backoff exponentiel pour les retries.
    Implémente un circuit breaker pour éviter les attentes répétées.

    Args:
        query: Requête Overpass QL
        timeout: Timeout HTTP par requête en secondes

    Returns:
        dict JSON de la réponse Overpass

    Raises:
        requests.exceptions.RequestException: Si tous les serveurs échouent
    """
    global _overpass_circuit_open, _overpass_last_failure_time
    
    # Vérifier le circuit breaker
    if _overpass_circuit_open:
        time_since_failure = time.time() - _overpass_last_failure_time
        if time_since_failure < OVERPASS_CIRCUIT_RESET_S:
            logger.warning(f"⚡ Circuit breaker actif - Overpass indisponible "
                          f"(réessai dans {OVERPASS_CIRCUIT_RESET_S - time_since_failure:.0f}s)")
            raise requests.exceptions.RequestException(
                "Circuit breaker: Overpass temporairement indisponible"
            )
        else:
            # Réinitialiser le circuit breaker
            logger.info("🔄 Circuit breaker réinitialisé, tentative Overpass...")
            _overpass_circuit_open = False
    
    last_error = None
    start_time = time.time()
    servers_tried = 0

    for server_url in OVERPASS_SERVERS:
        servers_tried += 1
        # Vérifier le timeout total
        elapsed = time.time() - start_time
        if elapsed >= OVERPASS_TOTAL_TIMEOUT_S:
            logger.warning(f"Overpass: timeout total de {OVERPASS_TOTAL_TIMEOUT_S}s dépassé après {servers_tried} serveurs")
            break

        for attempt in range(1, OVERPASS_MAX_RETRIES + 1):
            elapsed = time.time() - start_time
            remaining = OVERPASS_TOTAL_TIMEOUT_S - elapsed
            if remaining <= 3:
                logger.warning("Overpass: plus de temps restant pour d'autres tentatives")
                break

            try:
                req_timeout = min(timeout, remaining - 1)
                logger.debug(f"Overpass requête → {server_url} (essai {attempt}/{OVERPASS_MAX_RETRIES}, timeout={req_timeout:.0f}s)")
                response = requests.post(server_url, data={'data': query}, timeout=req_timeout)
                response.raise_for_status()
                logger.debug(f"✅ Overpass succès via {server_url}")
                # Succès - réinitialiser le circuit breaker si nécessaire
                _overpass_circuit_open = False
                return response.json()

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_error = e
                logger.warning(f"Overpass timeout/connexion ({server_url}, essai {attempt})")
                if attempt < OVERPASS_MAX_RETRIES:
                    # Exponential backoff: 3s, 6s, 12s...
                    backoff_delay = OVERPASS_RETRY_DELAY_S * (2 ** (attempt - 1))
                    time.sleep(min(backoff_delay, remaining - 2))

            except requests.exceptions.HTTPError as e:
                last_error = e
                status = getattr(e.response, 'status_code', None)
                if status in (429, 504, 502, 503):
                    logger.warning(f"Overpass erreur {status} ({server_url}, essai {attempt})")
                    if attempt < OVERPASS_MAX_RETRIES:
                        # Pour 504/502/503, attendre plus longtemps (serveur surchargé)
                        backoff_delay = OVERPASS_RETRY_DELAY_S * (2 ** attempt)
                        time.sleep(min(backoff_delay, remaining - 2))
                else:
                    # Autres erreurs HTTP: ne pas réessayer
                    raise

        logger.info(f"Serveur {server_url} épuisé ({OVERPASS_MAX_RETRIES} essais), passage au suivant...")

    # Tous les serveurs ont échoué - activer le circuit breaker
    _overpass_circuit_open = True
    _overpass_last_failure_time = time.time()
    logger.warning(f"⚡ Circuit breaker ACTIVÉ - tous les serveurs Overpass ont échoué")
    
    raise requests.exceptions.RequestException(
        f"Tous les {len(OVERPASS_SERVERS)} serveurs Overpass ont échoué "
        f"(temps écoulé: {time.time() - start_time:.1f}s). "
        f"Dernière erreur: {last_error}"
    )


# ============================================================
# CONSTANTES
# ============================================================

# Seuils règle 3-30-300
MIN_TREES_VISIBLE = 3
TARGET_CANOPY_PCT = 30.0
MAX_PARK_DISTANCE_M = 300.0

# Rayon d'analyse pour canopée
CANOPY_ANALYSIS_RADIUS_M = 500


# ============================================================
# ANALYSE YOLO - DÉTECTION D'ARBRES
# ============================================================

def analyze_trees_from_yolo(
    address: str,
    yolo_results_dir: Optional[str] = None
) -> Dict[str, int]:
    """
    Analyse les résultats YOLO pour compter les arbres visibles.

    Args:
        address: Adresse à analyser
        yolo_results_dir: Dossier contenant les résultats YOLO

    Returns:
        Dict avec nombre d'arbres par type d'image
    """
    base_dir = Path(__file__).parent / "environment_data" / "yolo_results"

    # Normaliser l'adresse
    try:
        from db_async_wrapper import DatabaseManager
        normalized_address = DatabaseManager.sanitize_address(address)
    except ImportError:
        import re
        normalized_address = re.sub(r'[^\w\s-]', '', address.lower())
        normalized_address = re.sub(r'[\s_-]+', '_', normalized_address).strip('_')

    tree_counts = {
        'total_trees': 0,
        'detection_arbres': 0,
        'detection_general': 0,
        'images_analyzed': 0
    }

    # Chercher d'abord dans le sous-dossier de l'adresse, puis fallback global
    if yolo_results_dir is not None:
        search_dirs = [Path(yolo_results_dir)]
    else:
        search_dirs = [
            base_dir / normalized_address,  # Dossier par adresse (prioritaire)
            base_dir                        # Fallback global (backward compat)
        ]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        # Analyser les résultats de détection d'arbres
        arbres_dir = search_dir / "detection_arbres"
        if arbres_dir.exists():
            tree_count = count_trees_in_yolo_results(arbres_dir)
            tree_counts['detection_arbres'] = tree_count
            tree_counts['total_trees'] += tree_count

        # Analyser les résultats de détection générale
        general_dir = search_dir / "detection_général"
        if general_dir.exists():
            tree_count = count_trees_in_yolo_results(general_dir)
            tree_counts['detection_general'] = tree_count

        # Utiliser le maximum des deux détections
        tree_counts['total_trees'] = max(
            tree_counts['detection_arbres'],
            tree_counts['detection_general']
        )

        # Si on a trouvé des résultats, pas besoin de chercher dans le fallback
        if tree_counts['total_trees'] > 0:
            logger.info(f"Arbres détectés: {tree_counts['total_trees']} (source: {search_dir})")
            return tree_counts

    logger.info(f"Arbres détectés: {tree_counts['total_trees']}")
    return tree_counts


def count_trees_in_yolo_results(results_dir: Path) -> int:
    """
    Compte les arbres dans un dossier de résultats YOLO.

    Args:
        results_dir: Dossier contenant les images annotées YOLO

    Returns:
        Nombre total d'arbres détectés
    """
    # Pour l'instant, compter les images contenant des détections
    # Dans une version future, parser les fichiers .txt de labels YOLO
    # ou utiliser les métadonnées JSON si disponibles

    tree_count = 0
    images_found = 0

    # Chercher les fichiers image
    for ext in ['*.jpg', '*.png', '*.jpeg']:
        images = list(results_dir.glob(ext))
        images_found += len(images)

    # Heuristique simple: si des images existent dans le dossier detection_arbres,
    # supposer qu'il y a au moins MIN_TREES_VISIBLE arbres
    # TODO: Implémenter parsing des labels YOLO pour comptage précis
    if images_found > 0:
        # Estimation conservative: 1-2 arbres par image en moyenne
        tree_count = max(images_found // 2, MIN_TREES_VISIBLE)

    return tree_count


def parse_yolo_labels(label_file: Path) -> List[Dict]:
    """
    Parse un fichier de labels YOLO (.txt).

    Format YOLO: class_id center_x center_y width height

    Args:
        label_file: Chemin vers le fichier .txt de labels

    Returns:
        Liste de dictionnaires avec les détections
    """
    detections = []

    try:
        with open(label_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    detection = {
                        'class_id': int(parts[0]),
                        'center_x': float(parts[1]),
                        'center_y': float(parts[2]),
                        'width': float(parts[3]),
                        'height': float(parts[4]),
                        'confidence': float(parts[5]) if len(parts) > 5 else 1.0
                    }
                    detections.append(detection)
    except Exception as e:
        logger.error(f"Erreur parsing YOLO labels {label_file}: {e}")

    return detections


# ============================================================
# ANALYSE SEGMENTATION - CANOPÉE
# ============================================================

def analyze_canopy_from_segmentation(
    address: str,
    segmentation_results_dir: Optional[str] = None
) -> Dict[str, float]:
    """
    Analyse les résultats de segmentation pour calculer la couverture canopée.

    Args:
        address: Adresse à analyser
        segmentation_results_dir: Dossier contenant les résultats

    Returns:
        Dict avec métriques de canopée
    """
    canopy_metrics = {
        'canopy_coverage_pct': 0.0,
        'vegetation_area_m2': 0.0,
        'total_area_analyzed_m2': 0.0,
        'method': 'segmentation'
    }

    # Déterminer le dossier de recherche
    base_dir = Path(__file__).parent / "environment_data" / "map_analysis"

    if segmentation_results_dir is not None:
        search_dirs = [Path(segmentation_results_dir)]
    else:
        # Chercher d'abord dans le sous-dossier de l'adresse, puis fallback global
        try:
            from db_async_wrapper import DatabaseManager
            normalized = DatabaseManager.sanitize_address(address)
        except ImportError:
            import re
            normalized = re.sub(r'[^\w\s-]', '', address.lower())
            normalized = re.sub(r'[\s_-]+', '_', normalized).strip('_')

        search_dirs = [
            base_dir / normalized,  # Dossier par adresse (prioritaire)
            base_dir               # Fallback global (backward compat)
        ]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        # Utiliser pattern glob pour trouver n'importe quel fichier de stats
        # ex: statistics_z17.json, statistics_z19.json
        stats_files = list(search_dir.glob("statistics_z*.json"))
        
        # Trier pour prioriser le zoom le plus élevé (meilleure résolution)
        # On extrait le zoom du nom de fichier
        def get_zoom_level(filepath):
            try:
                # statistics_z18.json -> 18
                match = re.search(r'z(\d+)', filepath.name)
                return int(match.group(1)) if match else 0
            except Exception:
                return 0

        # Tri décroissant (z19 avant z18)
        stats_files.sort(key=get_zoom_level, reverse=True)

        if stats_files:
            logger.info(f"Fichiers stats trouvés dans {search_dir}: {[f.name for f in stats_files]}")
            
            # Essayer les fichiers dans l'ordre
            for stats_file in stats_files:
                try:
                    with open(stats_file, 'r', encoding='utf-8') as f:
                        stats = json.load(f)

                    # Format réel: stats['elements']['green_spaces']['coverage_percent']
                    elements = stats.get('elements', {})
                    green = elements.get('green_spaces', {})

                    if green.get('coverage_percent', 0) > 0:
                        canopy_metrics['canopy_coverage_pct'] = green['coverage_percent']
                    elif 'vegetation_pct' in stats:
                        # Fallback ancien format
                        canopy_metrics['canopy_coverage_pct'] = stats['vegetation_pct']

                    if green.get('area_m2', 0) > 0:
                        canopy_metrics['vegetation_area_m2'] = green['area_m2']
                    elif 'vegetation_area_m2' in stats:
                        canopy_metrics['vegetation_area_m2'] = stats['vegetation_area_m2']

                    if 'total_area_m2' in stats:
                        canopy_metrics['total_area_analyzed_m2'] = stats['total_area_m2']

                    logger.info(f"✅ Couverture canopée récupérée: {canopy_metrics['canopy_coverage_pct']:.1f}% "
                               f"(fichier: {stats_file.name})")
                    return canopy_metrics

                except Exception as e:
                    logger.error(f"Erreur lecture stats {stats_file}: {e}")
        else:
             logger.debug(f"Aucun fichier statistics_z*.json dans {search_dir}")

    logger.warning(f"❌ Aucun fichier de statistiques valide trouvé pour '{address}'")
    return canopy_metrics


def estimate_canopy_from_ndvi(
    satellite_image_path: str,
    latitude: float,
    longitude: float,
    radius_m: int = CANOPY_ANALYSIS_RADIUS_M
) -> float:
    """
    Estime la couverture canopée depuis NDVI (Normalized Difference Vegetation Index).

    NDVI = (NIR - RED) / (NIR + RED)

    Note: Nécessite des images satellite avec bandes NIR (Near-Infrared).
    Pour Sentinel-2 ou Landsat.

    Args:
        satellite_image_path: Chemin vers l'image satellite
        latitude: Latitude du point central
        longitude: Longitude du point central
        radius_m: Rayon d'analyse en mètres

    Returns:
        Pourcentage de couverture végétale (0-100)
    """
    # TODO: Implémenter calcul NDVI si images multi-spectrales disponibles
    # Pour l'instant, retourner estimation par défaut
    logger.warning("Calcul NDVI non implémenté, utiliser segmentation RGB à la place")
    return 0.0


# ============================================================
# DISTANCE ESPACES VERTS (OSM + PostGIS)
# ============================================================

def calculate_distance_to_nearest_park(
    latitude: float,
    longitude: float,
    search_radius_m: int = 2000
) -> Tuple[float, Optional[str], Optional[float]]:
    """
    Calcule la distance au parc/espace vert le plus proche via Overpass API.

    Sources:
    - OpenStreetMap (tags: leisure=park, landuse=forest, natural=wood, leisure=garden)

    Args:
        latitude: Latitude du domicile
        longitude: Longitude du domicile
        search_radius_m: Rayon de recherche maximum (m)

    Returns:
        (distance_m, park_name, park_area_m2)
    """
    green_spaces = query_osm_green_spaces(latitude, longitude, search_radius_m)

    if not green_spaces:
        logger.warning(f"Aucun espace vert trouvé dans un rayon de {search_radius_m}m")
        return (999.0, None, None)

    # Le plus proche (déjà trié par distance)
    nearest = green_spaces[0]
    distance_m = nearest['distance_m']
    park_name = nearest['name']

    # L'aire n'est pas disponible via Overpass center query (nécessiterait geom complet)
    park_area_m2 = None

    logger.info(f"Parc le plus proche: {park_name} à {distance_m:.0f}m")
    return (distance_m, park_name, park_area_m2)


def query_osm_green_spaces(
    latitude: float,
    longitude: float,
    radius_m: int = 2000
) -> List[Dict]:
    """
    Interroge OpenStreetMap pour trouver les espaces verts à proximité.

    Args:
        latitude: Latitude du point
        longitude: Longitude du point
        radius_m: Rayon de recherche

    Returns:
        Liste d'espaces verts avec métadonnées
    """
    overpass_query = f"""
    [out:json][timeout:25];
    (
      way["leisure"="park"](around:{radius_m},{latitude},{longitude});
      way["landuse"="forest"](around:{radius_m},{latitude},{longitude});
      way["natural"="wood"](around:{radius_m},{latitude},{longitude});
      way["leisure"="garden"](around:{radius_m},{latitude},{longitude});
      relation["leisure"="park"](around:{radius_m},{latitude},{longitude});
      relation["landuse"="forest"](around:{radius_m},{latitude},{longitude});
    );
    out center tags;
    """

    try:
        data = _overpass_request(overpass_query, timeout=30)

        green_spaces = []
        for element in data.get('elements', []):
            # Récupérer le centre (pour ways/relations, Overpass retourne 'center')
            if 'center' in element:
                el_lat = element['center']['lat']
                el_lon = element['center']['lon']
            elif 'lat' in element and 'lon' in element:
                el_lat = element['lat']
                el_lon = element['lon']
            else:
                continue

            tags = element.get('tags', {})
            name = tags.get('name', tags.get('leisure', tags.get('landuse', 'Espace vert')))

            # Distance haversine
            dist = _haversine_distance(latitude, longitude, el_lat, el_lon)

            green_spaces.append({
                'name': name,
                'latitude': el_lat,
                'longitude': el_lon,
                'distance_m': dist,
                'type': tags.get('leisure', tags.get('landuse', tags.get('natural', 'unknown'))),
                'osm_id': element.get('id')
            })

        # Trier par distance
        green_spaces.sort(key=lambda x: x['distance_m'])
        logger.info(f"Overpass: {len(green_spaces)} espaces verts trouvés dans un rayon de {radius_m}m")
        return green_spaces

    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur Overpass API (espaces verts): {e}")
        return []
    except (KeyError, ValueError) as e:
        logger.error(f"Erreur parsing réponse Overpass: {e}")
        return []


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule la distance en mètres entre deux points GPS (formule haversine)."""
    R = 6371000  # Rayon de la Terre en mètres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# ============================================================
# ESTIMATION TRAFIC VIA OSM
# ============================================================

# Estimation du trafic par type de route OSM (véhicules/heure)
# Basé sur les moyennes européennes pour zones urbaines
TRAFFIC_BY_ROAD_TYPE = {
    'motorway':      {'light': 800, 'utility': 120, 'heavy': 60},
    'trunk':         {'light': 500, 'utility': 80,  'heavy': 30},
    'primary':       {'light': 300, 'utility': 50,  'heavy': 15},
    'secondary':     {'light': 200, 'utility': 40,  'heavy': 10},
    'tertiary':      {'light': 100, 'utility': 20,  'heavy': 5},
    'residential':   {'light': 50,  'utility': 10,  'heavy': 2},
    'living_street': {'light': 10,  'utility': 2,   'heavy': 0},
    'pedestrian':    {'light': 0,   'utility': 0,   'heavy': 0},
    'service':       {'light': 30,  'utility': 8,   'heavy': 1},
    'unclassified':  {'light': 60,  'utility': 12,  'heavy': 3},
}

# Ajustement par nombre de voies
LANES_MULTIPLIER = {
    1: 0.6,
    2: 1.0,
    3: 1.3,
    4: 1.6,
    5: 1.8,
    6: 2.0,
}


def estimate_traffic_from_osm(
    latitude: float,
    longitude: float,
    search_radius_m: int = 100
) -> Optional[Dict]:
    """
    Estime le trafic à partir du type de route OSM le plus proche.

    Args:
        latitude: Latitude du point
        longitude: Longitude du point
        search_radius_m: Rayon de recherche (m)

    Returns:
        Dict avec light_vehicles, utility_vehicles, heavy_vehicles, ou None si erreur
    """
    overpass_query = f"""
    [out:json][timeout:25];
    way["highway"](around:{search_radius_m},{latitude},{longitude});
    out tags 1;
    """

    try:
        data = _overpass_request(overpass_query, timeout=30)

        elements = data.get('elements', [])
        if not elements:
            # Élargir la recherche
            if search_radius_m < 500:
                return estimate_traffic_from_osm(latitude, longitude, search_radius_m * 2)
            logger.warning("Aucune route trouvée via Overpass")
            return None

        # Prendre la première route (la plus proche)
        road = elements[0]
        tags = road.get('tags', {})
        highway_type = tags.get('highway', 'unclassified')

        # Récupérer estimation de base
        base_traffic = TRAFFIC_BY_ROAD_TYPE.get(highway_type, TRAFFIC_BY_ROAD_TYPE['unclassified'])

        # Ajuster par nombre de voies si disponible
        lanes = tags.get('lanes')
        multiplier = 1.0
        if lanes:
            try:
                lanes_int = int(lanes)
                multiplier = LANES_MULTIPLIER.get(lanes_int, min(lanes_int / 2, 2.5))
            except (ValueError, TypeError):
                pass

        result = {
            'light_vehicles': int(base_traffic['light'] * multiplier),
            'utility_vehicles': int(base_traffic['utility'] * multiplier),
            'heavy_vehicles': int(base_traffic['heavy'] * multiplier),
            'source': 'osm_estimation',
            'road_type': highway_type,
            'lanes': lanes,
            'multiplier': multiplier
        }

        logger.info(f"Trafic estimé (route {highway_type}, {lanes or '?'} voies): "
                     f"{result['light_vehicles']}/{result['utility_vehicles']}/{result['heavy_vehicles']} veh/h")
        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur Overpass API (trafic): {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Erreur parsing réponse Overpass (trafic): {e}")
        return None


# ============================================================
# CALCUL RÈGLE 3-30-300 COMPLET
# ============================================================

def calculate_330_rule_metrics(
    address: str,
    latitude: float,
    longitude: float,
    yolo_results_dir: Optional[str] = None,
    segmentation_results_dir: Optional[str] = None
) -> Dict:
    """
    Calcule toutes les métriques de la règle 3-30-300.

    Args:
        address: Adresse à analyser
        latitude: Latitude
        longitude: Longitude
        yolo_results_dir: Dossier résultats YOLO (optionnel)
        segmentation_results_dir: Dossier résultats segmentation (optionnel)

    Returns:
        Dict complet avec toutes les métriques
    """
    metrics = {
        'address': address,
        'latitude': latitude,
        'longitude': longitude
    }

    # ========== COMPOSANTE 1: VISIBILITÉ (3 arbres) ==========
    tree_detection = analyze_trees_from_yolo(address, yolo_results_dir)
    metrics['trees_visible_count'] = tree_detection['total_trees']
    metrics['has_minimum_3_trees'] = tree_detection['total_trees'] >= MIN_TREES_VISIBLE
    metrics['visibility_score'] = 1.0 if metrics['has_minimum_3_trees'] else 0.0

    # ========== COMPOSANTE 2: CANOPÉE (30%) ==========
    canopy_data = analyze_canopy_from_segmentation(address, segmentation_results_dir)
    metrics['canopy_coverage_pct'] = canopy_data['canopy_coverage_pct']
    metrics['canopy_area_m2'] = canopy_data['vegetation_area_m2']
    metrics['total_area_analyzed_m2'] = canopy_data['total_area_analyzed_m2']
    metrics['canopy_score'] = min(canopy_data['canopy_coverage_pct'] / TARGET_CANOPY_PCT, 1.0)

    # ========== COMPOSANTE 3: ACCESSIBILITÉ (300m) ==========
    distance_m, park_name, park_area = calculate_distance_to_nearest_park(latitude, longitude)
    metrics['distance_to_nearest_park_m'] = distance_m
    metrics['nearest_park_name'] = park_name
    metrics['nearest_park_area_m2'] = park_area
    metrics['within_access_radius'] = distance_m <= MAX_PARK_DISTANCE_M
    metrics['accessibility_score'] = 1.0 if metrics['within_access_radius'] else 0.0

    # ========== SCORE GLOBAL RÈGLE 3-30-300 ==========
    metrics['green_index_score'] = (
        metrics['visibility_score'] +
        metrics['canopy_score'] +
        metrics['accessibility_score']
    ) / 3.0

    # ========== MÉTADONNÉES ==========
    metrics['detection_method'] = 'yolo+segmentation+osm'
    metrics['data_source'] = 'yolo_streetview,map_segmentation,osm'
    metrics['confidence_level'] = calculate_green_confidence(metrics)

    logger.info(f"Score 3-30-300: {metrics['green_index_score']:.2f}")

    return metrics


def calculate_green_confidence(metrics: Dict) -> float:
    """
    Calcule le niveau de confiance des métriques vertes.

    Args:
        metrics: Dict avec les métriques

    Returns:
        Niveau de confiance 0-1
    """
    confidence = 1.0

    # Réduire confiance si données manquantes
    if metrics['trees_visible_count'] == 0:
        confidence *= 0.7  # Détection YOLO peut avoir échoué

    if metrics['canopy_coverage_pct'] == 0.0:
        confidence *= 0.7  # Segmentation peut avoir échoué

    if metrics['distance_to_nearest_park_m'] >= 999.0:
        confidence *= 0.7  # Requête OSM peut avoir échoué

    return confidence


# ============================================================
# EXPORT
# ============================================================

__all__ = [
    'analyze_trees_from_yolo',
    'analyze_canopy_from_segmentation',
    'calculate_distance_to_nearest_park',
    'calculate_330_rule_metrics',
    'estimate_traffic_from_osm',
    'query_osm_green_spaces',
    'MIN_TREES_VISIBLE',
    'TARGET_CANOPY_PCT',
    'MAX_PARK_DISTANCE_M'
]
