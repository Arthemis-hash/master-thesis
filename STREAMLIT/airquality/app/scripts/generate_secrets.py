#!/usr/bin/env python3
"""
Script utilitaire pour générer les secrets sécurisés
et vérifier la configuration de sécurité
"""

import secrets
import string
import os
import sys


def generate_jwt_secret():
    """Génère un secret JWT sécurisé"""
    return secrets.token_urlsafe(32)


def generate_hex_secret(length=64):
    """Génère un secret hexadécimal sécurisé"""
    return secrets.token_hex(length)


def generate_password(length=16):
    """Génère un mot de passe aléatoire sécurisé"""
    characters = string.ascii_letters + string.digits + "!@#$%&*"
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%&*"),
    ]
    password += [secrets.choice(characters) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def check_env_file():
    """Vérifie le fichier .env et affiche les valeurs manquantes"""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")

    if not os.path.exists(env_path):
        print("❌ Fichier .env non trouvé!")
        return False

    required_vars = ["JWT_SECRET", "DATABASE_URL", "REDIS_HOST"]

    missing = []
    with open(env_path, "r") as f:
        content = f.read()
        for var in required_vars:
            if var not in content or f"{var}=" in content and f"{var}=" in content:
                if var not in content:
                    missing.append(var)
                else:
                    # Vérifier si la valeur est encore la valeur par défaut
                    for line in content.split("\n"):
                        if line.startswith(f"{var}="):
                            value = line.split("=", 1)[1].strip()
                            if (
                                "votre_" in value
                                or "changez" in value.lower()
                                or value == ""
                            ):
                                missing.append(f"{var} (à personnaliser)")

    if missing:
        print("⚠️ Variables à configurer:")
        for var in missing:
            print(f"  - {var}")
        return False

    print("✅ Configuration .env valide!")
    return True


def main():
    print("=" * 60)
    print("🔐 Générateur de Secrets Sécurisés")
    print("=" * 60)

    print("\n📋 JWT Secret:")
    print(f"   {generate_jwt_secret()}")

    print("\n📋 Signaling Secret:")
    print(f"   {generate_hex_secret(32)}")

    print("\n📋 Internal Secret:")
    print(f"   {generate_hex_secret(32)}")

    print("\n📋 Mot de passe aléatoire:")
    print(f"   {generate_password(16)}")

    print("\n" + "=" * 60)
    print("🔍 Vérification du fichier .env...")
    print("=" * 60)

    check_env_file()


if __name__ == "__main__":
    main()
