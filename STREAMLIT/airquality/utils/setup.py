#!/usr/bin/env python3
"""
Script de configuration et d'installation pour l'application de qualité de l'air
"""

import subprocess
import sys
import os

def install_requirements():
    """Installer les dépendances Python nécessaires"""
    print("📦 Installation des dépendances Python...")
    
    requirements = [
        "openmeteo-requests>=1.1.0",
        "requests-cache>=1.0.0", 
        "retry-requests>=2.0.0",
        "pandas>=2.0.0",
        "matplotlib>=3.5.0",
        "seaborn>=0.12.0",
        "folium>=0.14.0",
        "numpy>=1.20.0"
    ]
    
    for req in requirements:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", req])
            print(f"✅ {req.split('>=')[0]} installé")
        except subprocess.CalledProcessError:
            print(f"❌ Erreur lors de l'installation de {req}")
            return False
    
    return True

def check_database():
    """Vérifier si la base de données existe"""
    db_file = "bruxelles_air_quality.db"
    if os.path.exists(db_file):
        print(f"✅ Base de données trouvée : {db_file}")
        return True
    else:
        print(f"⚠️ Base de données non trouvée : {db_file}")
        print("   Exécutez d'abord download.py pour créer la base de données")
        return False

def main():
    """Fonction principale"""
    print("🚀 CONFIGURATION DE L'APPLICATION QUALITÉ DE L'AIR")
    print("=" * 60)
    
    # Installation des dépendances
    if install_requirements():
        print("\n✅ Toutes les dépendances sont installées")
    else:
        print("\n❌ Problème lors de l'installation des dépendances")
        return
    
    # Vérification de la base de données
    print(f"\n🔍 Vérification de la base de données...")
    if not check_database():
        print("\n📝 ÉTAPES SUIVANTES :")
        print("1. Exécutez 'python download.py' pour télécharger des données")
        print("2. Ensuite exécutez 'python air_quality_map.py' pour l'analyse")
        return
    
    print(f"\n✨ Configuration terminée !")
    print(f"🎯 Vous pouvez maintenant exécuter :")
    print(f"   • python download.py - Pour télécharger de nouvelles données")
    print(f"   • python air_quality_map.py - Pour l'analyse interactive avec carte")
    print(f"   • python db_utils.py - Pour les requêtes en ligne de commande")

if __name__ == "__main__":
    main()
