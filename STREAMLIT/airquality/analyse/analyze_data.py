#!/usr/bin/env python3
"""
Script d'analyse des données de qualité de l'air de Bruxelles
Analyse les données stockées dans la base SQLite
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np

def connect_to_db():
    """Se connecter à la base de données SQLite"""
    return sqlite3.connect('bruxelles_air_quality.db')

def load_data():
    """Charger toutes les données depuis la base"""
    conn = connect_to_db()
    
    query = """
    SELECT date, pm10, pm2_5, carbon_monoxide, carbon_dioxide, 
           nitrogen_dioxide, uv_index, uv_index_clear_sky, 
           alder_pollen, birch_pollen, ozone, sulphur_dioxide, 
           methane, ammonia, dust, aerosol_optical_depth,
           ragweed_pollen, olive_pollen, mugwort_pollen, grass_pollen
    FROM air_quality 
    WHERE pm10 IS NOT NULL AND pm2_5 IS NOT NULL
    ORDER BY date
    """
    
    df = pd.read_sql_query(query, conn)
    df['date'] = pd.to_datetime(df['date'])
    conn.close()
    
    return df

def basic_statistics(df):
    """Afficher les statistiques de base"""
    print("📊 STATISTIQUES DE BASE")
    print("=" * 50)
    print(f"Période analysée : du {df['date'].min()} au {df['date'].max()}")
    print(f"Nombre total d'enregistrements : {len(df)}")
    print()
    
    # Statistiques descriptives pour les polluants principaux
    pollutants = ['pm10', 'pm2_5', 'carbon_monoxide', 'nitrogen_dioxide', 'ozone', 'sulphur_dioxide']
    stats = df[pollutants].describe()
    print("Statistiques des polluants principaux :")
    print(stats.round(2))
    print()
    
    # Statistiques pour les pollens
    pollen_types = ['alder_pollen', 'birch_pollen', 'ragweed_pollen', 'olive_pollen', 'mugwort_pollen', 'grass_pollen']
    pollen_stats = df[pollen_types].describe()
    print("Statistiques des pollens :")
    print(pollen_stats.round(2))
    print()

def air_quality_analysis(df):
    """Analyse de la qualité de l'air selon les seuils OMS"""
    print("🌍 ANALYSE QUALITÉ DE L'AIR (seuils OMS)")
    print("=" * 50)
    
    # Seuils OMS pour PM2.5 et PM10 (μg/m³)
    pm25_threshold = 15  # Seuil annuel OMS
    pm10_threshold = 45  # Seuil annuel OMS
    
    # Pourcentage de dépassement des seuils
    pm25_exceed = (df['pm2_5'] > pm25_threshold).mean() * 100
    pm10_exceed = (df['pm10'] > pm10_threshold).mean() * 100
    
    print(f"PM2.5 > {pm25_threshold} μg/m³ : {pm25_exceed:.1f}% du temps")
    print(f"PM10 > {pm10_threshold} μg/m³ : {pm10_exceed:.1f}% du temps")
    print()
    
    # Moyennes
    print("Concentrations moyennes :")
    print(f"PM2.5 : {df['pm2_5'].mean():.2f} μg/m³")
    print(f"PM10 : {df['pm10'].mean():.2f} μg/m³")
    print(f"NO2 : {df['nitrogen_dioxide'].mean():.2f} μg/m³")
    print(f"CO : {df['carbon_monoxide'].mean():.2f} mg/m³")
    print(f"O3 : {df['ozone'].mean():.2f} μg/m³")
    print(f"SO2 : {df['sulphur_dioxide'].mean():.2f} μg/m³")
    print(f"CH4 : {df['methane'].mean():.2f} μg/m³")
    print(f"NH3 : {df['ammonia'].mean():.2f} μg/m³")
    print()

def daily_patterns(df):
    """Analyser les patterns journaliers"""
    print("🕐 PATTERNS JOURNALIERS")
    print("=" * 50)
    
    df['hour'] = df['date'].dt.hour
    hourly_avg = df.groupby('hour')[['pm10', 'pm2_5', 'nitrogen_dioxide', 'ozone']].mean()
    
    print("Concentrations moyennes par heure (PM2.5) :")
    for hour in range(0, 24, 3):
        print(f"{hour:02d}h : {hourly_avg.loc[hour, 'pm2_5']:.2f} μg/m³")
    print()
    
    print("Concentrations moyennes par heure (Ozone) :")
    for hour in range(0, 24, 3):
        print(f"{hour:02d}h : {hourly_avg.loc[hour, 'ozone']:.2f} μg/m³")
    print()

def correlation_analysis(df):
    """Analyser les corrélations entre polluants"""
    print("🔗 ANALYSE DES CORRÉLATIONS")
    print("=" * 50)
    
    pollutants = ['pm10', 'pm2_5', 'carbon_monoxide', 'nitrogen_dioxide', 'ozone', 'sulphur_dioxide']
    correlation_matrix = df[pollutants].corr()
    
    print("Matrice de corrélation (polluants) :")
    print(correlation_matrix.round(3))
    print()
    
    # Corrélations intéressantes
    print("Corrélations remarquables :")
    print(f"PM10 vs PM2.5 : {correlation_matrix.loc['pm10', 'pm2_5']:.3f}")
    print(f"NO2 vs PM2.5 : {correlation_matrix.loc['nitrogen_dioxide', 'pm2_5']:.3f}")
    print(f"O3 vs NO2 : {correlation_matrix.loc['ozone', 'nitrogen_dioxide']:.3f}")
    print()

def export_summary_to_db():
    """Créer une table de résumé dans la base de données"""
    conn = connect_to_db()
    df = load_data()
    
    # Créer des résumés journaliers
    df['date_only'] = df['date'].dt.date
    daily_summary = df.groupby('date_only').agg({
        'pm10': ['mean', 'max', 'min'],
        'pm2_5': ['mean', 'max', 'min'],
        'nitrogen_dioxide': ['mean', 'max', 'min'],
        'carbon_monoxide': ['mean', 'max', 'min'],
        'ozone': ['mean', 'max', 'min'],
        'sulphur_dioxide': ['mean', 'max', 'min']
    }).round(2)
    
    # Aplatir les colonnes
    daily_summary.columns = ['_'.join(col).strip() for col in daily_summary.columns.values]
    daily_summary = daily_summary.reset_index()
    
    # Sauvegarder dans la base
    daily_summary.to_sql('daily_summary', conn, if_exists='replace', index=False)
    print("✅ Résumé journalier sauvegardé dans la table 'daily_summary'")
    
    conn.close()

def main():
    """Fonction principale d'analyse"""
    print("🔬 ANALYSE DES DONNÉES DE QUALITÉ DE L'AIR - BRUXELLES")
    print("=" * 60)
    print()
    
    try:
        # Charger les données
        df = load_data()
        
        if df.empty:
            print("❌ Aucune donnée trouvée dans la base de données")
            return
        
        # Analyses
        basic_statistics(df)
        air_quality_analysis(df)
        daily_patterns(df)
        correlation_analysis(df)
        
        # Export du résumé
        export_summary_to_db()
        
        print("✅ Analyse terminée avec succès!")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse : {e}")

if __name__ == "__main__":
    main()
