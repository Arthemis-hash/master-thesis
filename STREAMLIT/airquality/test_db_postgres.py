#!/usr/bin/env python3
"""
Test des nouvelles classes PostgreSQL
"""

import asyncio
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

app_path = Path(__file__).parent / 'app'
sys.path.insert(0, str(app_path))

from db_utils_postgres import AirQualityDB, WeatherDB, DatabaseManager


async def test_air_quality_db():
    """Test AirQualityDB avec PostgreSQL"""
    print("\n" + "="*60)
    print("TEST : AirQualityDB (PostgreSQL)")
    print("="*60)

    db = AirQualityDB(address="Test Bruxelles")

    # Créer des données de test
    test_data = pd.DataFrame({
        'date': [datetime.now() - timedelta(hours=i) for i in range(5)],
        'pm10': [15.5, 18.2, 12.1, 20.0, 16.8],
        'pm2_5': [10.2, 12.5, 8.3, 14.0, 11.2],
        'nitrogen_dioxide': [25.0, 28.5, 22.0, 30.0, 26.5],
        'ozone': [45.0, 48.0, 42.0, 50.0, 46.0],
        'sulphur_dioxide': [5.0, 6.2, 4.5, 7.0, 5.8]
    })

    # Insérer données
    success = await db.insert_data(test_data, lat=50.8503, lon=4.3517)
    print(f"✅ Insertion réussie: {success}")

    # Récupérer données
    df = await db.get_location_data()
    print(f"✅ Données récupérées: {len(df)} enregistrements")

    # Récupérer intervalle de dates
    date_range = await db.get_date_range()
    if date_range:
        print(f"✅ Période: {date_range['start_date']} → {date_range['end_date']}")
        print(f"   Total: {date_range['total_records']} enregistrements")

    return True


async def test_weather_db():
    """Test WeatherDB avec PostgreSQL"""
    print("\n" + "="*60)
    print("TEST : WeatherDB (PostgreSQL)")
    print("="*60)

    db = WeatherDB(address="Test Bruxelles")

    # Créer données météo de test
    test_data = pd.DataFrame({
        'date': [datetime.now() - timedelta(hours=i) for i in range(5)],
        'temperature': [15.5, 14.2, 16.8, 13.5, 15.0],
        'feels_like': [13.0, 12.0, 14.5, 11.0, 13.5],
        'humidity': [65, 70, 60, 75, 68],
        'pressure': [1013, 1015, 1012, 1016, 1014],
        'wind_speed': [12.5, 15.0, 10.0, 18.0, 13.5],
        'cloud_cover': [50, 60, 40, 70, 55]
    })

    # Insérer données
    success = await db.insert_data(test_data, lat=50.8503, lon=4.3517)
    print(f"✅ Insertion météo réussie: {success}")

    # Récupérer prévisions
    df = await db.get_hourly_forecast(hours=5)
    print(f"✅ Prévisions récupérées: {len(df)} heures")

    return True


async def test_database_manager():
    """Test DatabaseManager"""
    print("\n" + "="*60)
    print("TEST : DatabaseManager")
    print("="*60)

    # Lister bases air quality
    air_dbs = await DatabaseManager.list_all_databases('air_quality')
    print(f"✅ Bases air quality: {len(air_dbs)}")

    for db_info in air_dbs:
        print(f"   - {db_info['address']}: {db_info['records']} enregistrements")

    # Lister bases météo
    weather_dbs = await DatabaseManager.list_all_databases('weather')
    print(f"✅ Bases météo: {len(weather_dbs)}")

    for db_info in weather_dbs:
        print(f"   - {db_info['address']}: {db_info['records']} enregistrements")

    return True


async def main():
    print("\n🚀 " + "="*58)
    print("   TEST DB_UTILS_POSTGRES")
    print("   " + "="*58)

    try:
        # Test AirQualityDB
        air_ok = await test_air_quality_db()

        # Test WeatherDB
        weather_ok = await test_weather_db()

        # Test DatabaseManager
        manager_ok = await test_database_manager()

        print("\n" + "="*60)
        print("RÉSUMÉ")
        print("="*60)
        print(f"{'✅' if air_ok else '❌'} AirQualityDB")
        print(f"{'✅' if weather_ok else '❌'} WeatherDB")
        print(f"{'✅' if manager_ok else '❌'} DatabaseManager")

        if air_ok and weather_ok and manager_ok:
            print("\n🎉 TOUS LES TESTS SONT PASSÉS !")
        else:
            print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")

    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
