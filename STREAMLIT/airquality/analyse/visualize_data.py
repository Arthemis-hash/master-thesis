#!/usr/bin/env python3
"""
Script de visualisation des données de qualité de l'air de Bruxelles
Crée des graphiques pour analyser les tendances
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np

# Configuration du style des graphiques
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

def connect_to_db():
    """Se connecter à la base de données SQLite"""
    return sqlite3.connect('bruxelles_air_quality.db')

def load_data():
    """Charger toutes les données depuis la base"""
    conn = connect_to_db()
    
    query = """
    SELECT date, pm10, pm2_5, carbon_monoxide, carbon_dioxide, 
           nitrogen_dioxide, uv_index, uv_index_clear_sky, 
           alder_pollen, birch_pollen
    FROM air_quality 
    WHERE pm10 IS NOT NULL AND pm2_5 IS NOT NULL
    ORDER BY date
    """
    
    df = pd.read_sql_query(query, conn)
    df['date'] = pd.to_datetime(df['date'])
    conn.close()
    
    return df

def plot_time_series():
    """Créer un graphique des séries temporelles"""
    df = load_data()
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('Évolution temporelle des polluants - Bruxelles (Oct 2025)', fontsize=16)
    
    # PM2.5 et PM10
    axes[0, 0].plot(df['date'], df['pm2_5'], label='PM2.5', color='red', alpha=0.7)
    axes[0, 0].plot(df['date'], df['pm10'], label='PM10', color='orange', alpha=0.7)
    axes[0, 0].axhline(y=15, color='red', linestyle='--', alpha=0.5, label='Seuil OMS PM2.5')
    axes[0, 0].set_title('Particules fines (μg/m³)')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # NO2
    axes[0, 1].plot(df['date'], df['nitrogen_dioxide'], label='NO₂', color='blue')
    axes[0, 1].set_title('Dioxyde d\'azote (μg/m³)')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    
    # CO
    axes[1, 0].plot(df['date'], df['carbon_monoxide'], label='CO', color='green')
    axes[1, 0].set_title('Monoxyde de carbone (mg/m³)')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)
    
    # UV Index
    uv_data = df[df['uv_index'].notna()]
    if not uv_data.empty:
        axes[1, 1].plot(uv_data['date'], uv_data['uv_index'], label='UV Index', color='purple')
        axes[1, 1].set_title('Indice UV')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)
    else:
        axes[1, 1].text(0.5, 0.5, 'Données UV non disponibles', 
                       ha='center', va='center', transform=axes[1, 1].transAxes)
    
    plt.tight_layout()
    plt.savefig('evolution_temporelle.png', dpi=300, bbox_inches='tight')
    plt.show()

def plot_daily_patterns():
    """Analyser les patterns quotidiens"""
    df = load_data()
    df['hour'] = df['date'].dt.hour
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('Patterns journaliers - Moyennes horaires', fontsize=16)
    
    hourly_means = df.groupby('hour')[['pm10', 'pm2_5', 'nitrogen_dioxide', 'carbon_monoxide']].mean()
    
    # PM2.5
    axes[0, 0].bar(hourly_means.index, hourly_means['pm2_5'], color='red', alpha=0.7)
    axes[0, 0].set_title('PM2.5 par heure (μg/m³)')
    axes[0, 0].set_xlabel('Heure')
    axes[0, 0].grid(True, alpha=0.3)
    
    # PM10
    axes[0, 1].bar(hourly_means.index, hourly_means['pm10'], color='orange', alpha=0.7)
    axes[0, 1].set_title('PM10 par heure (μg/m³)')
    axes[0, 1].set_xlabel('Heure')
    axes[0, 1].grid(True, alpha=0.3)
    
    # NO2
    axes[1, 0].bar(hourly_means.index, hourly_means['nitrogen_dioxide'], color='blue', alpha=0.7)
    axes[1, 0].set_title('NO₂ par heure (μg/m³)')
    axes[1, 0].set_xlabel('Heure')
    axes[1, 0].grid(True, alpha=0.3)
    
    # CO
    axes[1, 1].bar(hourly_means.index, hourly_means['carbon_monoxide'], color='green', alpha=0.7)
    axes[1, 1].set_title('CO par heure (mg/m³)')
    axes[1, 1].set_xlabel('Heure')
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('patterns_journaliers.png', dpi=300, bbox_inches='tight')
    plt.show()

def plot_correlation_heatmap():
    """Créer une heatmap des corrélations"""
    df = load_data()
    
    pollutants = ['pm10', 'pm2_5', 'carbon_monoxide', 'nitrogen_dioxide']
    correlation_matrix = df[pollutants].corr()
    
    plt.figure(figsize=(10, 8))
    sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0,
                square=True, fmt='.3f', cbar_kws={"shrink": .8})
    plt.title('Matrice de corrélation entre polluants', fontsize=14)
    plt.tight_layout()
    plt.savefig('correlation_polluants.png', dpi=300, bbox_inches='tight')
    plt.show()

def plot_distribution():
    """Créer des histogrammes de distribution"""
    df = load_data()
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('Distribution des concentrations de polluants', fontsize=16)
    
    # PM2.5
    axes[0, 0].hist(df['pm2_5'], bins=30, alpha=0.7, color='red', edgecolor='black')
    axes[0, 0].axvline(df['pm2_5'].mean(), color='darkred', linestyle='--', 
                      label=f'Moyenne: {df["pm2_5"].mean():.2f}')
    axes[0, 0].axvline(15, color='red', linestyle=':', label='Seuil OMS: 15')
    axes[0, 0].set_title('Distribution PM2.5 (μg/m³)')
    axes[0, 0].legend()
    
    # PM10
    axes[0, 1].hist(df['pm10'], bins=30, alpha=0.7, color='orange', edgecolor='black')
    axes[0, 1].axvline(df['pm10'].mean(), color='darkorange', linestyle='--',
                      label=f'Moyenne: {df["pm10"].mean():.2f}')
    axes[0, 1].axvline(45, color='red', linestyle=':', label='Seuil OMS: 45')
    axes[0, 1].set_title('Distribution PM10 (μg/m³)')
    axes[0, 1].legend()
    
    # NO2
    axes[1, 0].hist(df['nitrogen_dioxide'], bins=30, alpha=0.7, color='blue', edgecolor='black')
    axes[1, 0].axvline(df['nitrogen_dioxide'].mean(), color='darkblue', linestyle='--',
                      label=f'Moyenne: {df["nitrogen_dioxide"].mean():.2f}')
    axes[1, 0].set_title('Distribution NO₂ (μg/m³)')
    axes[1, 0].legend()
    
    # CO
    axes[1, 1].hist(df['carbon_monoxide'], bins=30, alpha=0.7, color='green', edgecolor='black')
    axes[1, 1].axvline(df['carbon_monoxide'].mean(), color='darkgreen', linestyle='--',
                      label=f'Moyenne: {df["carbon_monoxide"].mean():.2f}')
    axes[1, 1].set_title('Distribution CO (mg/m³)')
    axes[1, 1].legend()
    
    plt.tight_layout()
    plt.savefig('distribution_polluants.png', dpi=300, bbox_inches='tight')
    plt.show()

def create_summary_report():
    """Créer un rapport de synthèse"""
    df = load_data()
    
    print("📋 RAPPORT DE SYNTHÈSE - QUALITÉ DE L'AIR BRUXELLES")
    print("=" * 60)
    print(f"Période: {df['date'].min().strftime('%d/%m/%Y')} - {df['date'].max().strftime('%d/%m/%Y')}")
    print(f"Nombre de mesures: {len(df)}")
    print()
    
    # Analyse par rapport aux seuils OMS
    pm25_exceed = (df['pm2_5'] > 15).sum()
    pm10_exceed = (df['pm10'] > 45).sum()
    
    print("🚨 DÉPASSEMENTS DES SEUILS OMS:")
    print(f"PM2.5 > 15 μg/m³: {pm25_exceed} heures ({pm25_exceed/len(df)*100:.1f}%)")
    print(f"PM10 > 45 μg/m³: {pm10_exceed} heures ({pm10_exceed/len(df)*100:.1f}%)")
    print()
    
    # Moments de pics
    max_pm25_idx = df['pm2_5'].idxmax()
    max_pm10_idx = df['pm10'].idxmax()
    
    print("📈 PICS DE POLLUTION:")
    print(f"PM2.5 max: {df.loc[max_pm25_idx, 'pm2_5']:.2f} μg/m³ le {df.loc[max_pm25_idx, 'date'].strftime('%d/%m/%Y à %H:%M')}")
    print(f"PM10 max: {df.loc[max_pm10_idx, 'pm10']:.2f} μg/m³ le {df.loc[max_pm10_idx, 'date'].strftime('%d/%m/%Y à %H:%M')}")
    print()
    
    # Heures de pointe
    df['hour'] = df['date'].dt.hour
    peak_hour_pm25 = df.groupby('hour')['pm2_5'].mean().idxmax()
    low_hour_pm25 = df.groupby('hour')['pm2_5'].mean().idxmin()
    
    print("⏰ PATTERNS TEMPORELS:")
    print(f"Heure de pic PM2.5: {peak_hour_pm25}h")
    print(f"Heure de minimum PM2.5: {low_hour_pm25}h")

def main():
    """Fonction principale"""
    print("📊 GÉNÉRATION DES VISUALISATIONS...")
    
    try:
        # Créer les graphiques
        print("1. Série temporelle...")
        plot_time_series()
        
        print("2. Patterns journaliers...")
        plot_daily_patterns()
        
        print("3. Matrice de corrélation...")
        plot_correlation_heatmap()
        
        print("4. Distributions...")
        plot_distribution()
        
        print("5. Rapport de synthèse...")
        create_summary_report()
        
        print("\n✅ Toutes les visualisations ont été générées et sauvegardées!")
        print("📁 Fichiers créés: evolution_temporelle.png, patterns_journaliers.png, correlation_polluants.png, distribution_polluants.png")
        
    except Exception as e:
        print(f"❌ Erreur lors de la génération: {e}")

if __name__ == "__main__":
    main()
