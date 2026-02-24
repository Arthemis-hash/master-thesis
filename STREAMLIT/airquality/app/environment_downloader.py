#!/usr/bin/env python3
"""
Module unifié pour télécharger images satellites et Street View
Utilise directement les downloaders existants
"""
import os
import sys
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Augmenter la limite PIL pour éviter l'erreur "decompression bomb"
# Mais garder une limite raisonnable pour la sécurité
from PIL import Image
Image.MAX_IMAGE_PIXELS = 500000000  # 500 millions de pixels max

logger = logging.getLogger(__name__)

# NOTE: Le path vers Image-Analysis sera ajouté dynamiquement dans chaque méthode
# pour éviter les conflits d'imports avec le config.py de l'app
IMAGE_ANALYSIS_PATH = Path(__file__).parent.parent.parent / "Image-Analysis" / "map-download"

# Dossiers de sortie (chemins ABSOLUS pour éviter les problèmes)
BASE_DIR = Path(__file__).parent
SATELLITE_OUTPUT_DIR = str(BASE_DIR / "environment_data" / "satellite")
STREETVIEW_OUTPUT_DIR = str(BASE_DIR / "environment_data" / "streetview")

# Créer les dossiers
os.makedirs(SATELLITE_OUTPUT_DIR, exist_ok=True)
os.makedirs(STREETVIEW_OUTPUT_DIR, exist_ok=True)


class EnvironmentDownloader:
    """Gestionnaire unifié de téléchargements d'environnement"""
    
    def __init__(self, address: str):
        """
        Initialise le downloader
        
        Args:
            address: Adresse à analyser
        """
        self.address = address
        self.lat = None
        self.lon = None
        self.formatted_address = None
    
    def geocode(self) -> Tuple[float, float]:
        """
        Géocode l'adresse en utilisant importlib pour éviter les conflits
        
        Returns:
            (latitude, longitude)
        """
        try:
            # Import forcé du config.py de l'app avec importlib
            import importlib.util
            from pathlib import Path
            
            # Charger le config.py LOCAL de l'app
            config_path = Path(__file__).parent / "config.py"
            spec = importlib.util.spec_from_file_location("app_config", config_path)
            app_config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(app_config)
            
            # Utiliser la fonction geocode_address
            result = app_config.geocode_address(self.address)
            
            if result and result != ("MULTIPLE_RESULTS", None, None):
                lat, lon, full_address = result
                if lat and lon:
                    self.lat = lat
                    self.lon = lon
                    self.formatted_address = full_address
                    logger.info(f"✅ Géocodage: {self.formatted_address}")
                    return self.lat, self.lon
            
            raise ValueError("Géocodage échoué")
                
        except Exception as e:
            logger.error(f"❌ Erreur géocodage: {e}")
            raise
    
    def _estimate_image_size(self, radius_km: float, zoom_levels: List[int], map_types: List[str]) -> tuple:
        """
        Estime la taille finale de l'image assemblée
        
        Returns:
            (estimated_pixels, max_zoom, is_safe)
        """
        # Calcul du nombre de tuiles par dimension pour le zoom max
        max_zoom = max(zoom_levels)
        # Nombre de tuiles = 2^zoom * (radius_km / 40000km) * 2 (pour couvrir la zone)
        tiles_per_side = int(2 ** max_zoom * (radius_km / 40000) * 256 * 2)
        
        # Chaque tuile fait 256x256 pixels
        estimated_width = tiles_per_side
        estimated_height = tiles_per_side
        estimated_pixels = estimated_width * estimated_height
        
        # Limite de sécurité : 200M pixels
        MAX_SAFE_PIXELS = 200_000_000
        is_safe = estimated_pixels <= MAX_SAFE_PIXELS
        
        return (estimated_pixels, max_zoom, is_safe)
    
    def _check_existing_download(self, output_dir: str, metadata_filename: str,
                                  expected_params: Dict) -> Optional[Dict]:
        """
        Vérifie si un téléchargement identique existe déjà.

        Args:
            output_dir: Dossier de sortie
            metadata_filename: Nom du fichier de métadonnées
            expected_params: Paramètres attendus pour comparaison

        Returns:
            Les métadonnées existantes si le téléchargement existe et correspond, sinon None
        """
        metadata_file = os.path.join(output_dir, metadata_filename)
        if not os.path.exists(metadata_file):
            return None

        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                existing_metadata = json.load(f)

            # Vérifier que les paramètres correspondent
            for key, expected_value in expected_params.items():
                existing_value = existing_metadata.get(key)
                if existing_value != expected_value:
                    logger.info(f"Paramètre '{key}' différent: existant={existing_value}, attendu={expected_value}")
                    return None

            # Vérifier qu'il y a bien des images
            if existing_metadata.get('total_images', 0) > 0 or existing_metadata.get('total_photos', 0) > 0:
                logger.info(f"Téléchargement existant trouvé dans {output_dir}, skip")
                return existing_metadata

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Métadonnées corrompues dans {metadata_file}: {e}")

        return None

    def download_satellite_maps(
        self,
        radius_km: float = 0.5,
        zoom_levels: List[int] = [17, 18],
        map_types: List[str] = ['satellite', 'roadmap']
    ) -> Dict:
        """
        Télécharge les cartes satellites (skip si déjà existantes)

        Args:
            radius_km: Rayon en km (max 1.0 pour sécurité)
            zoom_levels: Niveaux de zoom (max 2 niveaux recommandé)
            map_types: Types de cartes

        Returns:
            Dictionnaire avec métadonnées
        """
        # Vérifier si le téléchargement existe déjà
        try:
            from db_async_wrapper import DatabaseManager
            normalized = DatabaseManager.sanitize_address(self.address)
        except ImportError:
            import re
            normalized = re.sub(r'[^\w\s-]', '', self.address.lower())
            normalized = re.sub(r'[\s_-]+', '_', normalized).strip('_')

        output_dir = os.path.join(SATELLITE_OUTPUT_DIR, normalized)
        existing = self._check_existing_download(
            output_dir, 'metadata.json',
            {'radius_km': radius_km, 'zoom_levels': zoom_levels, 'map_types': map_types}
        )
        if existing:
            logger.info(f"Images satellites déjà existantes pour '{self.address}', skip téléchargement")
            return existing

        # Validation de sécurité pour éviter bombe de décompression
        if radius_km > 1.5:
            logger.warning(f"⚠️ Rayon réduit de {radius_km} à 1.5 km pour sécurité")
            radius_km = 1.5
        
        if len(zoom_levels) > 3:
            logger.warning(f"⚠️ Nombre de zooms réduit de {len(zoom_levels)} à 3 pour sécurité")
            zoom_levels = zoom_levels[:3]
        
        # Limiter les zooms trop élevés (génèrent trop de tuiles)
        zoom_levels = [z for z in zoom_levels if z <= 19]
        if not zoom_levels:
            zoom_levels = [17, 18]
            logger.warning("⚠️ Zooms ajustés à [17, 18] pour sécurité")
        
        # VALIDATION CRITIQUE : Vérifier la taille estimée AVANT le téléchargement
        estimated_pixels, max_zoom, is_safe = self._estimate_image_size(radius_km, zoom_levels, map_types)
        logger.info(f"📊 Taille estimée: {estimated_pixels:,} pixels (zoom max: {max_zoom})")
        
        if not is_safe:
            error_msg = (
                f"🚫 TÉLÉCHARGEMENT BLOQUÉ : Configuration dangereuse!\n"
                f"   Taille estimée: {estimated_pixels:,} pixels\n"
                f"   Limite sécurité: 200,000,000 pixels\n"
                f"   Rayon: {radius_km} km, Zoom max: {max_zoom}\n"
                f"   💡 Réduisez le rayon ou le niveau de zoom maximum."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("=" * 60)
        logger.info("🛰️  TÉLÉCHARGEMENT CARTES SATELLITES")
        logger.info("=" * 60)
        logger.info(f"📐 Rayon: {radius_km} km")
        logger.info(f"🔎 Zooms: {zoom_levels}")
        logger.info(f"🗺️  Types: {map_types}")
        
        try:
            # Ajouter le path dynamiquement pour éviter conflits
            if str(IMAGE_ANALYSIS_PATH) not in sys.path:
                sys.path.insert(0, str(IMAGE_ANALYSIS_PATH))
            
            # Nettoyer le cache de modules pour éviter conflits
            if 'config' in sys.modules:
                del sys.modules['config']
            if 'map_downloader' in sys.modules:
                del sys.modules['map_downloader']
            
            # Import dynamique du downloader
            from map_downloader import MapDownloader  # type: ignore
            import config as map_config  # type: ignore

            # Vérifier que les clés sont bien chargées
            if not hasattr(map_config, 'GEOCODING_API_KEY') or not map_config.GEOCODING_API_KEY:
                raise ValueError("GEOCODING_API_KEY non chargée dans le config de map-download")

            # Créer sous-dossier pour cette adresse
            # Import avec gestion d'erreur pour db_utils
            try:
                from db_async_wrapper import DatabaseManager  # type: ignore
                normalized = DatabaseManager.sanitize_address(self.address)
            except ImportError:
                # Fallback: sanitization manuelle si db_utils non disponible
                import re
                normalized = re.sub(r'[^\w\s-]', '', self.address.lower())
                normalized = re.sub(r'[\s_-]+', '_', normalized).strip('_')
            output_dir = os.path.join(SATELLITE_OUTPUT_DIR, normalized)
            os.makedirs(output_dir, exist_ok=True)
            
            # Sauvegarder et modifier temporairement le dossier de sortie
            original_dir = map_config.MULTI_ZOOM_DIR
            map_config.MULTI_ZOOM_DIR = output_dir
            
            try:
                # Créer le downloader
                downloader = MapDownloader(self.address)
                downloader.geocode()
                
                # Télécharger
                results = downloader.download_multi_zoom(
                    radius_km=radius_km,
                    zoom_levels=zoom_levels,
                    maptypes=map_types
                )
            finally:
                # Toujours restaurer le dossier original
                map_config.MULTI_ZOOM_DIR = original_dir
            
            # Métadonnées
            metadata = {
                'address': self.formatted_address or self.address,
                'latitude': downloader.lat,
                'longitude': downloader.lon,
                'radius_km': radius_km,
                'zoom_levels': zoom_levels,
                'map_types': map_types,
                'output_directory': output_dir,
                'total_images': len(results),
                'download_timestamp': datetime.now().isoformat(),
                'maps_metadata': downloader.metadata
            }
            
            # Sauvegarder métadonnées JSON
            metadata_file = os.path.join(output_dir, 'metadata.json')
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            # La sauvegarde en PostgreSQL est gérée par l'appelant (environment_ui.py)
            logger.info(f"✅ {len(results)} images satellites téléchargées")
            logger.info(f"📁 Dossier: {output_dir}")
            
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Erreur téléchargement satellite: {e}")
            raise
    
    def download_streetview_images(
        self,
        radius_m: int = 250,
        max_photos: int = 12,
        use_smart_filter: bool = True
    ) -> Dict:
        """
        Télécharge les images Street View (skip si déjà existantes)

        Args:
            radius_m: Rayon en mètres
            max_photos: Nombre max de photos
            use_smart_filter: Utiliser le filtre intelligent

        Returns:
            Dictionnaire avec métadonnées
        """
        # Vérifier si le téléchargement existe déjà
        try:
            from db_async_wrapper import DatabaseManager
            normalized = DatabaseManager.sanitize_address(self.address)
        except ImportError:
            import re
            normalized = re.sub(r'[^\w\s-]', '', self.address.lower())
            normalized = re.sub(r'[\s_-]+', '_', normalized).strip('_')

        output_dir = os.path.join(STREETVIEW_OUTPUT_DIR, normalized)
        existing = self._check_existing_download(
            output_dir, 'street_view_metadata.json',
            {'radius_m': radius_m, 'max_photos': max_photos}
        )
        if existing:
            logger.info(f"Images Street View déjà existantes pour '{self.address}', skip téléchargement")
            return existing

        logger.info("=" * 60)
        logger.info("📸 TÉLÉCHARGEMENT STREET VIEW")
        logger.info("=" * 60)
        
        try:
            # Ajouter le path dynamiquement pour éviter conflits
            if str(IMAGE_ANALYSIS_PATH) not in sys.path:
                sys.path.insert(0, str(IMAGE_ANALYSIS_PATH))
            
            # Nettoyer le cache de modules pour éviter conflits
            if 'street_view_downloader' in sys.modules:
                del sys.modules['street_view_downloader']
            
            # Import dynamique
            from street_view_downloader import StreetViewDownloader  # type: ignore
            import street_view_downloader as sv_module  # type: ignore
            
            # Créer sous-dossier pour cette adresse
            # Import avec gestion d'erreur pour db_utils
            try:
                from db_async_wrapper import DatabaseManager  # type: ignore
                normalized = DatabaseManager.sanitize_address(self.address)
            except ImportError:
                # Fallback: sanitization manuelle si db_utils non disponible
                import re
                normalized = re.sub(r'[^\w\s-]', '', self.address.lower())
                normalized = re.sub(r'[\s_-]+', '_', normalized).strip('_')
            output_dir = os.path.join(STREETVIEW_OUTPUT_DIR, normalized)
            os.makedirs(output_dir, exist_ok=True)
            
            # Sauvegarder et modifier temporairement le dossier de sortie
            original_dir = sv_module.OUTPUT_DIR
            sv_module.OUTPUT_DIR = output_dir
            
            try:
                # Créer le downloader
                downloader = StreetViewDownloader(self.address, use_smart_filter=use_smart_filter)
                downloader.geocode()
                
                # Télécharger
                downloaded_files = downloader.download_area_street_views(
                    radius_m=radius_m,
                    max_photos=max_photos
                )
            finally:
                # Toujours restaurer le dossier original
                sv_module.OUTPUT_DIR = original_dir
            
            # Métadonnées
            metadata = {
                'address': downloader.formatted_address or self.address,
                'latitude': downloader.lat,
                'longitude': downloader.lon,
                'radius_m': radius_m,
                'max_photos': max_photos,
                'quality_filter_used': use_smart_filter,
                'total_photos': len(downloaded_files),
                'output_directory': output_dir,
                'download_timestamp': datetime.now().isoformat(),
                'downloaded_files': downloaded_files
            }
            
            # Sauvegarder métadonnées JSON
            metadata_file = os.path.join(output_dir, 'street_view_metadata.json')
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            # La sauvegarde en PostgreSQL est gérée par l'appelant (environment_ui.py)
            logger.info(f"✅ {len(downloaded_files)} images Street View téléchargées")
            logger.info(f"📁 Dossier: {output_dir}")
            
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Erreur téléchargement Street View: {e}")
            raise
    
    def download_all(
        self,
        satellite_config: Optional[Dict] = None,
        streetview_config: Optional[Dict] = None
    ) -> Dict:
        """
        Télécharge tout (satellites + Street View)
        
        Args:
            satellite_config: Config satellites (radius_km, zoom_levels, map_types)
            streetview_config: Config Street View (radius_m, max_photos, use_smart_filter)
            
        Returns:
            Dictionnaire avec toutes les métadonnées
        """
        # Géocoder d'abord
        if not self.lat or not self.lon:
            self.geocode()
        
        results = {
            'address': self.formatted_address or self.address,
            'coordinates': {'lat': self.lat, 'lon': self.lon}
        }
        
        # Télécharger satellites
        if satellite_config is not False:
            sat_config = satellite_config or {}
            try:
                sat_metadata = self.download_satellite_maps(**sat_config)
                results['satellite'] = sat_metadata
            except Exception as e:
                logger.error(f"⚠️ Erreur satellites: {e}")
                results['satellite'] = {'error': str(e)}
        
        # Télécharger Street View
        if streetview_config is not False:
            sv_config = streetview_config or {}
            try:
                sv_metadata = self.download_streetview_images(**sv_config)
                results['streetview'] = sv_metadata
            except Exception as e:
                logger.error(f"⚠️ Erreur Street View: {e}")
                results['streetview'] = {'error': str(e)}
        
        return results
