
import folium
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import numpy as np
from db_async_wrapper import AirQualityDB, StationManager
import webbrowser
import os
import logging

logger = logging.getLogger(__name__)

class AirQualityMapper:
    """Classe pour créer des cartes de qualité de l'air"""
    
    def __init__(self, address: str = None):
        """
        Initialise le mapper
        
        Args:
            address: Adresse pour laquelle charger les données
        """
        self.address = address
        self.db = AirQualityDB(address=address) if address else AirQualityDB()
        
    def create_pollution_color(self, pm25_value):
        """Déterminer la couleur basée sur la valeur PM2.5"""
        if pd.isna(pm25_value):
            return 'gray'
        elif pm25_value <= 10:
            return 'green'
        elif pm25_value <= 20:
            return 'yellow'
        elif pm25_value <= 25:
            return 'orange'
        else:
            return 'red'
    
    def get_air_quality_index(self, pm25):
        """Convertir PM2.5 en indice de qualité de l'air"""
        if pd.isna(pm25):
            return "Données non disponibles", "gray"
        elif pm25 <= 10:
            return "Bon", "green"
        elif pm25 <= 20:
            return "Modéré", "lightgreen"  # Remplace 'yellow' qui n'est pas valide pour folium.Icon
        elif pm25 <= 25:
            return "Mauvais pour groupes sensibles", "orange"
        else:
            return "Mauvais", "red"
    
    def create_location_map(self, address):
        """Créer une carte pour une adresse spécifique"""
        # Récupérer les données pour cette adresse
        location_data = self.db.get_location_data(address)

        if location_data.empty:
            logger.warning(f"❌ Aucune donnée trouvée pour l'adresse : {address}")
            print(f"❌ Aucune donnée trouvée pour l'adresse : {address}")
            return None

        # Obtenir le résumé de la localisation
        summary = self.db.get_location_summary(address)
        if not summary:
            logger.warning(f"❌ Impossible de générer le résumé pour : {address}")
            print(f"❌ Impossible de générer le résumé pour : {address}")
            return None

        # Coordonnées centrales
        center_lat = summary['latitude']
        center_lon = summary['longitude']

        # Log de débogage pour tracer le problème
        logger.info(f"🗺️ Carte pour '{address}': lat={center_lat:.6f}, lon={center_lon:.6f}")
        logger.info(f"   Adresse normalisée: '{summary['normalized_address']}'")
        logger.info(f"   Total enregistrements: {summary['total_records']}")
        
        # Créer la carte
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=12,
            tiles='OpenStreetMap'
        )
        
        # Dernière mesure disponible
        latest_data = location_data.iloc[0]
        latest_pm25 = latest_data['pm2_5']
        aqi_label, aqi_color = self.get_air_quality_index(latest_pm25)
        
        # Popup avec informations détaillées
        popup_html = f"""
        <div style="width: 300px;">
            <h4>📍 {summary['address']}</h4>
            <hr>
            <p><strong>🕐 Dernière mesure :</strong> {latest_data['date']}</p>
            <p><strong>🌡️ Qualité de l'air :</strong> <span style="color: {aqi_color}; font-weight: bold;">{aqi_label}</span></p>
            <hr>
            <p><strong>📊 Moyennes sur la période :</strong></p>
            <ul>
                <li>PM2.5: {summary['avg_pm2_5']:.1f} μg/m³</li>
                <li>PM10: {summary['avg_pm10']:.1f} μg/m³</li>
                <li>NO₂: {summary['avg_no2']:.1f} μg/m³</li>
                <li>O₃: {summary['avg_o3']:.1f} μg/m³</li>
                <li>SO₂: {summary['avg_so2']:.1f} μg/m³</li>
            </ul>
            <hr>
            <p><strong>⚠️ Alertes pollution :</strong> {summary['pollution_alert_pct']:.1f}% du temps</p>
            <p><strong>📅 Période :</strong> {summary['start_date']} à {summary['end_date']}</p>
            <p><strong>📊 Enregistrements :</strong> {summary['total_records']}</p>
        </div>
        """
        
        # Ajouter le marqueur principal
        folium.Marker(
            [center_lat, center_lon],
            popup=folium.Popup(popup_html, max_width=400),
            tooltip=f"{summary['address']} - {aqi_label}",
            icon=folium.Icon(
                color=aqi_color,
                icon='info-sign',
                prefix='glyphicon'
            )
        ).add_to(m)
        
        # Ajouter un cercle pour représenter la zone d'influence
        folium.Circle(
            location=[center_lat, center_lon],
            radius=150,  # 150m de rayon
            popup=f"Zone d'influence (150m) - {summary['address']}",
            color=aqi_color,
            fillColor=aqi_color,
            fillOpacity=0.2
        ).add_to(m)

        # Ajouter les stations de mesure proches (dans un rayon de 10km)
        try:
            station_mgr = StationManager()
            nearby_stations = station_mgr.get_stations_near_location(
                latitude=center_lat,
                longitude=center_lon,
                radius_km=10.0
            )

            if nearby_stations:
                logger.info(f"✅ {len(nearby_stations)} stations trouvées dans un rayon de 10km")

                # Créer un groupe de marqueurs pour les stations
                station_group = folium.FeatureGroup(name='🗺️ Stations de Mesure')

                for station in nearby_stations:
                    # Couleur différente selon le type de station
                    if station['station_type'] == 'air_quality':
                        station_color = 'blue'
                        station_icon = 'wind'
                        station_prefix = 'fa'
                    else:
                        station_color = 'lightblue'
                        station_icon = 'cloud'
                        station_prefix = 'fa'

                    # HTML popup pour la station
                    station_popup_html = f"""
                    <div style="width: 250px; font-family: Arial;">
                        <h4 style="margin: 0 0 10px 0; color: #2c3e50;">
                            {'🌬️' if station['station_type'] == 'air_quality' else '🌤️'} {station['station_name']}
                        </h4>
                        <table style="width: 100%; font-size: 12px;">
                            <tr>
                                <td style="font-weight: bold;">Code:</td>
                                <td style="font-family: monospace;">{station['station_code']}</td>
                            </tr>
                            <tr>
                                <td style="font-weight: bold;">Type:</td>
                                <td>{'Qualité de l\'air' if station['station_type'] == 'air_quality' else 'Météo'}</td>
                            </tr>
                            <tr>
                                <td style="font-weight: bold;">Distance:</td>
                                <td>{station['distance_km']:.2f} km</td>
                            </tr>
                            <tr>
                                <td style="font-weight: bold;">Position:</td>
                                <td>{station['latitude']:.4f}, {station['longitude']:.4f}</td>
                            </tr>
                    """

                    if station.get('elevation'):
                        station_popup_html += f"""
                            <tr>
                                <td style="font-weight: bold;">Altitude:</td>
                                <td>{station['elevation']}m</td>
                            </tr>
                        """

                    if station.get('air_quality_records', 0) > 0:
                        station_popup_html += f"""
                            <tr>
                                <td style="font-weight: bold;">Mesures air:</td>
                                <td>{station['air_quality_records']:,}</td>
                            </tr>
                        """

                    if station.get('weather_records', 0) > 0:
                        station_popup_html += f"""
                            <tr>
                                <td style="font-weight: bold;">Mesures météo:</td>
                                <td>{station['weather_records']:,}</td>
                            </tr>
                        """

                    station_popup_html += """
                        </table>
                    </div>
                    """

                    # Ajouter marqueur pour la station
                    folium.Marker(
                        location=[station['latitude'], station['longitude']],
                        popup=folium.Popup(station_popup_html, max_width=300),
                        tooltip=f"{station['station_name']} ({station['distance_km']:.1f} km)",
                        icon=folium.Icon(
                            color=station_color,
                            icon=station_icon,
                            prefix=station_prefix
                        )
                    ).add_to(station_group)

                # Ajouter le groupe à la carte
                station_group.add_to(m)

                # Ajouter contrôle des couches
                folium.LayerControl().add_to(m)

        except Exception as e:
            logger.warning(f"⚠️ Impossible d'ajouter les stations à la carte: {e}")

        return m, summary
    
    def create_data_visualization(self, address):
        """Créer des graphiques pour une adresse"""
        try:
            location_data = self.db.get_location_data(address)
            
            if location_data.empty:
                print(f"⚠️ Aucune donnée disponible pour {address}")
                return None
            
            # Vérifier les colonnes nécessaires
            required_cols = ['date', 'pm2_5', 'pm10', 'nitrogen_dioxide', 'ozone', 'sulphur_dioxide']
            missing_cols = [col for col in required_cols if col not in location_data.columns]
            if missing_cols:
                print(f"⚠️ Colonnes manquantes : {missing_cols}")
                return None
                
            # Convertir la date en datetime
            location_data['date'] = pd.to_datetime(location_data['date'])
            location_data = location_data.sort_values('date')
            
            # Créer la figure avec plusieurs sous-graphiques
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'Analyse de la qualité de l\'air - {address}', fontsize=16, fontweight='bold')
        except Exception as e:
            print(f"❌ Erreur lors de la création de la visualisation : {e}")
            return None
        
        # 1. Évolution temporelle des PM
        axes[0, 0].plot(location_data['date'], location_data['pm2_5'], 
                       label='PM2.5', color='red', linewidth=2)
        axes[0, 0].plot(location_data['date'], location_data['pm10'], 
                       label='PM10', color='orange', linewidth=2)
        axes[0, 0].axhline(y=20, color='red', linestyle='--', alpha=0.7, label='Seuil PM2.5 (20 μg/m³)')
        axes[0, 0].set_title('Évolution des particules fines (PM)')
        axes[0, 0].set_ylabel('Concentration (μg/m³)')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. Évolution des gaz
        axes[0, 1].plot(location_data['date'], location_data['nitrogen_dioxide'], 
                       label='NO₂', color='brown', linewidth=2)
        axes[0, 1].plot(location_data['date'], location_data['ozone'], 
                       label='O₃', color='blue', linewidth=2)
        axes[0, 1].plot(location_data['date'], location_data['sulphur_dioxide'], 
                       label='SO₂', color='purple', linewidth=2)
        axes[0, 1].set_title('Évolution des gaz polluants')
        axes[0, 1].set_ylabel('Concentration (μg/m³)')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Distribution des valeurs PM2.5
        axes[1, 0].hist(location_data['pm2_5'].dropna(), bins=20, 
                       color='skyblue', alpha=0.7, edgecolor='black')
        axes[1, 0].axvline(location_data['pm2_5'].mean(), color='red', 
                          linestyle='--', linewidth=2, label=f'Moyenne: {location_data["pm2_5"].mean():.1f}')
        axes[1, 0].axvline(20, color='orange', linestyle='--', linewidth=2, label='Seuil OMS: 20')
        axes[1, 0].set_title('Distribution PM2.5')
        axes[1, 0].set_xlabel('Concentration PM2.5 (μg/m³)')
        axes[1, 0].set_ylabel('Fréquence')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # 4. Corrélations entre polluants
        pollutants = ['pm2_5', 'pm10', 'nitrogen_dioxide', 'ozone', 'sulphur_dioxide']
        corr_data = location_data[pollutants].corr()
        
        im = axes[1, 1].imshow(corr_data, cmap='coolwarm', vmin=-1, vmax=1)
        axes[1, 1].set_xticks(range(len(pollutants)))
        axes[1, 1].set_yticks(range(len(pollutants)))
        axes[1, 1].set_xticklabels(['PM2.5', 'PM10', 'NO₂', 'O₃', 'SO₂'], rotation=45)
        axes[1, 1].set_yticklabels(['PM2.5', 'PM10', 'NO₂', 'O₃', 'SO₂'])
        axes[1, 1].set_title('Corrélations entre polluants')
        
        # Ajouter les valeurs de corrélation
        for i in range(len(pollutants)):
            for j in range(len(pollutants)):
                text = axes[1, 1].text(j, i, f'{corr_data.iloc[i, j]:.2f}',
                                     ha="center", va="center", color="black", fontweight='bold')
        
        plt.colorbar(im, ax=axes[1, 1], shrink=0.6)
        
        try:
            plt.tight_layout()
        except Exception as e:
            print(f"⚠️ Warning tight_layout : {e}")
        
        return fig
    
    def generate_report(self, address):
        """Générer un rapport complet pour une adresse"""
        print(f"\n🏠 RAPPORT DE QUALITÉ DE L'AIR - {address.upper()}")
        print("=" * 80)
        
        # Obtenir le résumé
        summary = self.db.get_location_summary(address)
        if not summary:
            print("❌ Aucune donnée trouvée pour cette adresse")
            return
        
        # Affichage du rapport
        print(f"📍 Adresse : {summary['address']}")
        print(f"🌍 Coordonnées : {summary['latitude']:.4f}°N, {summary['longitude']:.4f}°E")
        print(f"📊 Nombre de mesures : {summary['total_records']}")
        print(f"📅 Période couverte : {summary['start_date']} à {summary['end_date']}")
        
        print(f"\n🌡️ INDICATEURS MOYENS DE QUALITÉ DE L'AIR:")
        print("-" * 50)
        
        # Classification de la qualité de l'air basée sur PM2.5
        aqi_label, aqi_color = self.get_air_quality_index(summary['avg_pm2_5'])
        print(f"🎯 Indice de qualité : {aqi_label}")
        
        print(f"🔸 PM2.5 (particules fines) : {summary['avg_pm2_5']:.1f} μg/m³")
        print(f"🔸 PM10 (particules) : {summary['avg_pm10']:.1f} μg/m³") 
        print(f"🔸 NO₂ (dioxyde d'azote) : {summary['avg_no2']:.1f} μg/m³")
        print(f"🔸 O₃ (ozone) : {summary['avg_o3']:.1f} μg/m³")
        print(f"🔸 SO₂ (dioxyde de soufre) : {summary['avg_so2']:.1f} μg/m³")
        print(f"🔸 CO (monoxyde de carbone) : {summary['avg_co']:.1f} μg/m³")
        
        print(f"\n⚠️ ALERTES ET PICS DE POLLUTION:")
        print("-" * 40)
        print(f"📈 Pic PM2.5 maximum : {summary['max_pm2_5']:.1f} μg/m³")
        print(f"📈 Pic PM10 maximum : {summary['max_pm10']:.1f} μg/m³")
        print(f"🚨 Temps en alerte pollution : {summary['pollution_alert_pct']:.1f}%")
        
        # Recommandations
        print(f"\n💡 RECOMMANDATIONS:")
        print("-" * 25)
        if summary['avg_pm2_5'] <= 10:
            print("✅ Qualité de l'air excellente - Aucune précaution particulière")
        elif summary['avg_pm2_5'] <= 20:
            print("⚠️ Qualité de l'air modérée - Évitez les activités intenses à l'extérieur")
        else:
            print("🚨 Qualité de l'air mauvaise - Limitez les sorties, portez un masque si nécessaire")
        
        return summary

def main():
    """Fonction principale"""
    print("🌍 APPLICATION DE QUALITÉ DE L'AIR GÉOLOCALISÉE")
    print("=" * 60)
    print("Cette application vous permet de visualiser la qualité de l'air")
    print("dans votre zone avec une carte interactive et des graphiques détaillés.")
    print()
    
    mapper = AirQualityMapper()
    
    # Afficher les locations disponibles
    print("📋 Adresses disponibles dans la base de données :")
    locations = mapper.db.get_unique_locations()
    if not locations.empty:
        for idx, loc in locations.iterrows():
            print(f"  {idx + 1}. {loc['address']} ({loc['records_count']} enregistrements)")
    print()
    
    # Saisie utilisateur
    user_address = input("🏠 Entrez votre adresse ou ville : ").strip()
    if not user_address:
        print("❌ Adresse vide. Arrêt du programme.")
        return
    
    # Générer le rapport
    summary = mapper.generate_report(user_address)
    if not summary:
        return
    
    print(f"\n🗺️ Génération de la carte interactive...")
    
    # Créer la carte
    map_obj, map_summary = mapper.create_location_map(user_address)
    if map_obj:
        map_file = f"map_{user_address.replace(' ', '_').replace(',', '')}_air_quality.html"
        map_obj.save(map_file)
        print(f"✅ Carte sauvegardée : {map_file}")
        
        # Ouvrir la carte dans le navigateur
        try:
            webbrowser.open(f'file://{os.path.abspath(map_file)}')
            print("🌐 Carte ouverte dans votre navigateur web")
        except:
            print(f"⚠️ Veuillez ouvrir manuellement le fichier : {map_file}")
    
    # Créer les graphiques
    print(f"\n📊 Génération des graphiques d'analyse...")
    fig = mapper.create_data_visualization(user_address)
    if fig:
        graph_file = f"analysis_{user_address.replace(' ', '_').replace(',', '')}_air_quality.png"
        fig.savefig(graph_file, dpi=300, bbox_inches='tight')
        print(f"✅ Graphiques sauvegardés : {graph_file}")
        plt.show()  # Afficher les graphiques
    
    print(f"\n✨ Analyse complète terminée pour : {user_address}")
    print("📁 Fichiers générés dans le répertoire courant")

if __name__ == "__main__":
    main()
