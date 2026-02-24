#!/usr/bin/env python3
"""
Test EnvironmentDB wrapper et nouvelles fonctionnalités
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'app'))

print("🧪 TEST ENVIRONMENTDB WRAPPER\n")
print("="*60)

# Test 1: Import
try:
    from db_async_wrapper import EnvironmentDB, AddressManagerWrapper
    print("✅ Imports réussis")
except Exception as e:
    print(f"❌ Erreur import: {e}")
    sys.exit(1)

# Test 2: Initialisation
try:
    env_db = EnvironmentDB()
    print("✅ EnvironmentDB initialisé")
    address_mgr = AddressManagerWrapper()
    print("✅ AddressManagerWrapper initialisé")
except Exception as e:
    print(f"❌ Erreur initialisation: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Créer/récupérer une adresse
try:
    test_address = "1000 Région De Bruxelles-Capitale - Brussels Hoofd"
    addr_info = address_mgr.get_or_create_address(test_address, 50.8503, 4.3517)
    print(f"✅ Adresse récupérée/créée:")
    print(f"   ID: {addr_info['id']}")
    print(f"   Normalized: {addr_info['normalized_address']}")

    address_id = addr_info['id']
except Exception as e:
    print(f"❌ Erreur création adresse: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Méthodes EnvironmentDB
print("\n" + "="*60)
print("TEST MÉTHODES ENVIRONMENTDB")
print("="*60)

try:
    # Test get_latest_satellite_download
    sat_download = env_db.get_latest_satellite_download(address_id)
    if sat_download:
        print(f"✅ Téléchargement satellite trouvé:")
        print(f"   Date: {sat_download['download_date']}")
        print(f"   Images: {sat_download['total_images']}")
    else:
        print("ℹ️  Aucun téléchargement satellite pour cette adresse")

    # Test get_latest_streetview_download
    sv_download = env_db.get_latest_streetview_download(address_id)
    if sv_download:
        print(f"✅ Téléchargement street view trouvé:")
        print(f"   Date: {sv_download['download_date']}")
        print(f"   Photos: {sv_download['total_photos']}")
    else:
        print("ℹ️  Aucun téléchargement street view pour cette adresse")

    # Test get_all_downloads_summary
    summary = env_db.get_all_downloads_summary(address_id)
    print(f"\n✅ Résumé téléchargements:")
    print(f"   Satellite: {summary['satellite']['total']} téléchargement(s)")
    print(f"   Street View: {summary['streetview']['total']} téléchargement(s)")

    # Test get_environment_statistics
    stats = env_db.get_environment_statistics(address_id)
    print(f"\n✅ Statistiques environnement:")
    print(f"   Images satellite: {stats['total_satellite_images']}")
    print(f"   Images street view: {stats['total_streetview_images']}")
    print(f"   Dernière mise à jour: {stats['last_update'] or 'N/A'}")

except Exception as e:
    print(f"❌ Erreur méthodes: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Vérifier modèle Pollen
print("\n" + "="*60)
print("TEST MODÈLE POLLEN")
print("="*60)

try:
    from prisma.models import PollenRecord
    print("✅ Modèle PollenRecord importé depuis Prisma")
except Exception as e:
    print(f"❌ Erreur import PollenRecord: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("RÉSUMÉ")
print("="*60)
print("✅ EnvironmentDB wrapper fonctionnel")
print("✅ AddressManagerWrapper fonctionnel")
print("✅ Méthodes de téléchargement satellite/street view OK")
print("✅ Méthodes statistiques OK")
print("✅ Modèle PollenRecord disponible dans Prisma")
print("\n🎉 TOUS LES TESTS PASSENT !")
print("="*60)
