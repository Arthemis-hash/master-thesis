#!/bin/bash
# ============================================================
# CONFIGURATION CRON JOBS - RGPD
# ============================================================
# Script d'installation des tâches cron pour la conformité RGPD
# 
# Usage: 
#   ./setup_cron.sh install   - Installe les tâches cron
#   ./setup_cron.sh remove   - Supprime les tâches cron
#   ./setup_cron.sh status   - Affiche le statut
# ============================================================

set -e

# Configuration
PROJECT_DIR="/Users/macbook/Desktop/Master-Thésis/AirQualityProject"
CRON_USER=$(whoami)
CRON_FILE="/tmp/gdpr_cron_$$"

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "=========================================="
echo "  Configuration Cron Jobs - RGPD"
echo "=========================================="
echo ""

# Vérifier que le fichier Python existe
if [ ! -f "$PROJECT_DIR/STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py" ]; then
    echo -e "${RED}❌ Erreur: Le fichier scheduled_jobs.py n'existe pas${NC}"
    exit 1
fi

# Créer le log si inexistant
mkdir -p /var/log
touch /var/log/gdpr_cron.log 2>/dev/null || true

# Générer le contenu du cron
generate_cron() {
    cat > "$CRON_FILE" << 'EOF'
# ============================================================
# Tâches Cron - RGPD Compliance
# Brussels Air Quality Platform
# ============================================================

# Anonymisation automatique des comptes inactifs (2h chaque jour)
0 2 * * * cd /Users/macbook/Desktop/Master-Thésis/AirQualityProject && python3 STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py anonymize >> /var/log/gdpr_cron.log 2>&1

# Nettoyage des logs d'audit anciens (3h chaque dimanche)
0 3 * * 0 cd /Users/macbook/Desktop/Master-Thésis/AirQualityProject && python3 STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py clean-logs >> /var/log/gdpr_cron.log 2>&1

# Traitement des suppressions en attente (4h chaque jour)
0 4 * * * cd /Users/macbook/Desktop/Master-Thésis/AirQualityProject && python3 STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py process-deletions >> /var/log/gdpr_cron.log 2>&1

# Statistiques quotidiennes (5h chaque jour)
0 5 * * * cd /Users/macbook/Desktop/Master-Thésis/AirQualityProject && python3 STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py stats >> /var/log/gdpr_cron.log 2>&1
EOF
}

install_cron() {
    echo "📦 Installation des tâches cron..."
    
    generate_cron
    
    # Copier le fichier cron
    sudo cp "$CRON_FILE" /etc/cron.d/gdpr_tasks
    
    # Définir les permissions
    sudo chmod 644 /etc/cron.d/gdpr_tasks
    
    # Redémarrer cron (optionnel)
    sudo service cron restart 2>/dev/null || sudo systemctl restart cron 2>/dev/null || true
    
    echo -e "${GREEN}✅ Tâches cron installées avec succès${NC}"
    echo ""
    echo "Tâches configurées:"
    echo "  - anonymize:    2h00 chaque jour"
    echo "  - clean-logs:   3h00 chaque dimanche"
    echo "  - process-deletions: 4h00 chaque jour"
    echo "  - stats:        5h00 chaque jour"
    echo ""
    echo "Logs: /var/log/gdpr_cron.log"
}

remove_cron() {
    echo "🗑️ Suppression des tâches cron..."
    
    if [ -f /etc/cron.d/gdpr_tasks ]; then
        sudo rm /etc/cron.d/gdpr_tasks
        echo -e "${GREEN}✅ Tâches cron supprimées${NC}"
    else
        echo -e "${YELLOW}⚠️ Aucune tâche cron trouvée${NC}"
    fi
}

show_status() {
    echo "📊 Statut des tâches cron RGPD:"
    echo ""
    
    if [ -f /etc/cron.d/gdpr_tasks ]; then
        echo -e "${GREEN}✅ Tâches cron installées${NC}"
        echo ""
        echo "Contenu de /etc/cron.d/gdpr_tasks:"
        echo "----------------------------------------"
        cat /etc/cron.d/gdpr_tasks
        echo "----------------------------------------"
    else
        echo -e "${YELLOW}⚠️ Tâches cron non installées${NC}"
    fi
    
    echo ""
    echo "Dernière exécution des tâches:"
    if [ -f /var/log/gdpr_cron.log ]; then
        tail -10 /var/log/gdpr_cron.log
    else
        echo "Aucun log trouvé"
    fi
}

show_help() {
    echo "Usage: $0 [commande]"
    echo ""
    echo "Commandes:"
    echo "  install   - Installe les tâches cron"
    echo "  remove   - Supprime les tâches cron"
    echo "  status   - Affiche le statut"
    echo "  help     - Affiche cette aide"
    echo ""
}

# Traitement des arguments
case "${1:-help}" in
    install)
        install_cron
        ;;
    remove)
        remove_cron
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}❌ Commande inconnue: $1${NC}"
        show_help
        exit 1
        ;;
esac

# Nettoyage
rm -f "$CRON_FILE"
