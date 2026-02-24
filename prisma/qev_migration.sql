-- Migration: Add QeV tables
-- Created: 2026-01-04
-- Description: Creates tables for QeV (Environmental Quality of Life) indicator

-- Table 1: Traffic Records
CREATE TABLE IF NOT EXISTS traffic_records (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    
    light_vehicles INTEGER,
    utility_vehicles INTEGER,
    heavy_vehicles INTEGER,
    
    traffic_nuisance_score FLOAT,
    road_geometry geometry(LineString, 4326),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(address_id, timestamp)
);

-- Table 2: Green Space Metrics
CREATE TABLE IF NOT EXISTS green_space_metrics (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    
    trees_visible_count INTEGER,
    has_minimum_3_trees BOOLEAN,
    canopy_coverage_pct FLOAT,
    distance_to_nearest_park_m FLOAT,
    green_index_score FLOAT,
    
    analysis_buffer_geometry geometry(Polygon, 4326),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Table 3: QeV Scores
CREATE TABLE IF NOT EXISTS qev_scores (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    
    -- Raw indices
    raw_air_index FLOAT,
    raw_traffic_nuisance FLOAT,
    raw_green_index FLOAT,
    
    -- Normalized scores (0-1)
    normalized_air_score FLOAT,
    normalized_traffic_score FLOAT,
    normalized_green_score FLOAT,
    
    -- Final QeV score
    qev_score FLOAT NOT NULL,
    qev_category VARCHAR(50) NOT NULL,
    
    -- Weights used in calculation
    weight_air FLOAT DEFAULT 0.50,
    weight_traffic FLOAT DEFAULT 0.25,
    weight_green FLOAT DEFAULT 0.25,
    
    calculated_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Table 4: Green Spaces (OSM data)
CREATE TABLE IF NOT EXISTS green_spaces (
    id SERIAL PRIMARY KEY,
    green_space_type VARCHAR(100),
    geom geometry(Polygon, 4326),
    area FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indices for performance
CREATE INDEX IF NOT EXISTS idx_traffic_address_timestamp ON traffic_records(address_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_traffic_road_geom ON traffic_records USING GIST(road_geometry);

CREATE INDEX IF NOT EXISTS idx_green_metrics_address ON green_space_metrics(address_id);
CREATE INDEX IF NOT EXISTS idx_green_metrics_buffer_geom ON green_space_metrics USING GIST(analysis_buffer_geometry);

CREATE INDEX IF NOT EXISTS idx_qev_scores_address ON qev_scores(address_id);
CREATE INDEX IF NOT EXISTS idx_qev_scores_category ON qev_scores(qev_category);

CREATE INDEX IF NOT EXISTS idx_green_spaces_geom ON green_spaces USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_green_spaces_type ON green_spaces(green_space_type);

-- Add comments for documentation
COMMENT ON TABLE traffic_records IS 'Traffic data with EMEP/EEA weighted vehicle counts';
COMMENT ON TABLE green_space_metrics IS 'Green space analysis results using 3-30-300 rule';
COMMENT ON TABLE qev_scores IS 'QeV (Environmental Quality of Life) composite scores';
COMMENT ON TABLE green_spaces IS 'OSM green spaces data for proximity analysis';

COMMENT ON COLUMN qev_scores.qev_score IS 'Composite score 0-1: 50% air + 25% traffic + 25% green';
COMMENT ON COLUMN qev_scores.qev_category IS 'Categories: Excellent, Bon, Modéré, Médiocre, Très mauvais';
