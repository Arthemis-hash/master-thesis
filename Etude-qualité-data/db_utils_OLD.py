#!/usr/bin/env python3
"""
============================================================
GESTIONNAIRE BASES DE DONNÉES - Brussels Air Quality
============================================================
Architecture optimisée pour:
- API Open Data Brussels (qualité air)
- Données météo IRM
- Validation avec triggers SQL
- Multi-adresses avec géolocalisation
============================================================
"""

import sqlite3
import pandas as pd
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

DB_FOLDER = Path(__file__).parent / "databases"
DB_FOLDER.mkdir(exist_ok=True)


# ============================================================
# GESTIONNAIRE BASE - CLASSE ABSTRAITE
# ============================================================

class DatabaseManager:
    """Gestionnaire centralisé multi-bases"""

    @staticmethod
    def sanitize_address(address: str) -> str:
        """
        Normalise adresse pour nommage UNIQUE incluant rue + numéro
        Ex: "151 boulevard du triomphe, 1050 Bruxelles" -> "151_boulevard_du_triomphe_1050_bruxelles"
        Ex: "158 boulevard du triomphe, 1050 Bruxelles" -> "158_boulevard_du_triomphe_1050_bruxelles"
        IMPORTANT: Chaque adresse doit avoir sa propre DB, même si elles sont dans la même rue
        """
        if not address:
            return "unknown"
        
        # Nettoyer l'adresse complète en conservant TOUS les détails
        normalized = address.lower().strip()
        
        # Remplacer les caractères spéciaux par des underscores
        normalized = re.sub(r'[^\w\s-]', '_', normalized)
        
        # Remplacer les espaces multiples par un seul underscore
        normalized = re.sub(r'\s+', '_', normalized)
        
        # Supprimer les underscores multiples
        normalized = re.sub(r'_+', '_', normalized)
        
        # Supprimer les underscores au début et à la fin
        normalized = normalized.strip('_')
        
        # Limiter la longueur tout en gardant l'unicité
        if len(normalized) > 80:
            # Garder le début (rue + numéro) et la fin (code postal + commune)
            parts = normalized.split('_')
            if len(parts) > 4:
                # Garder les 3 premiers (numéro + rue) et les 2 derniers (code postal + commune)
                normalized = '_'.join(parts[:3] + parts[-2:])
            normalized = normalized[:80]
        
        return normalized

    @staticmethod
    def generate_db_name(address: str, db_type: str = 'brussels_air') -> str:
        """
        Génère nom DB unique: {type}_{adresse}_{timestamp}.db
        """
        clean_addr = DatabaseManager.sanitize_address(address)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{db_type}_{clean_addr}_{timestamp}.db"
        return str(DB_FOLDER / filename)

    @staticmethod
    def find_existing_db(address: str, db_type: str = 'brussels_air') -> Optional[str]:
        """
        Recherche DB existante pour cette adresse (la plus récente)
        """
        normalized = DatabaseManager.sanitize_address(address)

        # Recherche exacte avec wildcard pour timestamp
        matching = list(DB_FOLDER.glob(f"{db_type}_{normalized}_*.db"))
        
        # Si pas de résultat, essayer sans underscore pour compatibilité
        if not matching:
            # Essayer format alternatif (ex: air_quality_{address}.db)
            if db_type == 'brussels_air':
                matching = list(DB_FOLDER.glob(f"air_quality_{normalized}.db"))
            elif db_type == 'weather':
                matching = list(DB_FOLDER.glob(f"weather_{normalized}.db"))
        
        if matching:
            return str(max(matching, key=lambda p: p.stat().st_mtime))

        # Recherche partielle par mots-clés
        keywords = [k for k in normalized.split('_') if len(k) > 2]
        if keywords:
            all_dbs = list(DB_FOLDER.glob(f"{db_type}_*.db"))
            for db_file in sorted(all_dbs, key=lambda p: p.stat().st_mtime, reverse=True):
                matches = sum(1 for kw in keywords if kw in db_file.name)
                if matches >= min(2, len(keywords)):
                    return str(db_file)

        return None

    @staticmethod
    def get_or_create_db(address: str, db_type: str = 'brussels_air', force_new: bool = False) -> str:
        """Récupère DB existante ou crée nouvelle"""
        if not force_new:
            existing = DatabaseManager.find_existing_db(address, db_type)
            if existing:
                logger.info(f"📂 DB existante: {Path(existing).name}")
                return existing

        new_db = DatabaseManager.generate_db_name(address, db_type)
        logger.info(f"🆕 Nouvelle DB: {Path(new_db).name}")
        return new_db


# ============================================================
# BASE QUALITÉ AIR BRUSSELS
# ============================================================

class BrusselsAirQualityDB:
    """
    Base de données pour API Open Data Brussels
    Support multi-polluants avec validation
    """

    # Mapping API Brussels -> colonnes DB
    POLLUTANT_COLUMNS = {
        'no2': 'nitrogen_dioxide',
        'o3': 'ozone',
        'pm10': 'pm10',
        'pm2_5': 'pm2_5'
    }

    def __init__(self, address: str = None, force_new: bool = False):
        if address:
            self.db_path = DatabaseManager.get_or_create_db(address, 'brussels_air', force_new)
            self.current_address = address
            self.normalized_address = DatabaseManager.sanitize_address(address)
        else:
            self.db_path = str(DB_FOLDER / 'brussels_air_default.db')
            self.current_address = "Brussels"
            self.normalized_address = "brussels"

        self._initialize_schema()
        self._create_triggers()
        logger.info(f"✅ BrusselsAirQualityDB: {Path(self.db_path).name}")

    def _initialize_schema(self):
        """Création schéma tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Table principale
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS air_quality (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                address TEXT NOT NULL,
                normalized_address TEXT,
                latitude REAL,
                longitude REAL,
                station_name TEXT,
                station_code TEXT,
                pm10 REAL,
                pm2_5 REAL,
                nitrogen_dioxide REAL,
                ozone REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(address, timestamp, station_code)
            )
        ''')

        # Table anomalies
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                address TEXT,
                timestamp DATETIME,
                issue_type TEXT,
                pollutant TEXT,
                value REAL,
                station_code TEXT,
                corrected BOOLEAN DEFAULT 0
            )
        ''')

        # Table métadonnées stations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stations (
                station_code TEXT PRIMARY KEY,
                station_name TEXT,
                latitude REAL,
                longitude REAL,
                distance_from_address REAL,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Index
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON air_quality(timestamp DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_address ON air_quality(address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_station ON air_quality(station_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_anomalies_addr ON data_anomalies(address, corrected)')

        conn.commit()
        conn.close()

    def _create_triggers(self):
        """Triggers validation automatique"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Trigger: filtrer erreurs capteur (-9999)
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS filter_sensor_errors
            BEFORE INSERT ON air_quality
            FOR EACH ROW
            WHEN NEW.pm10 = -9999 OR NEW.pm2_5 = -9999 
                 OR NEW.nitrogen_dioxide = -9999 OR NEW.ozone = -9999
            BEGIN
                SELECT RAISE(IGNORE);
            END;
        ''')

        # Trigger: logger valeurs extrêmes
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS log_extreme_values
            AFTER INSERT ON air_quality
            FOR EACH ROW
            WHEN NEW.pm10 > 500 OR NEW.pm2_5 > 300 
                 OR NEW.nitrogen_dioxide > 1000 OR NEW.ozone > 600
            BEGIN
                INSERT INTO data_anomalies (address, timestamp, issue_type, pollutant, value, station_code)
                SELECT NEW.address, NEW.timestamp, 'extreme_value',
                    CASE 
                        WHEN NEW.pm10 > 500 THEN 'pm10'
                        WHEN NEW.pm2_5 > 300 THEN 'pm2_5'
                        WHEN NEW.nitrogen_dioxide > 1000 THEN 'no2'
                        WHEN NEW.ozone > 600 THEN 'o3'
                    END,
                    CASE 
                        WHEN NEW.pm10 > 500 THEN NEW.pm10
                        WHEN NEW.pm2_5 > 300 THEN NEW.pm2_5
                        WHEN NEW.nitrogen_dioxide > 1000 THEN NEW.nitrogen_dioxide
                        WHEN NEW.ozone > 600 THEN NEW.ozone
                    END,
                    NEW.station_code;
            END;
        ''')

        conn.commit()
        conn.close()

    def insert_brussels_data(self, df: pd.DataFrame, pollutant: str) -> Dict[str, int]:
        """
        Insertion données API Brussels
        Retourne statistiques pour UI
        """
        if df.empty:
            return {'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        db_column = self.POLLUTANT_COLUMNS.get(pollutant, pollutant)

        for _, row in df.iterrows():
            try:
                # Vérifier existence
                cursor.execute('''
                    SELECT id FROM air_quality 
                    WHERE address = ? AND timestamp = ? AND station_code = ?
                ''', (self.current_address, str(row['timestamp']), row.get('station_code', 'N/A')))

                existing = cursor.fetchone()

                if existing:
                    # UPDATE
                    cursor.execute(f'''
                        UPDATE air_quality 
                        SET {db_column} = ?, latitude = ?, longitude = ?, station_name = ?
                        WHERE id = ?
                    ''', (
                        row['value'],
                        row.get('latitude'),
                        row.get('longitude'),
                        row.get('station_name'),
                        existing[0]
                    ))
                    if cursor.rowcount > 0:
                        stats['updated'] += 1
                else:
                    # INSERT
                    cursor.execute(f'''
                        INSERT INTO air_quality (
                            timestamp, address, normalized_address, latitude, longitude,
                            station_name, station_code, {db_column}
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        str(row['timestamp']),
                        self.current_address,
                        self.normalized_address,
                        row.get('latitude'),
                        row.get('longitude'),
                        row.get('station_name'),
                        row.get('station_code', 'N/A'),
                        row['value']
                    ))
                    if cursor.rowcount > 0:
                        stats['inserted'] += 1

                # Upsert station
                if row.get('station_code'):
                    cursor.execute('''
                        INSERT OR REPLACE INTO stations (station_code, station_name, latitude, longitude)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        row['station_code'],
                        row.get('station_name'),
                        row.get('latitude'),
                        row.get('longitude'
                        )
                    ))

            except sqlite3.IntegrityError:
                stats['skipped'] += 1
            except Exception as e:
                logger.warning(f"⚠️ Erreur insertion: {e}")
                stats['errors'] += 1

        conn.commit()
        conn.close()

        logger.info(f"✅ {pollutant.upper()}: +{stats['inserted']} ~{stats['updated']}")
        return stats

    def get_connection(self):
        """Connexion SQLite"""
        return sqlite3.connect(self.db_path)

    def get_actual_address_from_db(self) -> Optional[str]:
        """
        Récupère la première adresse réelle stockée dans la base
        Utile lors du chargement d'une base existante
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT address FROM air_quality LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        return None

    def get_all_data(self, limit: Optional[int] = None, ignore_address_filter: bool = False) -> pd.DataFrame:
        """
        Récupère toutes les données
        
        Args:
            limit: Nombre max de lignes à retourner
            ignore_address_filter: Si True, ignore le filtre sur current_address
        """
        if ignore_address_filter:
            query = "SELECT * FROM air_quality ORDER BY timestamp DESC"
        else:
            query = "SELECT * FROM air_quality WHERE address = ? ORDER BY timestamp DESC"
        
        if limit:
            query += f" LIMIT {limit}"

        conn = self.get_connection()
        if ignore_address_filter:
            df = pd.read_sql_query(query, conn)
        else:
            df = pd.read_sql_query(query, conn, params=(self.current_address,))
        conn.close()

        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        return df

    def get_pollutant_data(self, pollutant: str, ignore_address_filter: bool = False) -> pd.DataFrame:
        """
        Récupère données d'un polluant spécifique
        
        Args:
            pollutant: Code du polluant (pm2_5, pm10, no2, o3)
            ignore_address_filter: Si True, ignore le filtre sur current_address
        """
        db_column = self.POLLUTANT_COLUMNS.get(pollutant, pollutant)
        
        if ignore_address_filter:
            query = f"""
                SELECT timestamp, {db_column} as value, station_name, latitude, longitude
                FROM air_quality 
                WHERE {db_column} IS NOT NULL
                ORDER BY timestamp DESC
            """
            conn = self.get_connection()
            df = pd.read_sql_query(query, conn)
        else:
            query = f"""
                SELECT timestamp, {db_column} as value, station_name, latitude, longitude
                FROM air_quality 
                WHERE address = ? AND {db_column} IS NOT NULL
                ORDER BY timestamp DESC
            """
            conn = self.get_connection()
            df = pd.read_sql_query(query, conn, params=(self.current_address,))
        
        conn.close()

        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        return df

    def get_summary(self) -> Dict:
        """Statistiques résumées"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT station_code) as num_stations,
                MIN(timestamp) as start_date,
                MAX(timestamp) as end_date,
                AVG(pm10) as avg_pm10,
                AVG(pm2_5) as avg_pm2_5,
                AVG(nitrogen_dioxide) as avg_no2,
                AVG(ozone) as avg_o3,
                MAX(pm10) as max_pm10,
                MAX(pm2_5) as max_pm2_5
            FROM air_quality
            WHERE address = ?
        ''', (self.current_address,))

        result = cursor.fetchone()
        conn.close()

        if not result:
            return {}

        return {
            'total_records': result[0],
            'num_stations': result[1],
            'start_date': result[2],
            'end_date': result[3],
            'avg_pm10': round(result[4], 2) if result[4] else None,
            'avg_pm2_5': round(result[5], 2) if result[5] else None,
            'avg_no2': round(result[6], 2) if result[6] else None,
            'avg_o3': round(result[7], 2) if result[7] else None,
            'max_pm10': round(result[8], 2) if result[8] else None,
            'max_pm2_5': round(result[9], 2) if result[9] else None
        }

    def get_stations(self) -> pd.DataFrame:
        """Liste stations enregistrées"""
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM stations", conn)
        conn.close()
        return df

    def get_anomalies(self, uncorrected_only: bool = True) -> pd.DataFrame:
        """Récupère anomalies détectées"""
        query = "SELECT * FROM data_anomalies WHERE address = ?"
        if uncorrected_only:
            query += " AND corrected = 0"
        query += " ORDER BY detected_at DESC"

        conn = self.get_connection()
        df = pd.read_sql_query(query, conn, params=(self.current_address,))
        conn.close()

        if not df.empty:
            df['detected_at'] = pd.to_datetime(df['detected_at'])

        return df

    def mark_corrected(self, anomaly_id: int):
        """Marque anomalie comme corrigée"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE data_anomalies SET corrected = 1 WHERE id = ?', (anomaly_id,))
        conn.commit()
        conn.close()

    def delete_anomalous_records(self, anomaly_id: int):
        """Supprime enregistrements liés à une anomalie"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Récupérer info anomalie
        cursor.execute('SELECT timestamp, pollutant FROM data_anomalies WHERE id = ?', (anomaly_id,))
        result = cursor.fetchone()

        if result:
            timestamp, pollutant = result
            db_column = self.POLLUTANT_COLUMNS.get(pollutant, pollutant)

            cursor.execute(f'''
                UPDATE air_quality 
                SET {db_column} = NULL 
                WHERE address = ? AND timestamp = ?
            ''', (self.current_address, timestamp))

            self.mark_corrected(anomaly_id)

        conn.commit()
        conn.close()


# ============================================================
# BASE MÉTÉO (FUTURE EXTENSION)
# ============================================================

class WeatherDB:
    """Base météo IRM avec support multi-stations"""

    def __init__(self, address: str = None, force_new: bool = False):
        if address:
            self.db_path = DatabaseManager.get_or_create_db(address, 'weather', force_new)
            self.current_address = address
            self.normalized_address = DatabaseManager.sanitize_address(address)
        else:
            self.db_path = str(DB_FOLDER / 'weather_default.db')
            self.current_address = "Brussels"
            self.normalized_address = "brussels"

        self._initialize_schema()
        logger.info(f"✅ WeatherDB: {Path(self.db_path).name}")

    def _initialize_schema(self):
        """Schéma météo IRM"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weather (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                address TEXT NOT NULL,
                station_code TEXT,
                station_name TEXT,
                latitude REAL,
                longitude REAL,
                temperature REAL,
                feels_like REAL,
                humidity INTEGER,
                pressure REAL,
                wind_speed REAL,
                wind_direction INTEGER,
                wind_direction_text TEXT,
                wind_gusts REAL,
                cloud_cover INTEGER,
                visibility REAL,
                weather_code INTEGER,
                precipitation_1h REAL,
                sunshine_1h REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(address, timestamp, station_code)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_weather_ts ON weather(timestamp DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_weather_addr ON weather(address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_weather_station ON weather(station_code)')

        conn.commit()
        conn.close()

    def insert_weather_data(self, weather_data: Dict) -> bool:
        """
        Insertion donnée météo IRM
        """
        if not weather_data:
            return False

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO weather (
                    timestamp, address, station_code, station_name,
                    latitude, longitude, temperature, feels_like,
                    humidity, pressure, wind_speed, wind_direction,
                    wind_direction_text, wind_gusts, cloud_cover,
                    visibility, weather_code, precipitation_1h, sunshine_1h
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(weather_data['timestamp']),
                self.current_address,
                weather_data.get('station_code'),
                weather_data.get('station_name'),
                weather_data.get('latitude'),
                weather_data.get('longitude'),
                weather_data.get('temperature'),
                weather_data.get('feels_like'),
                weather_data.get('humidity'),
                weather_data.get('pressure'),
                weather_data.get('wind_speed'),
                weather_data.get('wind_direction'),
                weather_data.get('wind_direction_text'),
                weather_data.get('wind_gusts'),
                weather_data.get('cloud_cover'),
                weather_data.get('visibility'),
                weather_data.get('weather_code'),
                weather_data.get('precipitation_1h'),
                weather_data.get('sunshine_1h')
            ))

            conn.commit()
            success = cursor.rowcount > 0
            conn.close()

            if success:
                logger.info(f"✅ Météo enregistrée: {weather_data.get('station_name')}")

            return success

        except Exception as e:
            logger.error(f"❌ Erreur insertion météo: {e}")
            conn.close()
            return False

    def insert_multiple(self, weather_list: List[Dict]) -> Dict[str, int]:
        """
        Insertion multiple (stations Bruxelles)
        """
        stats = {'inserted': 0, 'errors': 0}

        for weather_data in weather_list:
            if self.insert_weather_data(weather_data):
                stats['inserted'] += 1
            else:
                stats['errors'] += 1

        return stats

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def get_actual_address_from_db(self) -> Optional[str]:
        """
        Récupère la première adresse réelle stockée dans la base
        Utile lors du chargement d'une base existante
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT address FROM weather LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        return None

    def get_latest_weather(self) -> Optional[Dict]:
        """Récupère dernière observation météo"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM weather 
            WHERE address = ?
            ORDER BY timestamp DESC 
            LIMIT 1
        ''', (self.current_address,))

        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, result))

    def get_all_data(self, limit: Optional[int] = 100, ignore_address_filter: bool = False) -> pd.DataFrame:
        """
        Récupère toutes les données météo
        
        Args:
            limit: Nombre max de lignes à retourner
            ignore_address_filter: Si True, ignore le filtre sur current_address
        """
        if ignore_address_filter:
            query = "SELECT * FROM weather ORDER BY timestamp DESC"
        else:
            query = "SELECT * FROM weather WHERE address = ? ORDER BY timestamp DESC"
        
        if limit:
            query += f" LIMIT {limit}"

        conn = self.get_connection()
        if ignore_address_filter:
            df = pd.read_sql_query(query, conn)
        else:
            df = pd.read_sql_query(query, conn, params=(self.current_address,))
        conn.close()

        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        return df

    def get_summary(self) -> Dict:
        """Statistiques météo"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT 
                COUNT(*) as total_records,
                MIN(timestamp) as start_date,
                MAX(timestamp) as end_date,
                AVG(temperature) as avg_temp,
                MIN(temperature) as min_temp,
                MAX(temperature) as max_temp,
                AVG(humidity) as avg_humidity,
                AVG(wind_speed) as avg_wind,
                MAX(wind_gusts) as max_wind_gusts,
                SUM(precipitation_1h) as total_precip
            FROM weather
            WHERE address = ?
        ''', (self.current_address,))

        result = cursor.fetchone()
        conn.close()

        if not result or result[0] == 0:
            return {}

        return {
            'total_records': result[0],
            'start_date': result[1],
            'end_date': result[2],
            'avg_temp': round(result[3], 1) if result[3] else None,
            'min_temp': round(result[4], 1) if result[4] else None,
            'max_temp': round(result[5], 1) if result[5] else None,
            'avg_humidity': round(result[6], 1) if result[6] else None,
            'avg_wind': round(result[7], 1) if result[7] else None,
            'max_wind_gusts': round(result[8], 1) if result[8] else None,
            'total_precip': round(result[9], 2) if result[9] else 0
        }


# ============================================================
# UTILITAIRES GLOBAUX
# ============================================================

def list_all_databases() -> pd.DataFrame:
    """Liste toutes les DBs disponibles"""
    dbs = []

    for db_file in DB_FOLDER.glob("*.db"):
        try:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()

            # Déterminer type
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cursor.fetchall()]

            if 'air_quality' in tables:
                db_type = 'air_quality'
                cursor.execute('SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM air_quality')
            elif 'weather' in tables:
                db_type = 'weather'
                cursor.execute('SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM weather')
            else:
                conn.close()
                continue

            count, min_ts, max_ts = cursor.fetchone()
            conn.close()

            dbs.append({
                'filename': db_file.name,
                'path': str(db_file),
                'type': db_type,
                'records': count or 0,
                'date_range': f"{min_ts or 'N/A'} → {max_ts or 'N/A'}",
                'size_mb': round(db_file.stat().st_size / (1024 * 1024), 2),
                'modified': datetime.fromtimestamp(db_file.stat().st_mtime)
            })

        except Exception as e:
            logger.warning(f"⚠️ Erreur lecture {db_file.name}: {e}")

    return pd.DataFrame(dbs).sort_values('modified', ascending=False) if dbs else pd.DataFrame()