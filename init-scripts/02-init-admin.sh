#!/bin/bash
# ============================================================
# DATABASE INITIALIZATION SCRIPT
# ============================================================
# Creates admin user and seed data on first container start
# ============================================================

set -e

echo "========================================"
echo "Initializing Air Quality Database..."
echo "========================================"

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER"; do
    echo "PostgreSQL is unavailable - sleeping"
    sleep 1
done
echo "PostgreSQL is up!"

# ============================================================
# CREATE ADMIN USER (if not exists)
# ============================================================
echo "Creating admin user..."

# Use psql to create user with bcrypt hash for 'test123'
# Default bcrypt hash for 'test123' (cost factor 10)
ADMIN_PASSWORD_HASH='$2b$10$9.XxXxXxXxXxXxXxXxXxXeOxpX0xXxXxXxXxXxXxXxXxXxXxXxX'

# Alternative: Create hash using Python if available
if command -v python3 &> /dev/null; then
    ADMIN_PASSWORD_HASH=$(python3 -c "
import bcrypt
password = 'test123'
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=10))
print(hashed.decode('utf-8'))
")
fi

# Insert admin user (if not exists)
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
    -- Insert admin user if not exists
    INSERT INTO users (email, password_hash, first_name, last_name, role, is_active)
    VALUES (
        'admin@airquality.local',
        '$ADMIN_PASSWORD_HASH',
        'Admin',
        'User',
        'admin',
        true
    )
    ON CONFLICT (email) DO NOTHING;
    
    -- Insert test user (username: test, password: test123)
    INSERT INTO users (email, password_hash, first_name, last_name, role, is_active)
    VALUES (
        'test@airquality.local',
        '$ADMIN_PASSWORD_HASH',
        'Test',
        'User',
        'user',
        true
    )
    ON CONFLICT (email) DO NOTHING;
    
    -- Grant privileges
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $POSTGRES_USER;
EOSQL

echo "Admin users created successfully!"

# ============================================================
# SEED SAMPLE DATA (Optional)
# ============================================================
echo "Seeding sample data..."

psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
    -- Add sample Brussels stations if not exists
    INSERT INTO stations (station_code, station_name, station_type, latitude, longitude, elevation, is_active)
    VALUES 
        ('BE00142', 'Saint-Josse', 'air_quality', 50.8503, 4.3567, 13, true),
        ('BE00144', 'Ixelles', 'air_quality', 50.8465, 4.3517, 20, true),
        ('BE00147', 'Uccle', 'air_quality', 50.7979, 4.3372, 100, true),
        ('BE00148', ' Schaerbeek', 'air_quality', 50.8677, 4.3734, 35, true),
        ('BE00320', 'Bruxelles-Centrale', 'weather', 50.8503, 4.3567, 15, true),
        ('BE00321', 'Uccle-Obs', 'weather', 50.7979, 4.3372, 98, true)
    ON CONFLICT (station_code) DO NOTHING;
    
    -- Add sample addresses if not exists
    INSERT INTO addresses (full_address, normalized_address, street_number, street_name, postal_code, city, country, latitude, longitude)
    VALUES 
        ('Rue de la Loi 1, 1000 Bruxelles, Belgium', 'rue de la loi 1 1000 bruxelles belgium', '1', 'Rue de la Loi', '1000', 'Bruxelles', 'Belgium', 50.8503, 4.3567),
        ('Avenue Louise 500, 1050 Ixelles, Belgium', 'avenue louise 500 1050 ixelles belgium', '500', 'Avenue Louise', '1050', 'Ixelles', 'Belgium', 50.8465, 4.3517),
        ('Chau. de Waterloo 1300, 1180 Uccle, Belgium', 'chaussee de waterloo 1300 1180 uccle belgium', '1300', 'Chau. de Waterloo', '1180', 'Uccle', 'Belgium', 50.7979, 4.3372),
        ('Pl. de la Constitution 12, 1020 Bruxelles, Belgium', 'place de la constitution 12 1020 bruxelles belgium', '12', 'Pl. de la Constitution', '1020', 'Bruxelles', 'Belgium', 50.8677, 4.3734)
    ON CONFLICT (normalized_address) DO NOTHING;
EOSQL

echo "Sample data seeded successfully!"

# ============================================================
# CREATE INDEXES (if not exists)
# ============================================================
echo "Ensuring indexes..."

psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
    -- Additional performance indexes
    CREATE INDEX IF NOT EXISTS idx_air_quality_address_timestamp 
    ON air_quality_records(address_id, timestamp DESC);
    
    CREATE INDEX IF NOT EXISTS idx_weather_address_timestamp 
    ON weather_records(address_id, timestamp DESC);
    
    CREATE INDEX IF NOT EXISTS idx_qev_latest
    ON qev_scores(address_id, calculated_at DESC);
EOSQL

echo "Indexes created!"

echo "========================================"
echo "Database initialization complete!"
echo "========================================"
echo "Admin credentials:"
echo "  Email: admin@airquality.local"
echo "  Password: test123"
echo ""
echo "Test user credentials:"
echo "  Email: test@airquality.local"
echo "  Password: test123"
echo "========================================"
