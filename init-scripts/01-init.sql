-- ============================================================
# POSTGRESQL INITIALIZATION SCRIPT
# ============================================================
# PostgreSQL + PostGIS schema for Air Quality Platform
# Auto-executed on container first start
# ============================================================

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
# USERS & AUTHENTICATION
# ============================================================

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_email ON users(email);

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    jwt_token VARCHAR(1000) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sessions_jwt ON sessions(jwt_token);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- ============================================================
# ADDRESSES & GEOLOCATION
# ============================================================

CREATE TABLE IF NOT EXISTS addresses (
    id SERIAL PRIMARY KEY,
    full_address VARCHAR(500) NOT NULL,
    normalized_address VARCHAR(500) NOT NULL UNIQUE,
    street_number VARCHAR(20),
    street_name VARCHAR(200),
    postal_code VARCHAR(20),
    city VARCHAR(100),
    country VARCHAR(100) DEFAULT 'Belgium',
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geom geometry(Point, 4326),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_addresses_normalized ON addresses(normalized_address);
CREATE INDEX idx_addresses_postal ON addresses(postal_code);
CREATE INDEX idx_addresses_city ON addresses(city);
CREATE INDEX idx_addresses_geom ON addresses USING GIST(geom);

-- ============================================================
# MEASUREMENT STATIONS
# ============================================================

CREATE TABLE IF NOT EXISTS stations (
    id SERIAL PRIMARY KEY,
    station_code VARCHAR(50) NOT NULL UNIQUE,
    station_name VARCHAR(200) NOT NULL,
    station_type VARCHAR(50) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geom geometry(Point, 4326),
    elevation DOUBLE PRECISION,
    metadata JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_stations_code ON stations(station_code);
CREATE INDEX idx_stations_type ON stations(station_type);
CREATE INDEX idx_stations_geom ON stations USING GIST(geom);

-- ============================================================
# AIR QUALITY RECORDS
# ============================================================

CREATE TABLE IF NOT EXISTS air_quality_records (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    station_id INTEGER REFERENCES stations(id) ON DELETE SET NULL,
    
    -- Pollutants (µg/m³)
    pm10 DOUBLE PRECISION,
    pm2_5 DOUBLE PRECISION,
    nitrogen_dioxide DOUBLE PRECISION,
    ozone DOUBLE PRECISION,
    sulfur_dioxide DOUBLE PRECISION,
    carbon_monoxide DOUBLE PRECISION,
    
    -- AQI
    aqi_value INTEGER,
    aqi_category VARCHAR(50),
    
    -- Metadata
    data_source VARCHAR(100) DEFAULT 'brussels_opendata',
    data_quality VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE (address_id, timestamp, station_id)
);

CREATE INDEX idx_air_quality_timestamp ON air_quality_records(timestamp DESC);
CREATE INDEX idx_air_quality_address ON air_quality_records(address_id);
CREATE INDEX idx_air_quality_station ON air_quality_records(station_id);
CREATE INDEX idx_air_quality_aqi ON air_quality_records(aqi_category);

-- ============================================================
# WEATHER RECORDS
# ============================================================

CREATE TABLE IF NOT EXISTS weather_records (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    station_id INTEGER REFERENCES stations(id) ON DELETE SET NULL,
    
    -- Temperature & feels
    temperature DOUBLE PRECISION,
    feels_like DOUBLE PRECISION,
    humidity INTEGER,
    pressure DOUBLE PRECISION,
    dew_point DOUBLE PRECISION,
    
    -- Wind
    wind_speed DOUBLE PRECISION,
    wind_direction INTEGER,
    wind_direction_text VARCHAR(20),
    wind_gusts DOUBLE PRECISION,
    
    -- Precipitations & visibility
    precipitation_1h DOUBLE PRECISION,
    precipitation_24h DOUBLE PRECISION,
    cloud_cover INTEGER,
    visibility DOUBLE PRECISION,
    
    -- Sun & UV
    sunshine_1h DOUBLE PRECISION,
    uv_index DOUBLE PRECISION,
    
    -- Weather code
    weather_code INTEGER,
    weather_description VARCHAR(200),
    
    -- Metadata
    data_source VARCHAR(100) DEFAULT 'irm',
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE (address_id, timestamp, station_id)
);

CREATE INDEX idx_weather_timestamp ON weather_records(timestamp DESC);
CREATE INDEX idx_weather_address ON weather_records(address_id);
CREATE INDEX idx_weather_station ON weather_records(station_id);

-- ============================================================
# DATA ANOMALIES
# ============================================================

CREATE TABLE IF NOT EXISTS data_anomalies (
    id SERIAL PRIMARY KEY,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    record_type VARCHAR(50) NOT NULL,
    record_id INTEGER,
    issue_type VARCHAR(100) NOT NULL,
    pollutant VARCHAR(50),
    value DOUBLE PRECISION,
    threshold DOUBLE PRECISION,
    description TEXT,
    is_corrected BOOLEAN DEFAULT false,
    corrected_at TIMESTAMP WITH TIME ZONE,
    correction_note TEXT
);

CREATE INDEX idx_anomalies_detected ON data_anomalies(detected_at DESC);
CREATE INDEX idx_anomalies_type ON data_anomalies(record_type);
CREATE INDEX idx_anomalies_corrected ON data_anomalies(is_corrected);

-- ============================================================
# TRAFFIC RECORDS
# ============================================================

CREATE TABLE IF NOT EXISTS traffic_records (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    light_vehicles INTEGER,
    utility_vehicles INTEGER,
    heavy_vehicles INTEGER,
    motorcycles INTEGER,
    bicycles INTEGER,
    pedestrians INTEGER,
    
    traffic_nuisance_score DOUBLE PRECISION,
    equivalent_pcu DOUBLE PRECISION,
    
    road_type VARCHAR(50),
    lane_count INTEGER,
    speed_limit INTEGER,
    measurement_method VARCHAR(50),
    data_source VARCHAR(100) DEFAULT 'osm_traffic',
    data_quality VARCHAR(50),
    road_geometry geometry(LineString, 4326),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE (address_id, timestamp)
);

CREATE INDEX idx_traffic_timestamp ON traffic_records(timestamp DESC);
CREATE INDEX idx_traffic_address ON traffic_records(address_id);
CREATE INDEX idx_traffic_nuisance ON traffic_records(traffic_nuisance_score);
CREATE INDEX idx_traffic_geom ON traffic_records USING GIST(road_geometry);

-- ============================================================
# GREEN SPACE METRICS (3-30-300 Rule)
# ============================================================

CREATE TABLE IF NOT EXISTS green_space_metrics (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 3 trees visibility
    trees_visible_count INTEGER,
    has_minimum_3_trees BOOLEAN,
    visibility_score DOUBLE PRECISION,
    
    -- 30% canopy
    canopy_coverage_pct DOUBLE PRECISION,
    canopy_area_m2 DOUBLE PRECISION,
    total_area_analyzed_m2 DOUBLE PRECISION,
    canopy_score DOUBLE PRECISION,
    
    -- 300m accessibility
    distance_to_nearest_park_m DOUBLE PRECISION,
    nearest_park_name VARCHAR(200),
    nearest_park_area_m2 DOUBLE PRECISION,
    within_access_radius BOOLEAN,
    accessibility_score DOUBLE PRECISION,
    
    -- Composite score
    green_index_score DOUBLE PRECISION,
    
    -- Additional metrics
    tree_diversity_index DOUBLE PRECISION,
    vegetation_density_pct DOUBLE PRECISION,
    green_space_types_mix JSONB,
    
    -- Geometry
    analysis_buffer_geometry geometry(Polygon, 4326),
    nearest_park_geometry geometry(Polygon, 4326),
    
    -- Methods
    detection_method VARCHAR(50),
    data_source VARCHAR(100) DEFAULT 'yolo_streetview',
    confidence_level DOUBLE PRECISION,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_green_address ON green_space_metrics(address_id);
CREATE INDEX idx_green_calculated ON green_space_metrics(calculated_at DESC);
CREATE INDEX idx_green_score ON green_space_metrics(green_index_score);

-- ============================================================
# QeV SCORES
# ============================================================

CREATE TABLE IF NOT EXISTS qev_scores (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Raw indices
    raw_air_index DOUBLE PRECISION,
    raw_air_index_no2 DOUBLE PRECISION,
    raw_air_index_pm25 DOUBLE PRECISION,
    raw_air_index_pm10 DOUBLE PRECISION,
    raw_air_index_o3 DOUBLE PRECISION,
    raw_air_index_so2 DOUBLE PRECISION,
    
    raw_traffic_nuisance DOUBLE PRECISION,
    raw_traffic_light_count INTEGER,
    raw_traffic_utility_count INTEGER,
    raw_traffic_heavy_count INTEGER,
    
    raw_green_index DOUBLE PRECISION,
    raw_green_trees_visible INTEGER,
    raw_green_canopy_pct DOUBLE PRECISION,
    raw_green_distance_park_m DOUBLE PRECISION,
    
    -- Normalized scores (0-1)
    normalized_air_score DOUBLE PRECISION,
    normalized_traffic_score DOUBLE PRECISION,
    normalized_green_score DOUBLE PRECISION,
    
    -- Final QeV score
    qev_score DOUBLE PRECISION NOT NULL,
    qev_category VARCHAR(50) NOT NULL,
    
    -- Weights
    weight_air DOUBLE PRECISION DEFAULT 0.50,
    weight_traffic DOUBLE PRECISION DEFAULT 0.25,
    weight_green DOUBLE PRECISION DEFAULT 0.25,
    
    -- Normalization bounds
    normalization_bounds JSONB,
    
    -- Metadata
    data_completeness DOUBLE PRECISION,
    confidence_level DOUBLE PRECISION,
    calculation_method VARCHAR(50) DEFAULT 'belaqi_emep_330',
    data_sources_used JSONB,
    
    -- Validation
    is_validated BOOLEAN DEFAULT false,
    validated_by VARCHAR(100),
    validated_at TIMESTAMP WITH TIME ZONE,
    validation_notes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_qev_address ON qev_scores(address_id);
CREATE INDEX idx_qev_calculated ON qev_scores(calculated_at DESC);
CREATE INDEX idx_qev_score ON qev_scores(qev_score DESC);
CREATE INDEX idx_qev_category ON qev_scores(qev_category);

-- ============================================================
# POLLEN RECORDS
# ============================================================

CREATE TABLE IF NOT EXISTS pollen_records (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    graminaceae DOUBLE PRECISION,
    betula DOUBLE PRECISION,
    alnus DOUBLE PRECISION,
    corylus DOUBLE PRECISION,
    cupressaceae DOUBLE PRECISION,
    populus DOUBLE PRECISION,
    quercus DOUBLE PRECISION,
    fraxinus DOUBLE PRECISION,
    platanus DOUBLE PRECISION,
    urticaceae DOUBLE PRECISION,
    artemisia DOUBLE PRECISION,
    ambrosia DOUBLE PRECISION,
    plantago DOUBLE PRECISION,
    poaceae DOUBLE PRECISION,
    chenopod DOUBLE PRECISION,
    
    total_pollen DOUBLE PRECISION,
    data_source VARCHAR(100) DEFAULT 'irceline',
    quality_flag VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE (address_id, timestamp)
);

CREATE INDEX idx_pollen_timestamp ON pollen_records(timestamp DESC);
CREATE INDEX idx_pollen_address ON pollen_records(address_id);

-- ============================================================
# SATELLITE & STREET VIEW DATA
# ============================================================

CREATE TABLE IF NOT EXISTS satellite_downloads (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    radius_km DOUBLE PRECISION NOT NULL,
    zoom_levels INTEGER[],
    map_types VARCHAR(50)[],
    output_directory VARCHAR(500),
    total_images INTEGER,
    download_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS satellite_images (
    id SERIAL PRIMARY KEY,
    download_id INTEGER NOT NULL REFERENCES satellite_downloads(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    filepath VARCHAR(500) NOT NULL,
    zoom_level INTEGER,
    map_type VARCHAR(50),
    image_width INTEGER,
    image_height INTEGER,
    resolution_m_per_px DOUBLE PRECISION,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS streetview_downloads (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    radius_m INTEGER NOT NULL,
    total_photos INTEGER,
    quality_filter_used BOOLEAN,
    output_directory VARCHAR(500),
    download_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS streetview_images (
    id SERIAL PRIMARY KEY,
    download_id INTEGER NOT NULL REFERENCES streetview_downloads(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    filepath VARCHAR(500) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    heading INTEGER,
    quality_score INTEGER,
    is_outdoor BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
# IMAGE ANALYSES
# ============================================================

CREATE TABLE IF NOT EXISTS image_analyses (
    id SERIAL PRIMARY KEY,
    image_type VARCHAR(50) NOT NULL,
    image_id INTEGER NOT NULL,
    analysis_type VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50),
    results JSONB NOT NULL,
    statistics JSONB,
    processing_time DOUBLE PRECISION,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_image_analyses_type_id ON image_analyses(image_type, image_id);
CREATE INDEX idx_image_analyses_type ON image_analyses(analysis_type);
CREATE INDEX idx_image_analyses_created ON image_analyses(created_at DESC);

-- ============================================================
# META SCORES
# ============================================================

CREATE TABLE IF NOT EXISTS meta_scores (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    air_quality_score DOUBLE PRECISION,
    green_space_score DOUBLE PRECISION,
    urban_density_score DOUBLE PRECISION,
    noise_score DOUBLE PRECISION,
    weather_comfort_score DOUBLE PRECISION,
    
    overall_score DOUBLE PRECISION NOT NULL,
    score_category VARCHAR(50) NOT NULL,
    
    data_completeness DOUBLE PRECISION,
    confidence_level DOUBLE PRECISION,
    calculation_metadata JSONB,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_meta_address ON meta_scores(address_id);
CREATE INDEX idx_meta_calculated ON meta_scores(calculated_at DESC);
CREATE INDEX idx_meta_score ON meta_scores(overall_score);

-- ============================================================
# GREEN SPACES (OpenStreetMap data)
# ============================================================

CREATE TABLE IF NOT EXISTS green_spaces (
    id SERIAL PRIMARY KEY,
    osm_id VARCHAR(50) UNIQUE,
    name VARCHAR(200),
    green_space_type VARCHAR(50) NOT NULL,
    geom geometry(Polygon, 4326),
    area DOUBLE PRECISION,
    perimeter DOUBLE PRECISION,
    access_type VARCHAR(50),
    surface_type VARCHAR(50),
    has_playground BOOLEAN DEFAULT false,
    has_sports_facilities BOOLEAN DEFAULT false,
    has_benches BOOLEAN DEFAULT false,
    tree_density DOUBLE PRECISION,
    dominant_tree_species VARCHAR(100),
    biodiversity_index DOUBLE PRECISION,
    data_source VARCHAR(100) DEFAULT 'osm',
    last_verified TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_green_spaces_type ON green_spaces(green_space_type);
CREATE INDEX idx_green_spaces_access ON green_spaces(access_type);
CREATE INDEX idx_green_spaces_geom ON green_spaces USING GIST(geom);

-- ============================================================
# TRIGGERS FOR UPDATED_AT
# ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_addresses_updated_at
    BEFORE UPDATE ON addresses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_stations_updated_at
    BEFORE UPDATE ON stations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_air_quality_updated_at
    BEFORE UPDATE ON air_quality_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_weather_updated_at
    BEFORE UPDATE ON weather_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_traffic_updated_at
    BEFORE UPDATE ON traffic_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_green_space_metrics_updated_at
    BEFORE UPDATE ON green_space_metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_qev_scores_updated_at
    BEFORE UPDATE ON qev_scores
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_green_spaces_updated_at
    BEFORE UPDATE ON green_spaces
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
# CLEANUP: Delete expired sessions
# ============================================================

CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM sessions WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Schedule cleanup (if pg_cron extension available)
-- SELECT cron.schedule('cleanup-sessions', '0 * * * *', 'SELECT cleanup_expired_sessions()');

-- ============================================================
# COMMENTS
# ============================================================

COMMENT ON TABLE users IS 'User accounts for the Air Quality Platform';
COMMENT ON TABLE sessions IS 'Active JWT sessions';
COMMENT ON TABLE addresses IS 'Geocoded addresses with PostGIS geometry';
COMMENT ON TABLE stations IS 'Air quality and weather measurement stations';
COMMENT ON TABLE air_quality_records IS 'Air quality measurements (PM, NO2, O3, etc.)';
COMMENT ON TABLE weather_records IS 'Weather data from various sources';
COMMENT ON TABLE traffic_records IS 'Road traffic data for QeV calculation';
COMMENT ON TABLE green_space_metrics IS 'Green space metrics (3-30-300 rule)';
COMMENT ON TABLE qev_scores IS 'Quality of Environmental Life (QeV) scores';
