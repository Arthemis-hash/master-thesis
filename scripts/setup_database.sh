#!/bin/bash
# ============================================================
# SCRIPT DE CONFIGURATION BASE DE DONNÉES
# Brussels Air Quality Platform
# ============================================================

set -e

echo "🚀 Configuration de la base de données PostgreSQL + PostGIS"
echo ""

# ============================================================
# 1. Vérifier que Docker est installé
# ============================================================
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé. Installez Docker Desktop d'abord."
    exit 1
fi

echo "✅ Docker détecté"

# ============================================================
# 2. Créer fichier .env si inexistant
# ============================================================
if [ ! -f .env ]; then
    echo "📝 Création du fichier .env..."
    cp .env.example .env
    echo "⚠️  IMPORTANT: Éditez le fichier .env pour configurer vos credentials"
else
    echo "✅ Fichier .env existant"
fi

# ============================================================
# 3. Démarrer PostgreSQL avec Docker Compose
# ============================================================
echo ""
echo "🐘 Démarrage de PostgreSQL avec PostGIS..."
docker-compose up -d postgres

# Attendre que PostgreSQL soit prêt
echo "⏳ Attente du démarrage de PostgreSQL..."
sleep 10

# Vérifier que le conteneur est en cours d'exécution
if docker ps | grep -q airquality_postgres; then
    echo "✅ PostgreSQL démarré avec succès"
else
    echo "❌ Erreur lors du démarrage de PostgreSQL"
    docker-compose logs postgres
    exit 1
fi

# ============================================================
# 4. Créer les triggers PostGIS
# ============================================================
echo ""
echo "🗺️  Configuration des triggers PostGIS..."

# Attendre encore un peu pour être sûr que PostGIS est initialisé
sleep 5

# Exécuter le script de triggers
docker-compose exec -T postgres psql -U airquality_user -d airquality_db <<-EOSQL
-- Triggers pour auto-génération des geometries
DROP TRIGGER IF EXISTS trigger_update_address_geom ON addresses;
CREATE TRIGGER trigger_update_address_geom
    BEFORE INSERT OR UPDATE ON addresses
    FOR EACH ROW
    EXECUTE FUNCTION update_address_geom();

DROP TRIGGER IF EXISTS trigger_update_station_geom ON stations;
CREATE TRIGGER trigger_update_station_geom
    BEFORE INSERT OR UPDATE ON stations
    FOR EACH ROW
    EXECUTE FUNCTION update_station_geom();

-- Créer index spatiaux
CREATE INDEX IF NOT EXISTS idx_addresses_geom ON addresses USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_stations_geom ON stations USING GIST(geom);

SELECT 'Triggers PostGIS configurés avec succès' as status;
EOSQL

if [ $? -eq 0 ]; then
    echo "✅ Triggers PostGIS configurés"
else
    echo "⚠️  Attention: Les triggers seront créés après la migration Prisma"
fi

# ============================================================
# 5. Installer Prisma Python
# ============================================================
echo ""
echo "📦 Installation de Prisma Python..."

# Vérifier si Python 3 est installé
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé"
    exit 1
fi

# Installer prisma-client-py
pip3 install prisma prisma-client-py

echo "✅ Prisma Python installé"

# ============================================================
# 6. Générer le client Prisma
# ============================================================
echo ""
echo "🔧 Génération du client Prisma..."

cd "$(dirname "$0")/.."
prisma generate

echo "✅ Client Prisma généré"

# ============================================================
# 7. Appliquer les migrations
# ============================================================
echo ""
echo "📊 Application des migrations Prisma..."

# Créer migration initiale
prisma migrate dev --name init --skip-generate

echo "✅ Migrations appliquées"

# ============================================================
# 8. Recréer les triggers (car migration les a écrasés)
# ============================================================
echo ""
echo "🔄 Recréation des triggers PostGIS..."

docker-compose exec -T postgres psql -U airquality_user -d airquality_db <<-EOSQL
-- Re-créer triggers
DROP TRIGGER IF EXISTS trigger_update_address_geom ON addresses;
CREATE TRIGGER trigger_update_address_geom
    BEFORE INSERT OR UPDATE ON addresses
    FOR EACH ROW
    EXECUTE FUNCTION update_address_geom();

DROP TRIGGER IF EXISTS trigger_update_station_geom ON stations;
CREATE TRIGGER trigger_update_station_geom
    BEFORE INSERT OR UPDATE ON stations
    FOR EACH ROW
    EXECUTE FUNCTION update_station_geom();

-- Re-créer index spatiaux
CREATE INDEX IF NOT EXISTS idx_addresses_geom ON addresses USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_stations_geom ON stations USING GIST(geom);

SELECT 'Triggers finaux configurés' as status;
EOSQL

echo "✅ Triggers finaux configurés"

# ============================================================
# 9. Démarrer PgAdmin (optionnel)
# ============================================================
echo ""
read -p "Voulez-vous démarrer PgAdmin ? (o/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Oo]$ ]]; then
    echo "🖥️  Démarrage de PgAdmin..."
    docker-compose up -d pgadmin
    echo "✅ PgAdmin disponible sur http://localhost:5050"
    echo "   Email: admin@airquality.com"
    echo "   Password: admin"
fi

# ============================================================
# RÉCAPITULATIF
# ============================================================
echo ""
echo "=========================================="
echo "✅ CONFIGURATION TERMINÉE"
echo "=========================================="
echo ""
echo "📊 PostgreSQL: localhost:5432"
echo "   Database: airquality_db"
echo "   User: airquality_user"
echo ""
echo "🗺️  PostGIS configuré avec succès"
echo "🔧 Client Prisma généré"
echo ""
echo "Prochaines étapes:"
echo "1. Vérifier les variables dans .env"
echo "2. Tester la connexion avec: prisma studio"
echo "3. Migrer les données SQLite si nécessaire"
echo ""
echo "Commandes utiles:"
echo "  docker-compose logs -f postgres  # Voir logs PostgreSQL"
echo "  docker-compose down              # Arrêter services"
echo "  prisma studio                    # Interface admin DB"
echo ""
