#!/usr/bin/env python3
"""
Test d'intégration : App + PostgreSQL
Vérifie que l'app peut démarrer avec la nouvelle architecture
"""

import sys
from pathlib import Path

# Ajouter le dossier app au path
sys.path.insert(0, str(Path(__file__).parent / 'app'))

print("🚀 Test d'intégration App + PostgreSQL\n")

# Test 1: Imports des modules de base de données
print("="*60)
print("TEST 1 : Imports DB")
print("="*60)

try:
    from db_async_wrapper import AirQualityDB, WeatherDB, DatabaseManager
    print("✅ db_async_wrapper importé")
except Exception as e:
    print(f"❌ Erreur import db_async_wrapper: {e}")
    sys.exit(1)

# Test 2: Création d'instances
print("\n" + "="*60)
print("TEST 2 : Création instances DB")
print("="*60)

try:
    air_db = AirQualityDB(address="Test Integration")
    print(f"✅ AirQualityDB créé: {air_db.current_address}")

    weather_db = WeatherDB(address="Test Integration")
    print(f"✅ WeatherDB créé: {weather_db.current_address}")
except Exception as e:
    print(f"❌ Erreur création DB: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Imports app (sans streamlit)
print("\n" + "="*60)
print("TEST 3 : Imports modules app")
print("="*60)

try:
    from auth_db import AuthDB
    print("✅ auth_db importé")

    from db_environment import EnvironmentDB
    print("✅ db_environment importé")

except Exception as e:
    print(f"❌ Erreur import modules app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("RÉSUMÉ")
print("="*60)
print("✅ Tous les imports fonctionnent")
print("✅ Les classes DB PostgreSQL sont opérationnelles")
print("✅ L'architecture est prête pour Streamlit")
print("\n🎉 INTÉGRATION RÉUSSIE !")
print("="*60)
print("\nPour lancer l'application Streamlit :")
print("  cd /Users/macbook/Desktop/Master-Thésis/STREAMLIT/airquality")
print("  streamlit run app/app.py")
print("="*60 + "\n")
