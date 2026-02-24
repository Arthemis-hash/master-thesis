# 🗺️ Fonctionnalité de Visualisation des Stations de Mesure

## 📋 Vue d'ensemble

Cette fonctionnalité permet de visualiser toutes les stations de mesure (qualité de l'air et météo) sur une carte interactive avec leurs informations détaillées. Elle utilise PostGIS pour les calculs de distance et les requêtes spatiales.

## ✨ Fonctionnalités

### 1. **Carte Interactive**
- Visualisation de toutes les stations sur une carte Folium
- Marqueurs colorés par type de station:
  - 🔵 Bleu: Stations de qualité de l'air actives
  - 🟢 Vert: Stations météo actives
  - Couleurs claires: Stations sans données récentes
  - 🔴 Rouge: Station sélectionnée

### 2. **Filtrage Avancé**
- Filtrage par type de station (toutes / qualité de l'air / météo)
- Affichage des stations actives uniquement
- Recherche de stations à proximité d'une position (rayon configurable)

### 3. **Informations Détaillées**
Pour chaque station, affichage de:
- Nom et code de la station
- Type (qualité de l'air ou météo)
- Coordonnées GPS (latitude, longitude)
- Altitude
- Statut (active/inactive)
- Nombre de mesures enregistrées
- Date de la dernière mesure
- Distance depuis la position actuelle (si applicable)

### 4. **Export de Données**
- Export CSV de la liste des stations avec toutes leurs informations
- Recherche dans le tableau

## 🏗️ Architecture

### Fichiers Créés/Modifiés

#### 1. **db_utils_postgres.py** (lignes 731-1011)
Classe `StationManager` avec méthodes:

```python
# Récupérer toutes les stations
async def get_all_stations(station_type, active_only)

# Recherche spatiale avec PostGIS
async def get_stations_near_location(latitude, longitude, radius_km, station_type)

# Récupérer une station spécifique
async def get_station_by_code(station_code)

# Créer une nouvelle station
async def create_station(station_code, station_name, station_type, latitude, longitude, elevation, metadata)
```

**Utilise PostGIS** pour:
- Calcul de distance avec `ST_Distance(geom::geography, ...)`
- Recherche dans un rayon avec `ST_DWithin(geom, ...)`
- Stockage de géométrie Point avec `ST_SetSRID(ST_MakePoint(lon, lat), 4326)`

#### 2. **db_async_wrapper.py** (lignes 400-442)
Wrapper synchrone pour Streamlit:

```python
class StationManager:
    def get_all_stations(...)
    def get_stations_near_location(...)
    def get_station_by_code(...)
    def create_station(...)
```

#### 3. **stations_map_ui.py** (nouveau fichier)
Interface utilisateur complète avec:
- `display_stations_map_ui()`: Interface principale
- `create_stations_map()`: Création de la carte Folium
- `create_station_popup_html()`: Génération des popups détaillés
- `display_station_details()`: Affichage détaillé d'une station

#### 4. **app.py**
Modifications:
- Import de `display_stations_map_ui`
- Bouton "🗺️ Carte des Stations" dans la sidebar (ligne 346)
- Logique d'affichage de la carte (lignes 205-234)

#### 5. **add_example_stations.py** (nouveau fichier)
Script pour ajouter des stations d'exemple:
- 5 stations IRCELINE (qualité de l'air) à Bruxelles
- 2 stations IRM (météo) à Uccle et Zaventem

## 🚀 Utilisation

### Accès à la Carte

1. Dans l'application, cliquez sur le bouton **"🗺️ Carte des Stations"** dans la barre latérale
2. La carte s'affiche avec toutes les stations disponibles
3. Utilisez les filtres dans la sidebar pour affiner la recherche

### Filtrage

**Sidebar - Filtres de Visualisation:**
- Type de stations: Toutes / Qualité de l'air / Météo
- Stations actives uniquement (checkbox)
- Afficher stations à proximité (si une analyse est en cours)
  - Rayon de recherche configurable (1-50 km)

### Exploration de la Carte

- **Clic sur un marqueur**: Affiche popup avec informations détaillées
- **Survol d'un marqueur**: Affiche nom et code de la station
- **Contrôle des couches** (en haut à droite):
  - Toggle groupes de stations (air / météo)
  - Changement de fond de carte (OpenStreetMap, CartoDB, etc.)

### Export

1. Utilisez la zone de recherche pour filtrer les stations
2. Cliquez sur **"📥 Télécharger la liste (CSV)"**

## 🗄️ Schéma de Base de Données

### Table `stations`

```sql
CREATE TABLE stations (
  id SERIAL PRIMARY KEY,
  station_code VARCHAR UNIQUE NOT NULL,
  station_name VARCHAR NOT NULL,
  station_type VARCHAR NOT NULL,  -- 'air_quality' | 'weather'
  latitude FLOAT NOT NULL,
  longitude FLOAT NOT NULL,
  geom geometry(Point, 4326),     -- PostGIS geometry
  elevation FLOAT,
  metadata JSONB,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Index spatial PostGIS
CREATE INDEX idx_stations_geom ON stations USING GIST (geom);
```

### Relations

- `AirQualityRecord.stationId` → `Station.id` (optionnel)
- `WeatherRecord.stationId` → `Station.id` (optionnel)

## 📊 Ajout de Stations

### Via Script Python

```bash
cd /Users/macbook/Desktop/Master-Thésis/STREAMLIT/airquality/app
python3 add_example_stations.py
```

Ce script ajoute:
- **BELAB001**: Arts-Loi (trafic urbain)
- **BELAB002**: Berchem-Sainte-Agathe (fond urbain)
- **BELAB004**: Haren (fond urbain)
- **BELAB005**: Ixelles (fond urbain)
- **BELAB006**: Molenbeek (fond urbain)
- **IRM_UCCLE**: Station météo IRM Uccle
- **IRM_ZAVENTEM**: Station météo Aéroport Zaventem

### Via Code Python

```python
from db_async_wrapper import StationManager

station_mgr = StationManager()

# Créer une nouvelle station
station = station_mgr.create_station(
    station_code='MY_STATION_01',
    station_name='Ma Station de Test',
    station_type='air_quality',  # ou 'weather'
    latitude=50.8503,
    longitude=4.3517,
    elevation=50,  # optionnel
    metadata={  # optionnel
        'network': 'CUSTOM',
        'pollutants': ['PM10', 'NO2']
    }
)
```

### Via SQL Direct

```sql
INSERT INTO stations (
    station_code, station_name, station_type,
    latitude, longitude, elevation, metadata
) VALUES (
    'TEST_001',
    'Station de Test',
    'air_quality',
    50.8503,
    4.3517,
    50,
    '{"network": "TEST"}'::jsonb
);

-- Mettre à jour la géométrie PostGIS
UPDATE stations
SET geom = ST_SetSRID(ST_MakePoint(4.3517, 50.8503), 4326)
WHERE station_code = 'TEST_001';
```

## 🔍 Requêtes Utiles

### Recherche de Stations Proches

```python
# Dans un rayon de 5 km autour de la Grand-Place
stations = station_mgr.get_stations_near_location(
    latitude=50.8467,
    longitude=4.3525,
    radius_km=5.0,
    station_type='air_quality'  # optionnel
)

for station in stations:
    print(f"{station['station_name']}: {station['distance_km']} km")
```

### Récupérer Toutes les Stations

```python
# Toutes les stations actives
all_stations = station_mgr.get_all_stations(active_only=True)

# Seulement les stations météo
weather_stations = station_mgr.get_all_stations(
    station_type='weather',
    active_only=True
)
```

### Récupérer une Station Spécifique

```python
station = station_mgr.get_station_by_code('BELAB001')
print(f"Station: {station['station_name']}")
print(f"Mesures: {station['air_quality_records']}")
```

## 🎨 Personnalisation

### Couleurs des Marqueurs

Modifiez `get_station_icon_color()` dans `stations_map_ui.py`:

```python
def get_station_icon_color(station: Dict) -> str:
    if station['station_type'] == 'air_quality':
        return 'blue'  # Changez ici
    elif station['station_type'] == 'weather':
        return 'green'  # Changez ici
    return 'gray'
```

### Icônes

Modifiez `get_station_icon()` dans `stations_map_ui.py`:

```python
def get_station_icon(station: Dict) -> str:
    if station['station_type'] == 'air_quality':
        return 'wind'  # Font Awesome icon
    elif station['station_type'] == 'weather':
        return 'cloud'
    return 'info-sign'
```

### Contenu du Popup

Modifiez `create_station_popup_html()` dans `stations_map_ui.py` pour ajouter des informations personnalisées.

## 🐛 Dépannage

### La Carte ne S'Affiche Pas

1. Vérifiez que `streamlit-folium` est installé:
   ```bash
   pip install streamlit-folium
   ```

2. Vérifiez que PostGIS est activé:
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   ```

### Aucune Station N'Apparaît

1. Vérifiez que des stations existent:
   ```python
   stations = station_mgr.get_all_stations(active_only=False)
   print(f"Nombre de stations: {len(stations)}")
   ```

2. Exécutez le script d'exemple:
   ```bash
   python3 add_example_stations.py
   ```

### Erreurs PostGIS

1. Vérifiez que l'extension PostGIS est installée:
   ```sql
   SELECT PostGIS_version();
   ```

2. Si nécessaire, créez l'extension:
   ```sql
   CREATE EXTENSION postgis;
   ```

## 📚 Références

- **PostGIS Documentation**: https://postgis.net/docs/
- **Folium Documentation**: https://python-visualization.github.io/folium/
- **IRCELINE Open Data**: https://www.irceline.be/fr/documentation/open-data
- **IRM Stations**: https://www.meteo.be/fr/meteo/observations

## 🔄 Améliorations Futures

1. **Clustering**: Regrouper les marqueurs proches pour une meilleure lisibilité
2. **Graphiques**: Afficher des graphiques de tendances dans les popups
3. **Export KML/GeoJSON**: Permettre l'export au format géospatial
4. **Filtres Temporels**: Filtrer les stations par période d'activité
5. **API REST**: Exposer les données des stations via une API
6. **Import CSV**: Permettre l'import de stations via fichier CSV

---

**Auteur**: Claude Sonnet 4.5
**Date**: 2026-01-08
**Version**: 1.0.0
