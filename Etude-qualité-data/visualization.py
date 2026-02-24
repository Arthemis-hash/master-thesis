#!/usr/bin/env python3
"""
Visualisations interactives avec Plotly
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from typing import Dict, List


def plot_pollutant_evolution(df: pd.DataFrame, pollutant: str, address: str) -> go.Figure:
    """Évolution temporelle d'un polluant"""
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['value'],
        mode='lines+markers',
        name=pollutant.upper(),
        line=dict(width=2),
        marker=dict(size=6)
    ))
    
    fig.update_layout(
        title=f"Évolution {pollutant.upper()} - {address}",
        xaxis_title="Date",
        yaxis_title=f"Concentration ({df['unit'].iloc[0] if not df.empty else 'µg/m³'})",
        hovermode='x unified',
        template='plotly_white'
    )
    
    return fig


def plot_multi_pollutants(pollutant_data: Dict[str, pd.DataFrame], address: str) -> go.Figure:
    """Graphique multi-polluants normalisé"""
    
    fig = go.Figure()
    
    for pollutant, df in pollutant_data.items():
        if df.empty:
            continue
            
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['value'],
            mode='lines',
            name=pollutant.upper(),
            line=dict(width=2)
        ))
    
    fig.update_layout(
        title=f"Tous les polluants - {address}",
        xaxis_title="Date",
        yaxis_title="Concentration (µg/m³)",
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    return fig


def plot_aqi_gauge(current_score: int, category: str) -> go.Figure:
    """Jauge AQI style speedometer"""
    
    from scoring import get_health_recommendations
    info = get_health_recommendations(category)
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=current_score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Indice Qualité de l'Air"},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': info['color']},
            'steps': [
                {'range': [0, 20], 'color': '#99004c'},
                {'range': [20, 40], 'color': '#ff0000'},
                {'range': [40, 60], 'color': '#ff7e00'},
                {'range': [60, 80], 'color': '#ffff00'},
                {'range': [80, 100], 'color': '#00e400'}
            ],
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 0.75,
                'value': current_score
            }
        }
    ))
    
    fig.update_layout(height=300)
    return fig


def plot_comparison_radar(data_dict: Dict[str, Dict[str, float]]) -> go.Figure:
    """Radar chart comparaison multi-adresses"""
    
    fig = go.Figure()
    
    pollutants = list(next(iter(data_dict.values())).keys())
    
    for address, values in data_dict.items():
        fig.add_trace(go.Scatterpolar(
            r=[values.get(p, 0) for p in pollutants],
            theta=[p.upper() for p in pollutants],
            fill='toself',
            name=address
        ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True,
        title="Comparaison scores par polluant"
    )
    
    return fig


def plot_heatmap_calendar(df: pd.DataFrame, pollutant: str) -> go.Figure:
    """Heatmap calendrier style GitHub"""
    
    df['date'] = df['timestamp'].dt.date
    daily_avg = df.groupby('date')['value'].mean().reset_index()
    
    daily_avg['week'] = pd.to_datetime(daily_avg['date']).dt.isocalendar().week
    daily_avg['day'] = pd.to_datetime(daily_avg['date']).dt.dayofweek
    
    pivot = daily_avg.pivot(index='day', columns='week', values='value')
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'],
        colorscale='RdYlGn_r',
        hovertemplate='Semaine %{x}<br>%{y}<br>%{z:.1f} µg/m³<extra></extra>'
    ))
    
    fig.update_layout(
        title=f"Calendrier {pollutant.upper()}",
        xaxis_title="Semaine",
        yaxis_title="Jour"
    )
    
    return fig