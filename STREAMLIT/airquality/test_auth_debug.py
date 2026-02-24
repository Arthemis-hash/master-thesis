#!/usr/bin/env python3
"""
Test debug du système d'authentification
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'app'))

from auth_manager import AuthManager

print("🔍 Test debug authentification\n")

auth_mgr = AuthManager()

# Login
print("1. Login...")
success, user_data = auth_mgr.login("test@test.com", "test")

if success:
    print(f"✅ Login OK - Token: {user_data['token'][:30]}...")

    # Debug get_session
    print("\n2. Récupération session depuis DB...")
    session = auth_mgr.db.get_session(user_data['token'])

    if session:
        print("✅ Session trouvée en DB")
        print(f"   Structure: {session.keys()}")
        print(f"   user_id: {session.get('user_id')}")
        print(f"   expires_at: {session.get('expires_at')}")
        print(f"   user: {session.get('user')}")
    else:
        print("❌ Session NOT trouvée")

    # Verify JWT
    print("\n3. Vérification JWT...")
    payload = auth_mgr.verify_jwt(user_data['token'])
    if payload:
        print(f"✅ JWT valide: {payload}")
    else:
        print("❌ JWT invalide")

    # Verify session
    print("\n4. verify_session complet...")
    valid, session_data = auth_mgr.verify_session(user_data['token'])

    if valid:
        print(f"✅ verify_session OK: {session_data}")
    else:
        print("❌ verify_session échoué")
else:
    print("❌ Login échoué")
