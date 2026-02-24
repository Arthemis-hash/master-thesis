# Dossier des Bases de Données

Ce dossier contient toutes les bases de données SQLite générées par l'application.

## Structure des fichiers

Les bases de données suivent la nomenclature :
```
{type}_{adresse_normalisée}_{YYYYMMDD_HHMMSS}.db
```

### Types de bases :
- `air_quality_*.db` : Données de qualité de l'air
- `weather_*.db` : Données météorologiques

### Exemple :
```
air_quality_1000_bruxelles_20250123_143052.db
weather_1000_bruxelles_20250123_143052.db
```

## Gestion automatique

Les bases sont gérées automatiquement par le module `db_utils.py` via la classe `DatabaseManager`.

Les fonctionnalités incluent :
- ✅ Création automatique de bases avec timestamp
- ✅ Recherche intelligente de bases existantes
- ✅ Normalisation des adresses pour cohérence
- ✅ Support multi-adresses
- ✅ Évitement des doublons (UNIQUE constraint)

## Maintenance

Pour réinitialiser une base, utilisez l'interface Streamlit :
**Barre latérale → Options de maintenance → Réinitialiser la base par défaut**
