#!/usr/bin/env python3
"""
Gestion de la base de données pour les téléchargements d'environnement
(Images satellites, Street View, métadonnées géographiques)
"""
import sqlite3
import os
import logging
import json
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


class EnvironmentDB:
    """Base de données pour les téléchargements d'environnement"""
    
    def __init__(self, address: str = None):
        """
        Initialise la base Environment
        
        Args:
            address: Adresse pour laquelle chercher/créer une base
        """
        from db_utils import DatabaseManager
        
        if address:
            self.db_path = DatabaseManager.get_or_create_db(address, 'environment', force_new=False)
            self.current_address = address
            self.normalized_address = DatabaseManager.sanitize_address(address)
        else:
            self.db_path = 'environment_data.db'
            self.current_address = "Unknown"
            self.normalized_address = "unknown"
        
        self._initialize_tables()
        logger.info(f"✅ EnvironmentDB initialisée: {self.db_path}")
    
    def _initialize_tables(self):
        """Crée les tables pour stocker les métadonnées d'environnement"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table pour les téléchargements satellites
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS satellite_downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                normalized_address TEXT,
                latitude REAL,
                longitude REAL,
                radius_km REAL,
                zoom_levels TEXT,
                map_types TEXT,
                output_directory TEXT,
                total_images INTEGER,
                download_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT,
                UNIQUE(address, download_date)
            )
        ''')
        
        # Table pour les téléchargements Street View
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS streetview_downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                normalized_address TEXT,
                latitude REAL,
                longitude REAL,
                radius_m INTEGER,
                total_photos INTEGER,
                quality_filter_used BOOLEAN,
                output_directory TEXT,
                download_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT,
                UNIQUE(address, download_date)
            )
        ''')
        
        # Table pour les images individuelles (satellites)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS satellite_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                download_id INTEGER,
                filename TEXT,
                filepath TEXT,
                zoom_level INTEGER,
                map_type TEXT,
                image_width INTEGER,
                image_height INTEGER,
                resolution_m_per_px REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (download_id) REFERENCES satellite_downloads(id)
            )
        ''')
        
        # Table pour les images individuelles (Street View)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS streetview_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                download_id INTEGER,
                filename TEXT,
                filepath TEXT,
                latitude REAL,
                longitude REAL,
                heading INTEGER,
                quality_score INTEGER,
                is_outdoor BOOLEAN,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (download_id) REFERENCES streetview_downloads(id)
            )
        ''')
        
        # Index pour recherche rapide
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sat_address ON satellite_downloads(address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sv_address ON streetview_downloads(address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sat_date ON satellite_downloads(download_date DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sv_date ON streetview_downloads(download_date DESC)')
        
        conn.commit()
        conn.close()
    
    def insert_satellite_download(
        self, 
        address: str,
        lat: float,
        lon: float,
        radius_km: float,
        zoom_levels: List[int],
        map_types: List[str],
        output_dir: str,
        metadata: Dict
    ) -> Optional[int]:
        """
        Enregistre un téléchargement satellite
        
        Returns:
            ID du téléchargement ou None si erreur
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            from db_utils import DatabaseManager
            normalized = DatabaseManager.sanitize_address(address)
            
            cursor.execute('''
                INSERT INTO satellite_downloads 
                (address, normalized_address, latitude, longitude, radius_km, 
                 zoom_levels, map_types, output_directory, total_images, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                address,
                normalized,
                lat,
                lon,
                radius_km,
                json.dumps(zoom_levels),
                json.dumps(map_types),
                output_dir,
                len(zoom_levels) * len(map_types),
                json.dumps(metadata)
            ))
            
            download_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Téléchargement satellite enregistré (ID: {download_id})")
            return download_id
            
        except Exception as e:
            logger.error(f"❌ Erreur enregistrement satellite: {e}")
            return None
    
    def insert_streetview_download(
        self,
        address: str,
        lat: float,
        lon: float,
        radius_m: int,
        total_photos: int,
        quality_filter: bool,
        output_dir: str,
        metadata: Dict
    ) -> Optional[int]:
        """
        Enregistre un téléchargement Street View
        
        Returns:
            ID du téléchargement ou None si erreur
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            from db_utils import DatabaseManager
            normalized = DatabaseManager.sanitize_address(address)
            
            cursor.execute('''
                INSERT INTO streetview_downloads 
                (address, normalized_address, latitude, longitude, radius_m,
                 total_photos, quality_filter_used, output_directory, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                address,
                normalized,
                lat,
                lon,
                radius_m,
                total_photos,
                quality_filter,
                output_dir,
                json.dumps(metadata)
            ))
            
            download_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Téléchargement Street View enregistré (ID: {download_id})")
            return download_id
            
        except Exception as e:
            logger.error(f"❌ Erreur enregistrement Street View: {e}")
            return None
    
    def get_latest_satellite_download(self, address: str) -> Optional[Dict]:
        """Récupère le dernier téléchargement satellite pour une adresse"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            from db_utils import DatabaseManager
            normalized = DatabaseManager.sanitize_address(address)
            
            cursor.execute('''
                SELECT * FROM satellite_downloads
                WHERE address = ? OR normalized_address = ?
                ORDER BY download_date DESC
                LIMIT 1
            ''', (address, normalized))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération satellite: {e}")
            return None
    
    def get_latest_streetview_download(self, address: str) -> Optional[Dict]:
        """Récupère le dernier téléchargement Street View pour une adresse"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            from db_utils import DatabaseManager
            normalized = DatabaseManager.sanitize_address(address)
            
            cursor.execute('''
                SELECT * FROM streetview_downloads
                WHERE address = ? OR normalized_address = ?
                ORDER BY download_date DESC
                LIMIT 1
            ''', (address, normalized))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération Street View: {e}")
            return None
    
    def get_all_downloads_summary(self, address: str) -> Dict:
        """Récupère un résumé de tous les téléchargements pour une adresse"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            from db_utils import DatabaseManager
            normalized = DatabaseManager.sanitize_address(address)
            
            # Satellites
            sat_df = pd.read_sql_query('''
                SELECT * FROM satellite_downloads
                WHERE address = ? OR normalized_address = ?
                ORDER BY download_date DESC
            ''', conn, params=(address, normalized))
            
            # Street View
            sv_df = pd.read_sql_query('''
                SELECT * FROM streetview_downloads
                WHERE address = ? OR normalized_address = ?
                ORDER BY download_date DESC
            ''', conn, params=(address, normalized))
            
            conn.close()
            
            return {
                'satellite': sat_df,
                'streetview': sv_df,
                'total_satellite': len(sat_df),
                'total_streetview': len(sv_df)
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération résumé: {e}")
            return {
                'satellite': pd.DataFrame(),
                'streetview': pd.DataFrame(),
                'total_satellite': 0,
                'total_streetview': 0
            }
