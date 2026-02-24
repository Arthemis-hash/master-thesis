# Documentation de Sécurité - Air Quality Project

## Vue d'ensemble

Ce document décrit les mesures de sécurité implémentées pour protéger l'application Air Quality Project.

## Fichiers de sécurité créés

### 1. Configuration centralisée
- **`app/config/security_config.py`** - Validation des variables d'environnement au démarrage
- **`.env`** - Fichier de configuration avec secrets sécurisés
- **`.env.example`** - Template pour configuration

### 2. Services de sécurité
- **`app/services/auth_service.py`** - Service d'authentification avec access/refresh tokens
- **`app/services/rate_limiter.py`** - Rate limiting avec Redis
- **`app/services/security_logger.py`** - Logging de sécurité structuré (JSON)
- **`app/services/input_validator.py`** - Validation des entrées utilisateur
- **`app/services/csrf_protection.py`** - Protection CSRF

### 3. Utilitaires
- **`app/scripts/generate_secrets.py`** - Générateur de secrets sécurisés

## Mesures de sécurité implémentées

### 1. Gestion des tokens JWT

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| Access Token | 15 minutes | Durée de vie courte pour limiter l'exposition |
| Refresh Token | 7 jours | Permet le refresh automatique |
| Rotation | ✅ | Chaque refresh génère un nouveau refresh token |
| Stockage | Session Redis | Pas de localStorage |

### 2. Rate Limiting

| Endpoint | Limite | Fenêtre |
|----------|--------|---------|
| `/login` | 5 tentatives | 15 minutes |
| `/register` | 3 tentatives | 1 heure |
| IP globale | 100 requêtes | 15 minutes |

### 3. Hashing des mots de passe

- **Algorithme**: bcrypt
- **Cost factor**: 12 (recommandé production)
- **Validation**:-force minimale de 8 caractères

### 4. Validation des entrées

- **Email**: Format RFC 5322
- **Noms**: Caractères alphabétiques uniquement, longueur 2-50
- **Adresses**: Longueur 3-200 caractères
- **Coordonnées**: Latitude [-90, 90], Longitude [-180, 180]
- **Protection XSS**: Échappement HTML automatique
- **Protection SQL**: Détection d'injections

### 5. Logging de sécurité

Événements journalisés:
- `LOGIN_SUCCESS` / `LOGIN_FAILED`
- `LOGOUT`
- `PASSWORD_CHANGE` / `PASSWORD_RESET_REQUEST`
- `REGISTRATION`
- `RATE_LIMIT_EXCEEDED`
- `SUSPICIOUS_ACTIVITY`
- `TOKEN_REFRESH`
- `SESSION_EXPIRED`

Format: JSON avec timestamp, email, user_id, IP, etc.

### 6. Protection CSRF

- Tokens HMAC-SHA256 signés
- Validité: 1 heure
- Actions spécifiques (form, password_change, user_create)

## Configuration requise

### Variables d'environnement

```bash
# JWT
JWT_SECRET=qp7TmIzqmrPMjunIxMtdE_e-Fr72lfjvwr_uEApELYU  # À personnaliser
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Session
SESSION_TTL_SECONDS=3600

# Rate Limiting
RATE_LIMIT_LOGIN_ATTEMPTS=5
RATE_LIMIT_WINDOW_SECONDS=900

# Bcrypt
BCRYPT_ROUNDS=12
```

## Utilisation des services

### AuthService
```python
from services.auth_service import AuthService

auth = AuthService()

# Créer une session
session = auth.create_session(
    user_id=1,
    email="user@example.com",
    role="user",
    first_name="John",
    last_name="Doe"
)
# Retourne: {session_id, access_token, refresh_token, ...}

# Rafraîchir le token
new_token, expires = auth.refresh_access_token(refresh_token)
```

### RateLimiter
```python
from services.rate_limiter import get_rate_limiter

limiter = get_rate_limiter()
allowed, count, reset_in = limiter.check_login_rate_limit("user@example.com")
if not allowed:
    print(f"Réessayez dans {reset_in} secondes")
```

### InputValidator
```python
from services.input_validator import InputValidator, validate_user_registration

# Valider un email
valid, error = InputValidator.validate_email("user@example.com")

# Valider une inscription complète
valid, errors = validate_user_registration(
    email="user@example.com",
    password="SecurePass123!",
    first_name="John",
    last_name="Doe"
)
```

### SecurityLogger
```python
from services.security_logger import get_security_logger

logger = get_security_logger()
logger.login_success("user@example.com", 1, "user")
logger.login_failed("user@example.com", "invalid_password")
```

## Prochaines améliorations suggérées

1. **HTTPS obligatoire** - Forcer HTTPS en production
2. **MFA (Multi-Factor Authentication)** - Ajouter authentification à deux facteurs
3. **Audit logs** - Tableau de bord des événements de sécurité
4. **Alertes** - Notifications en temps réel pour activités suspectes
5. **Sanitization** - Nettoyage supplémentaire des entrées pour les BDD

## Commandes utiles

```bash
# Générer de nouveaux secrets
python app/scripts/generate_secrets.py

# Tester la configuration
python -c "from config.security_config import get_security_config; print(get_security_config().JWT_SECRET)"
```
