#!/usr/bin/env python3
"""
Test du système d'authentification complet
Vérifie auth_db → auth_db_wrapper → auth_manager → auth
"""

import sys
from pathlib import Path

# Ajouter le dossier app au path
sys.path.insert(0, str(Path(__file__).parent / 'app'))

print("🔐 Test système d'authentification PostgreSQL\n")

# Test 1: Import auth_db_wrapper
print("="*60)
print("TEST 1 : Import auth_db_wrapper")
print("="*60)

try:
    from auth_db_wrapper import AuthDB
    print("✅ auth_db_wrapper importé")

    auth_db = AuthDB()
    print("✅ AuthDB instance créée")
except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Import auth_manager
print("\n" + "="*60)
print("TEST 2 : Import auth_manager")
print("="*60)

try:
    from auth_manager import AuthManager
    print("✅ auth_manager importé")

    auth_mgr = AuthManager()
    print("✅ AuthManager instance créée")
except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Test login avec compte test
print("\n" + "="*60)
print("TEST 3 : Test login (test@test.com)")
print("="*60)

try:
    success, user_data = auth_mgr.login("test@test.com", "test")

    if success:
        print("✅ Login réussi")
        print(f"   User ID: {user_data['user_id']}")
        print(f"   Email: {user_data['email']}")
        print(f"   Role: {user_data['role']}")
        print(f"   Token: {user_data['token'][:50]}...")

        # Test 4: Vérifier session
        print("\n" + "="*60)
        print("TEST 4 : Vérification session")
        print("="*60)

        valid, session_data = auth_mgr.verify_session(user_data['token'])

        if valid:
            print("✅ Session valide")
            print(f"   Email: {session_data['email']}")
            print(f"   Role: {session_data['role']}")
        else:
            print("❌ Session invalide")
            sys.exit(1)

        # Test 5: Logout
        print("\n" + "="*60)
        print("TEST 5 : Logout")
        print("="*60)

        auth_mgr.logout(user_data['token'])
        print("✅ Logout réussi")

        # Vérifier que la session est supprimée
        valid, _ = auth_mgr.verify_session(user_data['token'])
        if not valid:
            print("✅ Session correctement supprimée")
        else:
            print("❌ Session encore active après logout")
            sys.exit(1)
    else:
        print("❌ Login échoué")
        sys.exit(1)

except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Test login avec mauvais credentials
print("\n" + "="*60)
print("TEST 6 : Test login avec mauvais mot de passe")
print("="*60)

try:
    success, user_data = auth_mgr.login("test@test.com", "wrong_password")

    if not success:
        print("✅ Login correctement refusé avec mauvais mot de passe")
    else:
        print("❌ Login accepté avec mauvais mot de passe")
        sys.exit(1)
except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("RÉSUMÉ")
print("="*60)
print("✅ auth_db_wrapper fonctionnel")
print("✅ auth_manager fonctionnel")
print("✅ Login/Logout fonctionnels")
print("✅ Vérification session fonctionnelle")
print("✅ Sécurité mot de passe fonctionnelle")
print("\n🎉 TOUS LES TESTS D'AUTHENTIFICATION RÉUSSIS !")
print("="*60)
