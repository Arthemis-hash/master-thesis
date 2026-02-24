#!/usr/bin/env python3
"""
============================================================
MODULE DE GESTION DES BASES DE DONNÉES
============================================================
Gestion de DEUX bases de données distinctes :
- AirQualityDB : Données de qualité de l'air
- WeatherDB : Données météorologiques

Toutes les bases sont stockées dans le dossier databases/
"""

# ============================================================
# IMPORTS
# ============================================================
import sqlite3
import pandas as pd
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION GLOBALE
# ============================================================

# Dossier centralisé pour toutes les bases de données
DB_FOLDER = Path(__file__).parent / "databases"
DB_FOLDER.mkdir(exist_ok=True)  # Créer si n'existe pas


# ============================================================
# CLASSE : GESTIONNAIRE DE BASES DE DONNÉES
# ============================================================
class DatabaseManager:
    """Gestionnaire centralisé pour créer et gérer les bases de données"""

    @staticmethod
    def sanitize_address(address: str) -> str:
        """
        Normalise une adresse pour usage cohérent
        Extrait code postal + ville pour meilleure identification

        Args:
            address: Adresse à normaliser

        Returns:
            Adresse normalisée (max 50 caractères)
        """
        parts = address.split(',')
        postal_code = None
        city = None

        # Extraire code postal et ville
        for part in parts:
            part = part.strip()

            # Chercher code postal (4-5 chiffres)
            postal_match = re.search(r'\b(\d{4,5})\b', part)
            if postal_match:
                postal_code = postal_match.group(1)

            # Chercher nom de ville
            city_keywords = ['bruxelles', 'brussels', 'brussel', 'ixelles', 'elsene',
                           'schaerbeek', 'etterbeek', 'anderlecht', 'molenbeek']
            if any(keyword in part.lower() for keyword in city_keywords):
                city = re.sub(r'[^\w\s-]', '', part).strip()

        # Construire adresse normalisée
        if postal_code and city:
            normalized = f"{postal_code}_{re.sub(r'\s+', '_', city.lower())}"
        elif postal_code:
            normalized = postal_code
        elif city:
            normalized = re.sub(r'\s+', '_', city.lower())
        else:
            # Fallback: utiliser premiers mots
            first_part = parts[0].strip()
            normalized = re.sub(r'[^\w\s-]', '', first_part)
            normalized = re.sub(r'\s+', '_', normalized.lower())

        return normalized[:50]

    @staticmethod
    def generate_db_name(address: str, db_type: str = 'air_quality') -> str:
        """
        Génère un nom de base de données unique avec timestamp
        Format: {type}_{adresse}_{YYYYMMDD_HHMMSS}.db

        Args:
            address: Adresse pour la base
            db_type: Type de base ('air_quality' ou 'weather')

        Returns:
            Nom de fichier complet avec chemin vers databases/
        """
        clean_address = DatabaseManager.sanitize_address(address)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{db_type}_{clean_address}_{timestamp}.db"
        return str(DB_FOLDER / filename)

    @staticmethod
    def find_existing_db(address: str, db_type: str = 'air_quality') -> Optional[str]:
        """
        Cherche une base existante pour cette adresse
        Recherche flexible par correspondance exacte puis partielle

        Args:
            address: Adresse recherchée
            db_type: Type de base ('air_quality' ou 'weather')

        Returns:
            Chemin de la base la plus récente ou None
        """
        normalized = DatabaseManager.sanitize_address(address)

        # 1. Recherche exacte dans le dossier databases/
        matching_files = []
        for file in DB_FOLDER.glob(f"{db_type}_{normalized}_*.db"):
            matching_files.append(str(file))

        if matching_files:
            matching_files.sort(reverse=True)
            return matching_files[0]

        # 2. Recherche partielle par mots-clés
        normalized_parts = [p for p in normalized.split('_') if len(p) > 2]

        if normalized_parts:
            all_dbs = list(DB_FOLDER.glob(f"{db_type}_*.db"))

            for db_file in sorted(all_dbs, reverse=True):
                db_name = db_file.name
                matches = sum(1 for part in normalized_parts if part in db_name)
                if matches >= min(2, len(normalized_parts)):
                    return str(db_file)

        return None

    @staticmethod
    def get_or_create_db(address: str, db_type: str = 'air_quality', force_new: bool = False) -> str:
        """
        Récupère une base existante ou en crée une nouvelle

        Args:
            address: Adresse recherchée
            db_type: Type de base ('air_quality' ou 'weather')
            force_new: Force création d'une nouvelle base

        Returns:
            Chemin complet de la base de données
        """
        if not force_new:
            existing_db = DatabaseManager.find_existing_db(address, db_type)
            if existing_db:
                return existing_db

        # Créer nouvelle base
        new_db = DatabaseManager.generate_db_name(address, db_type)
        logger.info(f"🆕 Nouvelle base créée: {new_db}")
        return new_db

    @staticmethod
    def list_all_databases(db_type: str = 'air_quality') -> List[Dict]:
        """
        Liste toutes les bases de données disponibles d'un type

        Args:
            db_type: Type de base ('air_quality' ou 'weather')

        Returns:
            Liste de dictionnaires avec infos sur chaque base
        """
        databases = []

        try:
            # Chercher tous les fichiers .db dans databases/
            db_files = list(DB_FOLDER.glob(f"{db_type}_*.db"))

            for db_file in db_files:
                try:
                    file_info = {
                        'path': str(db_file),
                        'type': db_type,
                        'size': db_file.stat().st_size / (1024 * 1024),  # MB
                        'modified': datetime.fromtimestamp(db_file.stat().st_mtime)
                    }

                    # Extraire l'adresse du nom de fichier
                    filename = db_file.stem  # Sans extension
                    parts = filename.replace(f"{db_type}_", "").split('_')

                    # Retirer le timestamp (format YYYYMMDD_HHMMSS)
                    if len(parts) >= 2 and parts[-2].isdigit() and parts[-1].isdigit():
                        address_parts = parts[:-2]
                        file_info['address'] = '_'.join(address_parts)
                    else:
                        file_info['address'] = filename.replace(f"{db_type}_", "")

                    # Compter les enregistrements
                    conn = sqlite3.connect(str(db_file))
                    cursor = conn.cursor()

                    table_name = 'air_quality' if db_type == 'air_quality' else 'weather'
                    cursor.execute(f"SELECT COUNT(*), MIN(date), MAX(date) FROM {table_name}")
                    count, min_date, max_date = cursor.fetchone()

                    file_info['records'] = count or 0
                    file_info['date_range'] = f"{min_date or 'N/A'} → {max_date or 'N/A'}"

                    conn.close()
                    databases.append(file_info)

                except Exception as e:
                    logger.warning(f"⚠️ Erreur lecture {db_file}: {e}")
                    continue

            # Trier par date de modification (plus récent en premier)
            databases.sort(key=lambda x: x['modified'], reverse=True)

        except Exception as e:
            logger.error(f"❌ Erreur liste bases: {e}")

        return databases


# ============================================================
# CLASSE : BASE DE DONNÉES AIR QUALITY
# ============================================================
class AirQualityDB:
    """Base de données pour la qualité de l'air avec gestion multi-adresses"""

    def __init__(self, address: str = None, force_new: bool = False):
        """
        Initialise la base Air Quality

        Args:
            address: Adresse pour laquelle chercher/créer une base
            force_new: Force création d'une nouvelle base
        """
        if address:
            self.db_path = DatabaseManager.get_or_create_db(address, 'air_quality', force_new)
            self.current_address = address
            self.normalized_address = DatabaseManager.sanitize_address(address)
        else:
            # Fallback vers base par défaut
            self.db_path = str(DB_FOLDER / 'bruxelles_air_quality.db')
            self.current_address = "Bruxelles"
            self.normalized_address = "bruxelles"

        self._initialize_tables()
        logger.info(f"✅ AirQualityDB initialisée: {Path(self.db_path).name}")

    def _initialize_tables(self):
        """Crée les tables air quality si elles n'existent pas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS air_quality (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATETIME,
                latitude REAL,
                longitude REAL,
                address TEXT,
                normalized_address TEXT,
                pm10 REAL,
                pm2_5 REAL,
                carbon_monoxide REAL,
                carbon_dioxide REAL,
                nitrogen_dioxide REAL,
                uv_index REAL,
                uv_index_clear_sky REAL,
                alder_pollen REAL,
                birch_pollen REAL,
                ozone REAL,
                sulphur_dioxide REAL,
                methane REAL,
                ammonia REAL,
                dust REAL,
                aerosol_optical_depth REAL,
                ragweed_pollen REAL,
                olive_pollen REAL,
                mugwort_pollen REAL,
                grass_pollen REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(address, date)
            )
        ''')

        # Index pour recherche rapide
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_address ON air_quality(address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_normalized_address ON air_quality(normalized_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON air_quality(date DESC)')

        conn.commit()
        conn.close()

    def insert_data(self, dataframe: pd.DataFrame) -> bool:
        """
        Insère nouvelles données SANS supprimer les anciennes
        Évite les doublons avec UNIQUE constraint

        Args:
            dataframe: DataFrame avec nouvelles données

        Returns:
            True si succès
        """
        if dataframe is None or dataframe.empty:
            logger.error("❌ DataFrame vide")
            return False

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            inserted = 0
            skipped = 0

            for _, row in dataframe.iterrows():
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO air_quality (
                            date, address, normalized_address, latitude, longitude,
                            pm10, pm2_5, carbon_monoxide, carbon_dioxide, nitrogen_dioxide,
                            uv_index, uv_index_clear_sky, alder_pollen, birch_pollen,
                            ozone, sulphur_dioxide, methane, ammonia, dust,
                            aerosol_optical_depth, ragweed_pollen, olive_pollen,
                            mugwort_pollen, grass_pollen
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        str(row['date']),
                        self.current_address,
                        self.normalized_address,
                        row.get('latitude'),
                        row.get('longitude'),
                        row.get('pm10'),
                        row.get('pm2_5'),
                        row.get('carbon_monoxide'),
                        row.get('carbon_dioxide'),
                        row.get('nitrogen_dioxide'),
                        row.get('uv_index'),
                        row.get('uv_index_clear_sky'),
                        row.get('alder_pollen'),
                        row.get('birch_pollen'),
                        row.get('ozone'),
                        row.get('sulphur_dioxide'),
                        row.get('methane'),
                        row.get('ammonia'),
                        row.get('dust'),
                        row.get('aerosol_optical_depth'),
                        row.get('ragweed_pollen'),
                        row.get('olive_pollen'),
                        row.get('mugwort_pollen'),
                        row.get('grass_pollen')
                    ))

                    if cursor.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1

                except sqlite3.IntegrityError:
                    skipped += 1
                    continue

            conn.commit()

            # Total après insertion
            cursor.execute("SELECT COUNT(*) FROM air_quality WHERE address = ?", (self.current_address,))
            total = cursor.fetchone()[0]
            conn.close()

            if inserted > 0:
                logger.info(f"✅ {inserted} nouveaux enregistrements (ignorés: {skipped}, total: {total})")

            return True

        except Exception as e:
            logger.error(f"❌ Erreur insertion: {e}")
            return False

    def get_connection(self):
        """Connexion à la BDD air quality"""
        return sqlite3.connect(self.db_path)

    def get_all_data(self):
        """Récupère toutes les données air quality"""
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM air_quality ORDER BY date", conn)
        conn.close()
        return df

    def get_location_data(self, address=None):
        """
        Récupère données air quality pour une adresse
        Recherche flexible avec normalized_address
        """
        conn = self.get_connection()

        if address is None:
            address = self.current_address

        normalized_search = DatabaseManager.sanitize_address(address)

        # Essayer correspondance exacte
        query = "SELECT * FROM air_quality WHERE address = ? OR normalized_address = ? ORDER BY date DESC"
        df = pd.read_sql_query(query, conn, params=(address, normalized_search))

        # Si aucun résultat, recherche partielle
        if df.empty:
            keywords = [k for k in normalized_search.split('_') if len(k) > 2]
            if keywords:
                conditions = " OR ".join([f"normalized_address LIKE ?" for _ in keywords])
                query = f"SELECT * FROM air_quality WHERE {conditions} ORDER BY date DESC"
                params = [f"%{k}%" for k in keywords]
                df = pd.read_sql_query(query, conn, params=params)

        conn.close()

        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])

        return df

    def get_location_summary(self, address):
        """Résumé air quality pour une adresse"""
        conn = self.get_connection()
        normalized_search = DatabaseManager.sanitize_address(address)

        query = """
        SELECT
            address, normalized_address, latitude, longitude,
            COUNT(*) as total_records,
            AVG(pm10) as avg_pm10,
            AVG(pm2_5) as avg_pm2_5,
            AVG(nitrogen_dioxide) as avg_no2,
            AVG(ozone) as avg_o3,
            AVG(sulphur_dioxide) as avg_so2,
            AVG(carbon_monoxide) as avg_co,
            AVG(methane) as avg_ch4,
            AVG(ammonia) as avg_nh3,
            MAX(pm10) as max_pm10,
            MAX(pm2_5) as max_pm2_5,
            MIN(date) as start_date,
            MAX(date) as end_date,
            AVG(CASE WHEN pm2_5 > 20 THEN 1 ELSE 0 END) * 100 as pollution_alert_pct
        FROM air_quality
        WHERE address = ? OR normalized_address = ?
        GROUP BY address, normalized_address, latitude, longitude
        """
        df = pd.read_sql_query(query, conn, params=(address, normalized_search))

        # Recherche partielle si nécessaire
        if df.empty:
            keywords = [k for k in normalized_search.split('_') if len(k) > 2]
            if keywords:
                conditions = " OR ".join([f"normalized_address LIKE ?" for _ in keywords])
                query = query.replace("WHERE address = ? OR normalized_address = ?", f"WHERE {conditions}")
                params = [f"%{k}%" for k in keywords]
                df = pd.read_sql_query(query, conn, params=params)

        conn.close()
        return df.iloc[0].to_dict() if not df.empty else None

    def get_date_range(self, address):
        """
        Récupère l'intervalle de dates pour une adresse

        Returns:
            dict avec start_date et end_date ou None
        """
        conn = self.get_connection()
        normalized_search = DatabaseManager.sanitize_address(address)

        query = """
        SELECT MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as total_records
        FROM air_quality WHERE address = ? OR normalized_address = ?
        """
        df = pd.read_sql_query(query, conn, params=(address, normalized_search))

        # Recherche partielle si nécessaire
        if df.empty or df.iloc[0]['total_records'] == 0:
            keywords = [k for k in normalized_search.split('_') if len(k) > 2]
            if keywords:
                conditions = " OR ".join([f"normalized_address LIKE ?" for _ in keywords])
                query = f"SELECT MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as total_records FROM air_quality WHERE {conditions}"
                params = [f"%{k}%" for k in keywords]
                df = pd.read_sql_query(query, conn, params=params)

        conn.close()

        if not df.empty and df.iloc[0]['total_records'] > 0:
            return df.iloc[0].to_dict()
        return None


# ============================================================
# CLASSE : BASE DE DONNÉES MÉTÉO
# ============================================================
class WeatherDB:
    """Base de données pour la météo avec gestion multi-adresses"""

    def __init__(self, address: str = None, force_new: bool = False):
        """
        Initialise la base Weather

        Args:
            address: Adresse pour laquelle chercher/créer une base
            force_new: Force création d'une nouvelle base
        """
        if address:
            self.db_path = DatabaseManager.get_or_create_db(address, 'weather', force_new)
            self.current_address = address
            self.normalized_address = DatabaseManager.sanitize_address(address)
        else:
            # Fallback vers base par défaut
            self.db_path = str(DB_FOLDER / 'weather_bruxelles.db')
            self.current_address = "Bruxelles"
            self.normalized_address = "bruxelles"

        self._initialize_tables()
        logger.info(f"✅ WeatherDB initialisée: {Path(self.db_path).name}")

    def _initialize_tables(self):
        """Crée les tables weather si elles n'existent pas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weather (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATETIME,
                address TEXT,
                normalized_address TEXT,
                latitude REAL,
                longitude REAL,
                temperature REAL,
                feels_like REAL,
                humidity INTEGER,
                pressure INTEGER,
                wind_speed REAL,
                wind_direction INTEGER,
                wind_gusts REAL,
                cloud_cover INTEGER,
                rain REAL,
                snowfall REAL,
                weather_code INTEGER,
                visibility REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(address, date)
            )
        ''')

        # Index pour recherche rapide
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_weather_address ON weather(address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_weather_normalized ON weather(normalized_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_weather_date ON weather(date DESC)')

        conn.commit()
        conn.close()

    def insert_data(self, dataframe: pd.DataFrame) -> bool:
        """
        Insère nouvelles données météo SANS supprimer les anciennes

        Args:
            dataframe: DataFrame avec nouvelles données

        Returns:
            True si succès
        """
        if dataframe is None or dataframe.empty:
            logger.error("❌ DataFrame météo vide")
            return False

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            inserted = 0
            skipped = 0

            for _, row in dataframe.iterrows():
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO weather (
                            date, address, normalized_address, latitude, longitude,
                            temperature, feels_like, humidity, pressure,
                            wind_speed, wind_direction, wind_gusts, cloud_cover,
                            rain, snowfall, weather_code, visibility
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        str(row['date']),
                        self.current_address,
                        self.normalized_address,
                        row.get('latitude'),
                        row.get('longitude'),
                        row.get('temperature'),
                        row.get('feels_like'),
                        row.get('humidity'),
                        row.get('pressure'),
                        row.get('wind_speed'),
                        row.get('wind_direction'),
                        row.get('wind_gusts'),
                        row.get('cloud_cover'),
                        row.get('rain'),
                        row.get('snowfall'),
                        row.get('weather_code'),
                        row.get('visibility')
                    ))

                    if cursor.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1

                except sqlite3.IntegrityError:
                    skipped += 1
                    continue

            conn.commit()

            # Total après insertion
            cursor.execute("SELECT COUNT(*) FROM weather WHERE address = ?", (self.current_address,))
            total = cursor.fetchone()[0]
            conn.close()

            if inserted > 0:
                logger.info(f"✅ Météo: {inserted} nouveaux enregistrements (ignorés: {skipped}, total: {total})")

            return True

        except Exception as e:
            logger.error(f"❌ Erreur insertion météo: {e}")
            return False

    def get_connection(self):
        """Connexion à la BDD weather"""
        return sqlite3.connect(self.db_path)

    def get_all_data(self):
        """Récupère toutes les données météo"""
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM weather ORDER BY date DESC", conn)
        conn.close()
        return df

    def get_hourly_forecast(self, address: str = None, hours: int = 24):
        """Récupère prévisions horaires pour une adresse"""
        conn = self.get_connection()

        if address is None:
            address = self.current_address

        normalized_search = DatabaseManager.sanitize_address(address)

        query = "SELECT * FROM weather WHERE address = ? OR normalized_address = ? ORDER BY date DESC LIMIT ?"
        df = pd.read_sql_query(query, conn, params=(address, normalized_search, hours))

        # Recherche partielle si nécessaire
        if df.empty:
            keywords = [k for k in normalized_search.split('_') if len(k) > 2]
            if keywords:
                conditions = " OR ".join([f"normalized_address LIKE ?" for _ in keywords])
                query = f"SELECT * FROM weather WHERE {conditions} ORDER BY date DESC LIMIT ?"
                params = [f"%{k}%" for k in keywords] + [hours]
                df = pd.read_sql_query(query, conn, params=params)

        conn.close()

        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')

        return df

    def get_weather_summary(self, address: str = None):
        """Résumé météo pour une adresse"""
        conn = self.get_connection()

        if address is None:
            address = self.current_address

        normalized_search = DatabaseManager.sanitize_address(address)

        query = """
        SELECT
            address, normalized_address,
            COUNT(*) as total_records,
            AVG(temperature) as avg_temp,
            MIN(temperature) as min_temp,
            MAX(temperature) as max_temp,
            AVG(humidity) as avg_humidity,
            AVG(wind_speed) as avg_wind,
            MAX(wind_gusts) as max_wind_gusts,
            SUM(rain) as total_rain,
            SUM(snowfall) as total_snow,
            MIN(date) as start_date,
            MAX(date) as end_date
        FROM weather
        WHERE address = ? OR normalized_address = ?
        GROUP BY address, normalized_address
        """
        df = pd.read_sql_query(query, conn, params=(address, normalized_search))

        # Recherche partielle si nécessaire
        if df.empty:
            keywords = [k for k in normalized_search.split('_') if len(k) > 2]
            if keywords:
                conditions = " OR ".join([f"normalized_address LIKE ?" for _ in keywords])
                query = query.replace("WHERE address = ? OR normalized_address = ?", f"WHERE {conditions}")
                params = [f"%{k}%" for k in keywords]
                df = pd.read_sql_query(query, conn, params=params)

        conn.close()
        return df.iloc[0].to_dict() if not df.empty else None

    def get_date_range(self, address: str = None):
        """Récupère l'intervalle de dates météo pour une adresse"""
        conn = self.get_connection()

        if address is None:
            address = self.current_address

        normalized_search = DatabaseManager.sanitize_address(address)

        query = "SELECT MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as total_records FROM weather WHERE address = ? OR normalized_address = ?"
        df = pd.read_sql_query(query, conn, params=(address, normalized_search))

        # Recherche partielle si nécessaire
        if df.empty or df.iloc[0]['total_records'] == 0:
            keywords = [k for k in normalized_search.split('_') if len(k) > 2]
            if keywords:
                conditions = " OR ".join([f"normalized_address LIKE ?" for _ in keywords])
                query = f"SELECT MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as total_records FROM weather WHERE {conditions}"
                params = [f"%{k}%" for k in keywords]
                df = pd.read_sql_query(query, conn, params=params)

        conn.close()

        if not df.empty and df.iloc[0]['total_records'] > 0:
            return df.iloc[0].to_dict()
        return None

    def save_current_weather(self, address: str, lat: float, lon: float, data: Dict) -> bool:
        """Sauvegarde météo actuelle"""
        if 'timestamp' not in data:
            logger.error("❌ Timestamp manquant")
            return False

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR IGNORE INTO weather (
                    date, address, normalized_address, latitude, longitude,
                    temperature, feels_like, humidity, pressure,
                    wind_speed, wind_direction, wind_gusts,
                    rain, snowfall, cloud_cover, weather_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(data['timestamp']),
                address,
                self.normalized_address,
                lat, lon,
                data.get('temperature'), data.get('feels_like'),
                data.get('humidity'), data.get('pressure'),
                data.get('wind_speed'), data.get('wind_angle'),
                data.get('wind_gusts'),
                data.get('rain'), data.get('snowfall'),
                data.get('cloud_cover'), data.get('weather_code')
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde: {e}")
            return False

    def save_hourly_weather(self, address: str, lat: float, lon: float, hourly_df: pd.DataFrame) -> bool:
        """Sauvegarde prévisions horaires"""
        if hourly_df.empty:
            return False

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            inserted = 0

            for _, row in hourly_df.iterrows():
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO weather (
                            date, address, normalized_address, latitude, longitude,
                            temperature, feels_like, humidity, pressure,
                            wind_speed, wind_direction, wind_gusts,
                            rain, snowfall, cloud_cover, weather_code
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        str(row.get('date')),
                        self.current_address,
                        self.normalized_address,
                        lat, lon,
                        row.get('temperature'), row.get('feels_like'),
                        row.get('humidity'), row.get('pressure'),
                        row.get('wind_speed'), row.get('wind_direction'),
                        row.get('wind_gusts'),
                        row.get('rain'), row.get('snowfall'),
                        row.get('cloud_cover'), row.get('weather_code')
                    ))

                    if cursor.rowcount > 0:
                        inserted += 1

                except sqlite3.IntegrityError:
                    continue

            conn.commit()
            conn.close()

            if inserted > 0:
                logger.info(f"✅ {inserted} prévisions horaires sauvegardées")

            return True

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde horaire: {e}")
            return False
