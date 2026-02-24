-- ============================================================
-- INITIALISATION PostgreSQL + PostGIS
-- Brussels Air Quality Platform
-- ============================================================

-- Activer l'extension PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Vérifier l'installation de PostGIS
SELECT PostGIS_Version();

-- Créer des index spatiaux pour optimiser les requêtes géospatiales
-- Ces index seront appliqués après la création des tables par Prisma

-- ============================================================
-- FONCTIONS UTILITAIRES GÉOSPATIALES
-- ============================================================

-- Fonction pour calculer la distance entre deux points (en mètres)
CREATE OR REPLACE FUNCTION calculate_distance(
    lat1 FLOAT,
    lon1 FLOAT,
    lat2 FLOAT,
    lon2 FLOAT
) RETURNS FLOAT AS $$
BEGIN
    RETURN ST_Distance(
        ST_GeographyFromText('POINT(' || lon1 || ' ' || lat1 || ')'),
        ST_GeographyFromText('POINT(' || lon2 || ' ' || lat2 || ')')
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Fonction pour trouver les stations dans un rayon donné (en mètres)
CREATE OR REPLACE FUNCTION find_stations_within_radius(
    center_lat FLOAT,
    center_lon FLOAT,
    radius_meters FLOAT
) RETURNS TABLE (
    station_id INT,
    station_code TEXT,
    station_name TEXT,
    distance_m FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id,
        s.station_code,
        s.station_name,
        ST_Distance(
            s.geom::geography,
            ST_SetSRID(ST_MakePoint(center_lon, center_lat), 4326)::geography
        ) as distance_m
    FROM stations s
    WHERE s.geom IS NOT NULL
      AND ST_DWithin(
          s.geom::geography,
          ST_SetSRID(ST_MakePoint(center_lon, center_lat), 4326)::geography,
          radius_meters
      )
    ORDER BY distance_m ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Fonction pour créer un point géométrique à partir de lat/lon
CREATE OR REPLACE FUNCTION create_point_geom(
    latitude FLOAT,
    longitude FLOAT
) RETURNS geometry AS $$
BEGIN
    RETURN ST_SetSRID(ST_MakePoint(longitude, latitude), 4326);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================
-- TRIGGERS POUR AUTO-GÉNÉRATION DES GEOMETRIES
-- ============================================================

-- Trigger pour addresses
CREATE OR REPLACE FUNCTION update_address_geom()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.geom := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger pour stations
CREATE OR REPLACE FUNCTION update_station_geom()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.geom := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Note: Les triggers seront créés après la migration Prisma
-- via un script séparé car Prisma doit d'abord créer les tables

-- ============================================================
-- VUES UTILES
-- ============================================================

-- Vue pour les statistiques de qualité de l'air par adresse
CREATE OR REPLACE VIEW air_quality_summary AS
SELECT
    a.id as address_id,
    a.full_address,
    COUNT(aq.id) as total_records,
    AVG(aq.pm10) as avg_pm10,
    AVG(aq.pm2_5) as avg_pm25,
    AVG(aq.nitrogen_dioxide) as avg_no2,
    AVG(aq.ozone) as avg_o3,
    MAX(aq.timestamp) as last_measurement,
    AVG(aq.aqi_value) as avg_aqi
FROM addresses a
LEFT JOIN air_quality_records aq ON a.id = aq.address_id
GROUP BY a.id, a.full_address;

-- Vue pour les dernières mesures météo par adresse
CREATE OR REPLACE VIEW latest_weather AS
SELECT DISTINCT ON (address_id)
    address_id,
    timestamp,
    temperature,
    feels_like,
    humidity,
    wind_speed,
    precipitation_1h
FROM weather_records
ORDER BY address_id, timestamp DESC;

-- ============================================================
-- CONFIGURATION PERFORMANCE
-- ============================================================

-- Augmenter la mémoire pour les requêtes spatiales
ALTER SYSTEM SET work_mem = '256MB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';
ALTER SYSTEM SET effective_cache_size = '4GB';

-- Statistiques auto
ALTER SYSTEM SET autovacuum = on;

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';
