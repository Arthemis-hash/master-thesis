# Documentation Conformite RGPD
# Brussels Air Quality Platform

## Table des matieres
1. Introduction
2. Articles RGPD implémentés
3. Techniques d'anonymisation
4. Politique de rétention
5. Procédures opérationnelles
6. Architecture technique
7. Configuration


## 1. Introduction

Ce document décrit l'implémentation de la conformité RGPD (Règlement Général sur la Protection des Données) pour la Brussels Air Quality Platform.

### Objectifs
- Garantir les droits des utilisateurs sur leurs données personnelles
- Implémenter la protection des données dès la conception (Privacy by Design)
- Automatiser les tâches de conformité
- Maintenir la traçabilité complète des opérations


## 2. Articles RGPD Implemente

### Article 15 - Droit d'acces
- **Statut**: Implemente
- **Description**: L'utilisateur peut obtenir une copie de toutes ses donnees personnelles
- **Endpoint Streamlit**: Page "Mes Donnees RGPD" > Onglet Export
- **Script**: `gdpr.export_user_data(user_id)`

### Article 16 - Droit de rectification
- **Statut**: Implemente
- **Description**: L'utilisateur peut corriger ses donnees inexactes
- **Endpoint Streamlit**: Page "Mes Donnees RGPD" > Onglet Rectification
- **Script**: `gdpr.update_user_data(user_id, ...)`

### Article 17 - Droit a l'oubli
- **Statut**: Implemente
- **Description**: L'utilisateur peut demander la suppression de ses donnees
- **Options**:
  1. Anonymisation (recommande): Conserve l'historique mais anonymise l'identite
  2. Suppression complete: Efface toutes les donnees
- **Endpoint Streamlit**: Page "Mes Donnees RGPD" > Onglet Suppression

### Article 20 - Droit a la portabilite
- **Statut**: Inclus dans l'export (Article 15)
- **Description**: L'utilisateur peut obtenir ses donnees dans un format structure


## 3. Techniques d'Anonymisation

### 3.1 Anonymisation Irreversible (Droit a l'oubli)

#### Noms et Prenoms
```python
# Methode: Hash SHA-256
Input:  "Jean Dupont"
Output: {
  "firstName": "User_a3f5b9c1",
  "lastName": "Anonymous"
}
```

#### Emails
```python
# Methode: Format anonyme avec hash
Input:  "jean.dupont@example.com"
Output: "anonymous_a3f5b9c12345@deleted.local"
```

#### Telephones
```python
# Methode: Hash SHA-256
Input:  "+33612345678"
Output: "5f4dcc3b5aa765d61d8327deb882cf99"
```

### 3.2 Anonymisation de Geolocalisation

#### Reduction de Precision
```python
# Methode: Arrondir a N decimales
Input:  { lat: 48.8566, lon: 2.3522 }
Output: { lat: 48.86,   lon: 2.35 }
```

| Decimales | Precision |
|-----------|-----------|
| 0 | ~111 km |
| 1 | ~11 km |
| 2 | ~1 km (RECOMMANDE) |
| 3 | ~100 m |
| 4 | ~10 m |

### 3.3 Anonymisation Adresse IP

#### IPv4
```python
# Methode: Masquer le dernier octet
Input:  "192.168.1.100"
Output: "192.168.1.0"
```

#### IPv6
```python
# Methode: Garder les 4 premiers blocs
Input:  "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
Output: "2001:0db8:85a3:0000:0000:0000:0000:0000"
```


## 4. Politique de Retention

### Donnees utilisateur
| Type de donnees | Duree de conservation |
|-----------------|---------------------|
| Utilisateurs inactifs | 2 ans (730 jours) |
| Periode de grace suppression | 30 jours |
| Donnees anonymisees | Indeterminee (conservation historique) |

### Sessions
| Type | Duree |
|------|-------|
| JWT Token | 30 minutes |
| Refresh Token | 7 jours |
| Session inactive | 35 minutes |

### Logs
| Type | Duree |
|------|-------|
| Logs d'audit | 1 an (365 jours) |
| Incidents de securite | 7 ans (2555 jours) |

### Donnees sensibles
| Type | Duree |
|------|-------|
| Geolocalisation | 6 mois maximum |
| Adresse IP | 3 mois |
| Donnees financieres | JAMAIS (tokenisation) |


## 5. Procedures Operationnelles

### 5.1 Demande de suppression (Utilisateur)

1. L'utilisateur accede a la page "Mes Donnees RGPD"
2. Il selectionne "Suppression (Article 17)"
3. Il choisie:
   - **Anonymisation** (recommande): clicks sur "Anonymiser mon compte"
   - **Suppression complete**: tape "SUPPRIMER" et confirme
4. Le systeme:
   - Desactive immediatement le compte
   - Lance l'anonymisation ou la suppression
   - Logger l'action dans audit_logs

### 5.2 Anonymisation automatique (Cron)

1. Tous les jours a 2h du matin
2. Le script `scheduled_jobs.py anonymize` s'execute
3. Il identifie les utilisateurs inactifs depuis 730+ jours
4. Il anonymise chaque compte:
   - Hash du nom et prenom
   - Email anonymise
   - Conservation des donnees analytiques
   - Invalidation du mot de passe
5. Generation d'un rapport

### 5.3 Nettoyage des logs (Cron)

1. Tous les dimanches a 3h du matin
2. Le script `scheduled_jobs.py clean-logs` s'execute
3. Il supprime les logs de plus de 365 jours
4. Conservation des logs d'incidents de securite (7 ans)


## 6. Architecture Technique

### Fichiers crees

```
STREAMLIT/airquality/app/
├── gdpr_anonymizer.py           # Classe principale async
├── gdpr_anonymizer_sync.py      # Wrapper synchrone
├── gdpr_ui.py                   # Interface Streamlit
└── scripts/gdpr/
    ├── __init__.py
    ├── cli.py                   # Interface CLI
    └── scheduled_jobs.py        # Taches cron
```

### Schema Prisma - Modifications

```prisma
model User {
  // Champs existants...
  
  // Nouveaux champs RGPD
  anonymizedAt         DateTime?
  deletionRequestedAt  DateTime?
  isAnonymized         Boolean
  isMarkedForDeletion  Boolean
  originalEmail        String?
  originalFirstName    String?
  originalLastName     String?
  gdprConsentGiven     Boolean
  gdprConsentDate      DateTime?
}

model AuditLog {
  id        Int      @id
  userId    Int?
  action    String   // USER_LOGIN, DATA_EXPORT, ANONYMIZATION, etc.
  resource  String?
  ipAddress String?
  details   Json?
  timestamp DateTime
}
```

### Base de donnees - Tables

| Table | Description |
|-------|-------------|
| users | Table principale avec champs RGPD |
| sessions | Sessions utilisateur (JWT) |
| audit_logs | Traçabilite complete des operations |


## 7. Configuration

### Variables d'environnement

Aucune nouvelle variable necessaire - utilise DATABASE_URL existant.

### Configuration cron (Linux)

```bash
# /etc/cron.d/gdpr-tasks

# Anonymisation automatique (2h chaque jour)
0 2 * * * cd /path/to/project && python STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py anonymize >> /var/log/gdpr_cron.log 2>&1

# Nettoyage logs (3h chaque dimanche)
0 3 * * 0 cd /path/to/project && python STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py clean-logs >> /var/log/gdpr_cron.log 2>&1

# Traitement suppressions (4h chaque jour)
0 4 * * * cd /path/to/project && python STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py process-deletions >> /var/log/gdpr_cron.log 2>&1

# Statistiques (5h chaque jour)
0 5 * * * cd /path/to/project && python STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py stats >> /var/log/gdpr_cron.log 2>&1
```

### Docker

Pour les containeurs Docker, utiliser scheduler externe comme `gosu` ou `cron` dans le conteneur.


## 8. Utilisation

### Interface CLI

```bash
# Menu interactif
python STREAMLIT/airquality/app/scripts/gdpr/cli.py

# Taches specifiques
python STREAMLIT/airquality/app/scripts/gdpr/cli.py
# Puis selectionner une option:
# 1. Anonymiser un utilisateur
# 2. Supprimer completement un utilisateur
# 3. Exporter les donnees
# 4. Anonymisation en masse
# 5. Statistiques de conformite
```

### Taches Cron

```bash
# Mode dry-run (simulation)
python STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py anonymize --dry-run

# Anonymisation
python STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py anonymize

# Nettoyage logs
python STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py clean-logs

# Traitement suppressions
python STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py process-deletions

# Statistiques
python STREAMLIT/airquality/app/scripts/gdpr/scheduled_jobs.py stats
```


## 9. Prochaines etapes

1. **Tester l'export de donnees** avec un utilisateur reel
2. **Verifier l'anonymisation** sur un echantillon
3. **Documenter les procedures** pour l'equipe
4. **Former les administrateurs** sur les outils RGPD
5. **Configurer les taches cron** sur le serveur de production


## 10. Support

Pour toute question concernant la conformite RGPD:
- Email: dpo@airquality.brussels
- Autorite de plainte: APD (Autorite de Protection des Donnees) - www.autoriteprotectiondonnees.be
