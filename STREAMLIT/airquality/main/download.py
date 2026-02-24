import openmeteo_requests
import sqlite3
import pandas as pd
import requests_cache
from retry_requests import retry
from datetime import datetime
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time

# ----------------------------
# 🧭 Fonctions de géocodage améliorées
# ----------------------------
def geocode_with_nominatim(address):
    """Utilise Nominatim (OpenStreetMap) pour un géocodage plus précis"""
    try:
        # Initialiser le géocodeur avec un user agent
        geolocator = Nominatim(user_agent="air_quality_brussels_app_v1.0")
        
        print(f"🔍 Recherche de l'adresse avec Nominatim...")
        location = geolocator.geocode(address, timeout=10)
        
        if location:
            print(f"✅ Adresse trouvée : {location.address}")
            print(f"📍 Coordonnées : {location.latitude:.6f}°N, {location.longitude:.6f}°E")
            return location.latitude, location.longitude, location.address
        else:
            return None, None, None
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"⚠️ Erreur Nominatim : {e}")
        return None, None, None

def geocode_with_openmeteo(address):
    """Utilise Open-Meteo comme solution de repli"""
    geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": address, "count": 5, "language": "fr"}
    
    try:
        resp = requests.get(geocode_url, params=params).json()
        
        if "results" in resp and len(resp["results"]) > 0:
            print("\n🔍 Résultats trouvés :")
            for i, loc in enumerate(resp["results"][:5], 1):
                country = loc.get('country', '')
                admin = loc.get('admin1', '')
                print(f"  {i}. {loc['name']}, {admin}, {country}")
                print(f"     → {loc['latitude']:.6f}°N, {loc['longitude']:.6f}°E")
            
            choice = input("\n👆 Choisissez un résultat (1-5) ou 0 pour annuler : ")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(resp["results"]):
                    loc = resp["results"][idx]
                    full_address = f"{loc['name']}, {loc.get('admin1', '')}, {loc.get('country', '')}"
                    return loc["latitude"], loc["longitude"], full_address
            except ValueError:
                pass
        
        return None, None, None
    except Exception as e:
        print(f"❌ Erreur lors du géocodage : {e}")
        return None, None, None

def manual_coordinates_input():
    """Permet à l'utilisateur d'entrer manuellement les coordonnées"""
    print("\n📝 Saisie manuelle des coordonnées")
    print("   Format accepté : décimal (ex: 50.812) ou DMS (ex: 50°48'42.9\")")
    
    try:
        lat_input = input("   Latitude : ").strip()
        lon_input = input("   Longitude : ").strip()
        
        # Convertir si nécessaire
        lat = parse_coordinate(lat_input)
        lon = parse_coordinate(lon_input)
        
        if lat and lon and -90 <= lat <= 90 and -180 <= lon <= 180:
            address = input("   Nom de l'adresse (optionnel) : ").strip() or f"Point ({lat:.4f}, {lon:.4f})"
            print(f"✅ Coordonnées acceptées : {lat:.6f}°N, {lon:.6f}°E")
            return lat, lon, address
        else:
            print("❌ Coordonnées invalides")
            return None, None, None
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return None, None, None

def parse_coordinate(coord_str):
    """Parse une coordonnée en format décimal ou DMS"""
    coord_str = coord_str.strip().replace(',', '.')
    
    # Si c'est déjà un nombre décimal
    try:
        return float(coord_str)
    except ValueError:
        pass
    
    # Essayer de parser le format DMS (degrés, minutes, secondes)
    import re
    dms_pattern = r'(\d+)[°\s]+(\d+)[\'′\s]+([0-9.]+)[\"″\s]*([NSEW]?)'
    match = re.match(dms_pattern, coord_str)
    
    if match:
        degrees = float(match.group(1))
        minutes = float(match.group(2))
        seconds = float(match.group(3))
        direction = match.group(4).upper()
        
        decimal = degrees + minutes/60 + seconds/3600
        
        if direction in ['S', 'W']:
            decimal = -decimal
        
        return decimal
    
    return None

def geocode_address_smart(address):
    """
    Géocodage intelligent avec plusieurs méthodes et validation
    """
    print(f"\n🎯 Géolocalisation de : {address}")
    print("=" * 60)
    
    # Méthode 1 : Nominatim (OpenStreetMap) - Plus précis
    print("\n1️⃣ Tentative avec Nominatim (OpenStreetMap)...")
    lat, lon, full_address = geocode_with_nominatim(address)
    
    if lat and lon:
        confirm = input(f"\n✅ Utiliser ces coordonnées ? (o/n) [o] : ").strip().lower()
        if confirm != 'n':
            return lat, lon, full_address
    
    # Méthode 2 : Open-Meteo avec sélection
    print("\n2️⃣ Tentative avec Open-Meteo...")
    lat, lon, full_address = geocode_with_openmeteo(address)
    
    if lat and lon:
        return lat, lon, full_address
    
    # Méthode 3 : Saisie manuelle
    print("\n3️⃣ Options alternatives :")
    print("   a) Entrer les coordonnées manuellement")
    print("   b) Chercher sur Google Maps et copier les coordonnées")
    print("   c) Annuler")
    
    choice = input("\nVotre choix (a/b/c) : ").strip().lower()
    
    if choice == 'a':
        return manual_coordinates_input()
    elif choice == 'b':
        print("\n💡 Instructions :")
        print("   1. Ouvrez Google Maps")
        print("   2. Cliquez sur votre emplacement")
        print("   3. Copiez les coordonnées affichées en haut")
        print("   4. Collez-les ici (format : 50.812, 4.382)")
        return manual_coordinates_input()
    
    return None, None, None

# ----------------------------
# ⚙️ Configuration Open-Meteo
# ----------------------------
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

# ----------------------------
# 🧑‍💻 Entrée utilisateur
# ----------------------------
print("🌍 TÉLÉCHARGEMENT DES DONNÉES DE QUALITÉ DE L'AIR")
print("=" * 60)
print("\n💡 Conseils pour une meilleure précision :")
print("   • Soyez précis : 'Avenue Franklin Roosevelt 50, Bruxelles'")
print("   • Incluez le quartier ou la commune")
print("   • Vous pourrez vérifier les coordonnées avant de continuer")
print()

address = input("📍 Entrez une adresse ou une ville : ").strip()

if not address:
    print("❌ Adresse vide. Arrêt du programme.")
    exit(1)

latitude, longitude, full_address = geocode_address_smart(address)

if latitude is not None and longitude is not None:
    # Afficher un résumé
    print("\n" + "=" * 60)
    print("📋 RÉSUMÉ DE LA LOCALISATION")
    print("=" * 60)
    print(f"📍 Adresse : {full_address}")
    print(f"🌐 Coordonnées : {latitude:.6f}°N, {longitude:.6f}°E")
    print(f"🔗 Vérifier sur Google Maps :")
    print(f"   https://www.google.com/maps?q={latitude},{longitude}")
    
    confirm_final = input("\n✅ Continuer avec ces coordonnées ? (o/n) [o] : ").strip().lower()
    if confirm_final == 'n':
        print("❌ Opération annulée par l'utilisateur")
        exit(0)
    
    # ----------------------------
    # 🌍 Paramètres API Air Quality
    # ----------------------------
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": [
            "pm10", "pm2_5", "carbon_monoxide", "carbon_dioxide", "nitrogen_dioxide", 
            "uv_index", "uv_index_clear_sky", "alder_pollen", "birch_pollen", "ozone", 
            "sulphur_dioxide", "methane", "ammonia", "dust", "aerosol_optical_depth", 
            "ragweed_pollen", "olive_pollen", "mugwort_pollen", "grass_pollen"
        ],
        "domains": "cams_europe",
        "timeformat": "unixtime",
        "start_date": "2025-10-01",
        "end_date": "2025-10-16",
    }

    # ----------------------------
    # 📡 Requête API
    # ----------------------------
    try:
        print("\n📡 Récupération des données de qualité de l'air...")
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]

        print(f"\n✅ Données récupérées avec succès")
        print(f"   Latitude: {response.Latitude()}°N")
        print(f"   Longitude: {response.Longitude()}°E")
        print(f"   Altitude: {response.Elevation()} m")
        print(f"   Décalage UTC: {response.UtcOffsetSeconds()}s")

        # Process hourly data
        hourly = response.Hourly()
        hourly_pm10 = hourly.Variables(0).ValuesAsNumpy()
        hourly_pm2_5 = hourly.Variables(1).ValuesAsNumpy()
        hourly_carbon_monoxide = hourly.Variables(2).ValuesAsNumpy()
        hourly_carbon_dioxide = hourly.Variables(3).ValuesAsNumpy()
        hourly_nitrogen_dioxide = hourly.Variables(4).ValuesAsNumpy()
        hourly_uv_index = hourly.Variables(5).ValuesAsNumpy()
        hourly_uv_index_clear_sky = hourly.Variables(6).ValuesAsNumpy()
        hourly_alder_pollen = hourly.Variables(7).ValuesAsNumpy()
        hourly_birch_pollen = hourly.Variables(8).ValuesAsNumpy()
        hourly_ozone = hourly.Variables(9).ValuesAsNumpy()
        hourly_sulphur_dioxide = hourly.Variables(10).ValuesAsNumpy()
        hourly_methane = hourly.Variables(11).ValuesAsNumpy()
        hourly_ammonia = hourly.Variables(12).ValuesAsNumpy()
        hourly_dust = hourly.Variables(13).ValuesAsNumpy()
        hourly_aerosol_optical_depth = hourly.Variables(14).ValuesAsNumpy()
        hourly_ragweed_pollen = hourly.Variables(15).ValuesAsNumpy()
        hourly_olive_pollen = hourly.Variables(16).ValuesAsNumpy()
        hourly_mugwort_pollen = hourly.Variables(17).ValuesAsNumpy()
        hourly_grass_pollen = hourly.Variables(18).ValuesAsNumpy()

        hourly_data = {"date": pd.date_range(
            start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
            end = pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
            freq = pd.Timedelta(seconds = hourly.Interval()),
            inclusive = "left"
        )}

        hourly_data["pm10"] = hourly_pm10
        hourly_data["pm2_5"] = hourly_pm2_5
        hourly_data["carbon_monoxide"] = hourly_carbon_monoxide
        hourly_data["carbon_dioxide"] = hourly_carbon_dioxide
        hourly_data["nitrogen_dioxide"] = hourly_nitrogen_dioxide
        hourly_data["uv_index"] = hourly_uv_index
        hourly_data["uv_index_clear_sky"] = hourly_uv_index_clear_sky
        hourly_data["alder_pollen"] = hourly_alder_pollen
        hourly_data["birch_pollen"] = hourly_birch_pollen
        hourly_data["ozone"] = hourly_ozone
        hourly_data["sulphur_dioxide"] = hourly_sulphur_dioxide
        hourly_data["methane"] = hourly_methane
        hourly_data["ammonia"] = hourly_ammonia
        hourly_data["dust"] = hourly_dust
        hourly_data["aerosol_optical_depth"] = hourly_aerosol_optical_depth
        hourly_data["ragweed_pollen"] = hourly_ragweed_pollen
        hourly_data["olive_pollen"] = hourly_olive_pollen
        hourly_data["mugwort_pollen"] = hourly_mugwort_pollen
        hourly_data["grass_pollen"] = hourly_grass_pollen

        hourly_dataframe = pd.DataFrame(data = hourly_data)

        # Ajouter les métadonnées de localisation
        hourly_dataframe['latitude'] = latitude
        hourly_dataframe['longitude'] = longitude
        hourly_dataframe['address'] = full_address
        
        # Filtrer pour garder seulement les données toutes les 4 heures
        hourly_dataframe = hourly_dataframe[hourly_dataframe['date'].dt.hour % 4 == 0].reset_index(drop=True)

        print("\n📊 Aperçu des données récupérées (toutes les 4h) :")
        print(hourly_dataframe.head())

        # Créer et configurer la base de données SQLite
        def create_database():
            """Crée la base de données SQLite et la table"""
            conn = sqlite3.connect('bruxelles_air_quality.db')
            cursor = conn.cursor()
            
            cursor.execute('DROP TABLE IF EXISTS air_quality')
            
            cursor.execute('''
                CREATE TABLE air_quality (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATETIME,
                    latitude REAL,
                    longitude REAL,
                    address TEXT,
                    pm10 REAL,
                    pm2_5 REAL,
                    carbon_monoxide REAL,
                    carbon_dioxide REAL,
                    nitrogen_dioxide REAL,
                    uv_index REAL,
                    uv_index_clear_sky REAL,
                    alder_pollen REAL,
                    birch_pollen REAL,
                    ozone REAL,
                    sulphur_dioxide REAL,
                    methane REAL,
                    ammonia REAL,
                    dust REAL,
                    aerosol_optical_depth REAL,
                    ragweed_pollen REAL,
                    olive_pollen REAL,
                    mugwort_pollen REAL,
                    grass_pollen REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            return conn

        def insert_data_to_db(dataframe, conn):
            """Insère les données dans la base de données"""
            try:
                dataframe.to_sql('air_quality', conn, if_exists='append', index=False, method='multi')
                print(f"\n✅ {len(dataframe)} enregistrements insérés avec succès")
                
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM air_quality")
                total_records = cursor.fetchone()[0]
                print(f"📊 Total d'enregistrements : {total_records}")
                
                cursor.execute("SELECT MIN(date), MAX(date) FROM air_quality")
                date_range = cursor.fetchone()
                print(f"📅 Période : du {date_range[0]} au {date_range[1]}")
                
            except Exception as e:
                print(f"❌ Erreur lors de l'insertion : {e}")

        def query_sample_data(conn):
            """Affiche des exemples de données"""
            try:
                sample_df = pd.read_sql_query("""
                    SELECT date, address, latitude, longitude, pm10, pm2_5, 
                           nitrogen_dioxide, ozone
                    FROM air_quality 
                    ORDER BY date DESC 
                    LIMIT 5
                """, conn)
                
                print("\n🔍 Échantillon des données stockées :")
                print(sample_df.to_string(index=False))
                
            except Exception as e:
                print(f"❌ Erreur lors de la lecture : {e}")

        # Créer la base de données
        print("\n🔧 Création de la base de données...")
        db_connection = create_database()

        # Insérer les données
        print("💾 Insertion des données...")
        insert_data_to_db(hourly_dataframe, db_connection)

        # Afficher un échantillon
        query_sample_data(db_connection)

        # Fermer la connexion
        db_connection.close()
        print("\n✅ Base de données fermée avec succès!")
        
        print("\n🎯 Prochaine étape :")
        print("   Exécutez 'python air_quality_map.py' pour générer la carte!")

    except Exception as e:
        print(f"❌ Erreur lors de la récupération des données : {e}")
        import traceback
        traceback.print_exc()
        
else:
    print("\n❌ Impossible de récupérer les données.")
    print("💡 Suggestions :")
    print("   - Réessayez avec une adresse plus précise")
    print("   - Utilisez la saisie manuelle des coordonnées")
    print("   - Vérifiez votre connexion internet")