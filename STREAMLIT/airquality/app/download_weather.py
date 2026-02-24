#!/usr/bin/env python3
"""
Téléchargeur météo utilisant Open-Meteo API (GRATUIT)
Supporte données actuelles ET historiques
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict

# Import du nouveau client Open-Meteo
from weather_api import OpenMeteoClient
from db_async_wrapper import WeatherDB

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeatherDownloader:
    """Gestionnaire de téléchargement et sauvegarde météo avec Open-Meteo"""
    
    def __init__(self, address: str = None, force_new: bool = False):
        """
        Initialise le téléchargeur
        
        Args:
            address: Adresse pour laquelle chercher/créer une base
            force_new: Force création d'une nouvelle base
        """
        self.api_client = OpenMeteoClient()
        self.db = WeatherDB(address=address, force_new=force_new)
        logger.info(f"✅ WeatherDownloader initialisé avec Open-Meteo (base: {self.db.db_path})")
    
    def download_and_save_current(self, address: str, lat: float, lon: float, 
                                  forecast_days: int = 7) -> bool:
        """
        Télécharge et sauvegarde météo ACTUELLE + prévisions
        
        Args:
            address: Adresse du lieu
            lat: Latitude
            lon: Longitude
            forecast_days: Nombre de jours de prévisions (max 16)
            
        Returns:
            True si succès, False sinon
        """
        logger.info(f"🌤️ Téléchargement ACTUEL pour {address}")
        
        success = True
        
        # 1. Météo actuelle
        current = self.api_client.get_current_weather(lat, lon)
        if current:
            if self.db.save_current_weather(address, lat, lon, current):
                logger.info("✅ Météo actuelle sauvegardée")
            else:
                logger.error("❌ Erreur sauvegarde météo actuelle")
                success = False
        else:
            logger.warning("⚠️ Météo actuelle indisponible")
        
        # 2. Prévisions horaires
        hourly = self.api_client.get_hourly_forecast(lat, lon, days=forecast_days)
        if hourly is not None and not hourly.empty:
            if self.db.save_hourly_weather(address, lat, lon, hourly):
                logger.info(f"✅ {len(hourly)} prévisions horaires sauvegardées")
            else:
                logger.error("❌ Erreur sauvegarde horaires")
                success = False
        else:
            logger.warning("⚠️ Prévisions horaires indisponibles")
        
        # 3. Prévisions journalières
        daily = self.api_client.get_daily_forecast(lat, lon, days=forecast_days)
        if daily is not None and not daily.empty:
            if self.db.save_daily_weather(address, lat, lon, daily):
                logger.info(f"✅ {len(daily)} prévisions journalières sauvegardées")
            else:
                logger.error("❌ Erreur sauvegarde journalières")
                success = False
        else:
            logger.warning("⚠️ Prévisions journalières indisponibles")
        
        if success:
            logger.info("✅ Toutes les données météo actuelles sauvegardées !")
        
        return success
    
    def download_and_save_historical(self, address: str, lat: float, lon: float, 
                                     start_date: datetime, end_date: datetime) -> bool:
        """
        Télécharge et sauvegarde données météo HISTORIQUES
        
        Args:
            address: Adresse du lieu
            lat: Latitude
            lon: Longitude
            start_date: Date de début
            end_date: Date de fin
            
        Returns:
            True si succès, False sinon
        """
        logger.info(f"📅 Téléchargement HISTORIQUE pour {address}")
        logger.info(f"   Période: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}")
        
        # Télécharger données historiques
        historical_df = self.api_client.get_historical_weather(lat, lon, start_date, end_date)
        
        if historical_df is None or historical_df.empty:
            logger.error("❌ Aucune donnée historique récupérée")
            return False
        
        # Sauvegarder dans la BDD
        if self.db.save_hourly_weather(address, lat, lon, historical_df):
            logger.info(f"✅ {len(historical_df)} données historiques sauvegardées")
            return True
        else:
            logger.error("❌ Erreur sauvegarde données historiques")
            return False
    
    def download_and_save(self, address: str, lat: float, lon: float, 
                         forecast_days: int = 7) -> bool:
        """
        Méthode legacy - Appelle download_and_save_current()
        """
        return self.download_and_save_current(address, lat, lon, forecast_days)
    
    def get_latest_weather(self, address: str) -> Optional[Dict]:
        """Récupère dernière météo depuis la BDD"""
        return self.db.get_latest_current_weather(address)
    
    def get_forecast(self, address: str, hours: int = 24):
        """Récupère prévisions depuis la BDD"""
        return self.db.get_hourly_forecast(address, hours)
    
    def get_statistics(self, address: str) -> Dict:
        """Récupère statistiques météo depuis la BDD"""
        return self.db.get_temperature_statistics(address)


def interactive_download():
    """Mode interactif pour téléchargement"""
    
    # Configuration localisation
    lat, lon = 50.8503, 4.3517
    address = "Bruxelles, Belgique"
    
    # Initialiser avec le système multi-adresses
    downloader = WeatherDownloader(address=address, force_new=False)
    
    print("\n" + "=" * 70)
    print("🌤️  TÉLÉCHARGEMENT DE DONNÉES MÉTÉOROLOGIQUES".center(70))
    print("=" * 70)
    print(f"📍 Localisation: {address}")
    print(f"   Coordonnées: {lat}, {lon}")
    print("\n💡 Utilise Open-Meteo API (GRATUIT, historique depuis 1940)")
    print()
    
    # Choix du type
    print("Quel type de données souhaitez-vous télécharger ?")
    print("  1. Données ACTUELLES + Prévisions (jusqu'à 16 jours)")
    print("  2. Données HISTORIQUES (depuis 1940)")
    print()
    
    choice = input("Votre choix (1 ou 2): ").strip()
    
    if choice == "1":
        # Données actuelles
        print("\n📥 Téléchargement données actuelles...")
        print("Combien de jours de prévisions ? (défaut: 7, max: 16)")
        days_input = input("Nombre de jours (Entrée pour 7): ").strip()
        
        days = 7
        if days_input:
            try:
                days = min(int(days_input), 16)
            except ValueError:
                logger.warning("⚠️ Valeur invalide, utilisation de 7 jours")
        
        success = downloader.download_and_save_current(address, lat, lon, forecast_days=days)
        
        if success:
            print("\n" + "=" * 70)
            print("✅ SUCCÈS - Données actuelles sauvegardées !".center(70))
            print("=" * 70)
            
            latest = downloader.get_latest_weather(address)
            if latest:
                print(f"🌡️  Température: {latest['temperature']}°C")
                print(f"💨 Vent: {latest['wind_speed']} km/h")
            
            forecast = downloader.get_forecast(address, hours=24)
            if not forecast.empty:
                print(f"📈 Prévisions: {len(forecast)} heures")
        else:
            print("\n❌ Échec du téléchargement")
    
    elif choice == "2":
        # Données historiques
        print("\n📅 Téléchargement HISTORIQUES (depuis 1940)")
        print("=" * 70)
        print("Entrez l'intervalle (format: AAAA-MM-JJ)")
        print()
        
        # Date début
        while True:
            start_input = input("Date DÉBUT (ex: 2024-01-01): ").strip()
            try:
                start_date = datetime.strptime(start_input, "%Y-%m-%d")
                if start_date.year < 1940:
                    print("⚠️ Année min: 1940")
                    continue
                break
            except ValueError:
                print("❌ Format invalide. Utilisez AAAA-MM-JJ")
        
        # Date fin
        while True:
            end_input = input("Date FIN (ex: 2024-12-31): ").strip()
            try:
                end_date = datetime.strptime(end_input, "%Y-%m-%d")
                
                if end_date < start_date:
                    print("❌ Date fin doit être après date début")
                    continue
                
                max_date = datetime.now() - timedelta(days=5)
                if end_date > max_date:
                    print(f"⚠️ Date max: {max_date.strftime('%Y-%m-%d')}")
                    end_date = max_date
                
                break
            except ValueError:
                print("❌ Format invalide. Utilisez AAAA-MM-JJ")
        
        days_diff = (end_date - start_date).days
        print(f"\n📊 Période: {days_diff} jours")
        print(f"   Du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}")
        
        confirm = input("\nConfirmer téléchargement ? (o/n): ").strip().lower()
        
        if confirm == 'o':
            print("\n📥 Téléchargement en cours...")
            success = downloader.download_and_save_historical(
                address, lat, lon, start_date, end_date
            )
            
            if success:
                print("\n" + "=" * 70)
                print("✅ SUCCÈS - Données historiques sauvegardées !".center(70))
                print("=" * 70)
                
                stats = downloader.get_statistics(address)
                if stats:
                    print(f"📊 Temp moyenne: {stats.get('avg_temp', 'N/A'):.1f}°C")
                    print(f"📊 Temp min: {stats.get('min_temp', 'N/A'):.1f}°C")
                    print(f"📊 Temp max: {stats.get('max_temp', 'N/A'):.1f}°C")
                    print(f"📊 Total enregistrements: {stats.get('total_records', 0)}")
            else:
                print("\n❌ Échec du téléchargement")
        else:
            print("❌ Téléchargement annulé")
    
    else:
        print("❌ Choix invalide")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    interactive_download()