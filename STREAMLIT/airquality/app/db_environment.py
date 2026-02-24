#!/usr/bin/env python3
"""
============================================================
GESTION BASE DE DONNÉES ENVIRONNEMENT
============================================================
Téléchargements & analyses d'environnement:
- Images satellites (Google Maps API)
- Street View
- Analyses YOLO/segmentation
Architecture Prisma + PostgreSQL
============================================================
"""

import logging
import json
from datetime import datetime
from typing import Optional, Dict, List
from prisma import Prisma
from prisma.models import (
    Address, SatelliteDownload, SatelliteImage,
    StreetViewDownload, StreetViewImage, ImageAnalysis
)

logger = logging.getLogger(__name__)


# ============================================================
# CLIENT PRISMA
# ============================================================

class EnvironmentDatabaseClient:
    """Client Prisma singleton pour données environnement"""

    _instance: Optional[Prisma] = None
    _is_connected: bool = False
    _loop: Optional[object] = None

    @classmethod
    async def get_client(cls) -> Prisma:
        """Récupère ou crée le client Prisma"""
        import asyncio
        current_loop = asyncio.get_running_loop()

        # Si le loop a changé (reload Streamlit), on doit recréer le client
        if cls._is_connected and cls._loop is not None and cls._loop is not current_loop:
            logger.warning("⚠️ Env Event loop changed. Resetting Prisma client.")
            if cls._instance:
                try:
                    await cls._instance.disconnect()
                except Exception:
                    pass
            cls._instance = None
            cls._is_connected = False

        if cls._instance is None:
            cls._instance = Prisma()

        if not cls._is_connected:
            await cls._instance.connect()
            cls._is_connected = True
            cls._loop = current_loop
            logger.info("✅ Environment Prisma client connected")

        return cls._instance

    @classmethod
    async def disconnect(cls):
        """Ferme la connexion"""
        if cls._instance and cls._is_connected:
            await cls._instance.disconnect()
            cls._is_connected = False
            cls._loop = None
            logger.info("🔌 Environment Prisma client disconnected")


# ============================================================
# GESTIONNAIRE TÉLÉCHARGEMENTS SATELLITES
# ============================================================

class SatelliteDownloadManager:
    """Gestion téléchargements images satellites"""

    def __init__(self):
        self.db: Optional[Prisma] = None

    async def _ensure_connected(self):
        """Assure connexion active"""
        if not self.db:
            self.db = await EnvironmentDatabaseClient.get_client()

    async def create_download(
        self,
        address_id: int,
        radius_km: float,
        zoom_levels: List[int],
        map_types: List[str],
        output_directory: str,
        metadata: Optional[Dict] = None
    ) -> SatelliteDownload:
        """
        Enregistre un téléchargement satellite
        """
        await self._ensure_connected()

        total_images = len(zoom_levels) * len(map_types)

        download = await self.db.satellitedownload.create(
            data={
                'address': {
                    'connect': {'id': address_id}
                },
                'radiusKm': radius_km,
                'zoomLevels': zoom_levels,
                'mapTypes': map_types,
                'outputDirectory': output_directory,
                'totalImages': total_images,
                'metadata': json.loads(json.dumps(metadata, default=str)) if metadata else None
            }
        )

        logger.info(f"✅ Téléchargement satellite créé: ID {download.id}")
        return download

    async def add_image(
        self,
        download_id: int,
        filename: str,
        filepath: str,
        zoom_level: int,
        map_type: str,
        image_width: int,
        image_height: int,
        resolution_m_per_px: float
    ):
        """Enregistre une image satellite individuelle"""
        await self._ensure_connected()

        image = await self.db.satelliteimage.create(
            data={
                'downloadId': download_id,
                'filename': filename,
                'filepath': filepath,
                'zoomLevel': zoom_level,
                'mapType': map_type,
                'imageWidth': image_width,
                'imageHeight': image_height,
                'resolutionMPerPx': resolution_m_per_px,
            }
        )

        logger.info(f"Image satellite ajoutée: {filename} (ID {image.id})")
        return image

    async def get_latest_download(
        self,
        address_id: int
    ) -> Optional[SatelliteDownload]:
        """
        Récupère le dernier téléchargement pour une adresse
        """
        await self._ensure_connected()

        download = await self.db.satellitedownload.find_first(
            where={'addressId': address_id},
            order={'downloadDate': 'desc'},
            include={'images': True, 'address': True}
        )

        return download

    async def get_download_by_id(
        self,
        download_id: int
    ) -> Optional[SatelliteDownload]:
        """
        Récupère un téléchargement par ID avec toutes les images
        """
        await self._ensure_connected()

        download = await self.db.satellitedownload.find_unique(
            where={'id': download_id},
            include={'images': True, 'address': True}
        )

        return download

    async def list_downloads_by_address(
        self,
        address_id: int
    ) -> List[SatelliteDownload]:
        """
        Liste tous les téléchargements pour une adresse
        """
        await self._ensure_connected()

        downloads = await self.db.satellitedownload.find_many(
            where={'addressId': address_id},
            order={'downloadDate': 'desc'},
            include={'images': True}
        )

        return downloads


# ============================================================
# GESTIONNAIRE TÉLÉCHARGEMENTS STREET VIEW
# ============================================================

class StreetViewDownloadManager:
    """Gestion téléchargements Street View"""

    def __init__(self):
        self.db: Optional[Prisma] = None

    async def _ensure_connected(self):
        if not self.db:
            self.db = await EnvironmentDatabaseClient.get_client()

    async def create_download(
        self,
        address_id: int,
        radius_m: int,
        total_photos: int,
        quality_filter_used: bool,
        output_directory: str,
        metadata: Optional[Dict] = None
    ) -> StreetViewDownload:
        """
        Enregistre un téléchargement Street View
        """
        await self._ensure_connected()

        download = await self.db.streetviewdownload.create(
            data={
                'address': {
                    'connect': {'id': address_id}
                },
                'radiusM': radius_m,
                'totalPhotos': total_photos,
                'qualityFilterUsed': quality_filter_used,
                'outputDirectory': output_directory,
                'metadata': json.loads(json.dumps(metadata, default=str)) if metadata else None
            }
        )

        logger.info(f"✅ Téléchargement Street View créé: ID {download.id}")
        return download

    async def add_image(
        self,
        download_id: int,
        filename: str,
        filepath: str,
        latitude: float,
        longitude: float,
        heading: int,
        quality_score: Optional[int] = None,
        is_outdoor: Optional[bool] = None
    ):
        """Enregistre une image Street View individuelle"""
        await self._ensure_connected()

        data = {
            'downloadId': download_id,
            'filename': filename,
            'filepath': filepath,
            'latitude': latitude,
            'longitude': longitude,
            'heading': heading,
        }
        if quality_score is not None:
            data['qualityScore'] = quality_score
        if is_outdoor is not None:
            data['isOutdoor'] = is_outdoor

        image = await self.db.streetviewimage.create(data=data)

        logger.info(f"Image Street View ajoutée: {filename} (ID {image.id})")
        return image

    async def get_latest_download(
        self,
        address_id: int
    ) -> Optional[StreetViewDownload]:
        """
        Récupère le dernier téléchargement pour une adresse
        """
        await self._ensure_connected()

        download = await self.db.streetviewdownload.find_first(
            where={'addressId': address_id},
            order={'downloadDate': 'desc'},
            include={'images': True, 'address': True}
        )

        return download

    async def get_download_by_id(
        self,
        download_id: int
    ) -> Optional[StreetViewDownload]:
        """
        Récupère un téléchargement par ID avec toutes les images
        """
        await self._ensure_connected()

        download = await self.db.streetviewdownload.find_unique(
            where={'id': download_id},
            include={'images': True, 'address': True}
        )

        return download

    async def list_downloads_by_address(
        self,
        address_id: int
    ) -> List[StreetViewDownload]:
        """
        Liste tous les téléchargements pour une adresse
        """
        await self._ensure_connected()

        downloads = await self.db.streetviewdownload.find_many(
            where={'addressId': address_id},
            order={'downloadDate': 'desc'},
            include={'images': True}
        )

        return downloads


# ============================================================
# GESTIONNAIRE ANALYSES D'IMAGES
# ============================================================

class ImageAnalysisManager:
    """Gestion analyses d'images (YOLO, segmentation, etc.)"""

    def __init__(self):
        self.db: Optional[Prisma] = None

    async def _ensure_connected(self):
        if not self.db:
            self.db = await EnvironmentDatabaseClient.get_client()

    async def save_analysis(
        self,
        image_type: str,  # 'satellite' ou 'streetview'
        image_id: int,  # ID de l'image (satellite_images.id ou streetview_images.id)
        analysis_type: str,  # 'yolo', 'segmentation', etc.
        model_name: str,  # Nom du modèle (ex: 'yolov8n', 'deeplabv3')
        results: Dict,
        model_version: Optional[str] = None,
        statistics: Optional[Dict] = None,
        processing_time: Optional[float] = None
    ) -> ImageAnalysis:
        """
        Enregistre une analyse d'image

        Args:
            image_type: Type d'image ('satellite' ou 'streetview')
            image_id: ID de l'image source (satellite_images.id ou streetview_images.id)
            analysis_type: Type d'analyse ('yolo', 'segmentation', etc.)
            model_name: Nom du modèle utilisé
            results: Résultats détaillés de l'analyse (JSON)
            model_version: Version du modèle (optionnel)
            statistics: Statistiques agrégées (optionnel)
            processing_time: Temps de traitement en secondes (optionnel)
        """
        await self._ensure_connected()

        data = {
            'imageType': image_type,
            'imageId': image_id,
            'analysisType': analysis_type,
            'modelName': model_name,
            'results': results,
        }
        if model_version:
            data['modelVersion'] = model_version
        if statistics:
            data['statistics'] = statistics
        if processing_time is not None:
            data['processingTime'] = processing_time

        analysis = await self.db.imageanalysis.create(data=data)

        logger.info(f"✅ Analyse sauvegardée: {analysis_type} ({model_name}) sur {image_type} image#{image_id}")
        return analysis

    async def get_analyses_for_image(
        self,
        image_type: str,
        image_id: int
    ) -> List[ImageAnalysis]:
        """
        Récupère toutes les analyses pour une image spécifique
        """
        await self._ensure_connected()

        analyses = await self.db.imageanalysis.find_many(
            where={
                'imageType': image_type,
                'imageId': image_id,
            },
            order={'createdAt': 'desc'}
        )

        return analyses

    async def get_latest_analysis(
        self,
        image_type: Optional[str] = None,
        image_id: Optional[int] = None,
        analysis_type: Optional[str] = None
    ) -> Optional[ImageAnalysis]:
        """
        Récupère la dernière analyse, filtrée par type d'image, image_id et/ou type d'analyse
        """
        await self._ensure_connected()

        where_clause = {}
        if image_type:
            where_clause['imageType'] = image_type
        if image_id is not None:
            where_clause['imageId'] = image_id
        if analysis_type:
            where_clause['analysisType'] = analysis_type

        analysis = await self.db.imageanalysis.find_first(
            where=where_clause,
            order={'createdAt': 'desc'}
        )

        return analysis

    async def get_analyses_by_type(
        self,
        analysis_type: str,
        limit: int = 100
    ) -> List[ImageAnalysis]:
        """
        Récupère toutes les analyses d'un type donné
        """
        await self._ensure_connected()

        analyses = await self.db.imageanalysis.find_many(
            where={'analysisType': analysis_type},
            order={'createdAt': 'desc'},
            take=limit
        )

        return analyses


# ============================================================
# GESTIONNAIRE ENVIRONNEMENT COMPLET
# ============================================================

class EnvironmentDB:
    """
    Gestionnaire principal pour toutes les données environnement
    API simplifiée qui regroupe tous les managers
    """

    def __init__(self):
        self.satellite = SatelliteDownloadManager()
        self.streetview = StreetViewDownloadManager()
        self.analysis = ImageAnalysisManager()

    async def get_all_downloads_summary(
        self,
        address_id: int
    ) -> Dict:
        """
        Récupère un résumé de tous les téléchargements pour une adresse
        """
        satellite_downloads = await self.satellite.list_downloads_by_address(address_id)
        streetview_downloads = await self.streetview.list_downloads_by_address(address_id)

        return {
            'satellite': {
                'total': len(satellite_downloads),
                'downloads': [
                    {
                        'id': d.id,
                        'download_date': d.downloadDate,
                        'radius_km': d.radiusKm,
                        'zoom_levels': d.zoomLevels,
                        'map_types': d.mapTypes,
                        'total_images': d.totalImages
                    }
                    for d in satellite_downloads
                ]
            },
            'streetview': {
                'total': len(streetview_downloads),
                'downloads': [
                    {
                        'id': d.id,
                        'download_date': d.downloadDate,
                        'radius_m': d.radiusM,
                        'total_photos': d.totalPhotos,
                        'quality_filter': d.qualityFilterUsed
                    }
                    for d in streetview_downloads
                ]
            }
        }

    async def get_environment_statistics(
        self,
        address_id: int
    ) -> Dict:
        """
        Calcule statistiques environnementales pour une adresse
        Basé sur les analyses d'images disponibles
        """
        # Récupérer tous les téléchargements
        summary = await self.get_all_downloads_summary(address_id)

        # TODO: Agréger les statistiques des analyses
        # Ex: moyenne % végétation, nb arbres détectés, etc.

        stats = {
            'total_satellite_images': sum(
                d['total_images'] for d in summary['satellite']['downloads']
            ),
            'total_streetview_images': sum(
                d['total_photos'] for d in summary['streetview']['downloads']
            ),
            'last_update': None
        }

        # Trouver la date de dernier téléchargement
        all_dates = []
        if summary['satellite']['downloads']:
            all_dates.extend([d['download_date'] for d in summary['satellite']['downloads']])
        if summary['streetview']['downloads']:
            all_dates.extend([d['download_date'] for d in summary['streetview']['downloads']])

        if all_dates:
            stats['last_update'] = max(all_dates)

        return stats

    async def insert_satellite_download(
        self,
        address_id: int,
        radius_km: float,
        zoom_levels: List[int],
        map_types: List[str],
        output_directory: str,
        metadata: Optional[Dict] = None
    ) -> int:
        """
        Wrapper pour créer un téléchargement satellite

        Returns:
            ID du téléchargement créé
        """
        download = await self.satellite.create_download(
            address_id=address_id,
            radius_km=radius_km,
            zoom_levels=zoom_levels,
            map_types=map_types,
            output_directory=output_directory,
            metadata=metadata
        )
        return download.id

    async def insert_streetview_download(
        self,
        address_id: int,
        radius_m: int,
        total_photos: int,
        quality_filter_used: bool,
        output_directory: str,
        metadata: Optional[Dict] = None
    ) -> int:
        """
        Wrapper pour créer un téléchargement Street View

        Returns:
            ID du téléchargement créé
        """
        download = await self.streetview.create_download(
            address_id=address_id,
            radius_m=radius_m,
            total_photos=total_photos,
            quality_filter_used=quality_filter_used,
            output_directory=output_directory,
            metadata=metadata
        )
        return download.id


# ============================================================
# EXPORT
# ============================================================

__all__ = [
    'EnvironmentDB',
    'SatelliteDownloadManager',
    'StreetViewDownloadManager',
    'ImageAnalysisManager'
]
