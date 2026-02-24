#!/usr/bin/env python3
"""
Validation et correction interactive des données
"""

import pandas as pd
import streamlit as st
from typing import Dict, List


class DataValidator:
    """Validateur avec suggestions correction"""
    
    THRESHOLDS = {
        'pm10': {'min': 0, 'max': 500, 'typical_max': 150},
        'pm2_5': {'min': 0, 'max': 300, 'typical_max': 75},
        'no2': {'min': 0, 'max': 1000, 'typical_max': 400},
        'o3': {'min': 0, 'max': 600, 'typical_max': 240}
    }
    
    @classmethod
    def validate_dataframe(cls, df: pd.DataFrame, pollutant: str) -> Dict:
        """
        Valide DataFrame et retourne rapport
        """
        if df.empty or pollutant not in cls.THRESHOLDS:
            return {'valid': True, 'issues': []}
        
        thresholds = cls.THRESHOLDS[pollutant]
        issues = []
        
        # Valeurs négatives
        negatives = df[df['value'] < thresholds['min']]
        if not negatives.empty:
            issues.append({
                'type': 'negative_values',
                'count': len(negatives),
                'severity': 'high',
                'message': f"{len(negatives)} valeurs négatives détectées",
                'action': 'delete'
            })
        
        # Valeurs extrêmes
        extremes = df[df['value'] > thresholds['max']]
        if not extremes.empty:
            issues.append({
                'type': 'extreme_values',
                'count': len(extremes),
                'severity': 'high',
                'message': f"{len(extremes)} valeurs > {thresholds['max']} (physiquement improbable)",
                'action': 'delete'
            })
        
        # Valeurs atypiques (mais possibles)
        atypical = df[
            (df['value'] > thresholds['typical_max']) & 
            (df['value'] <= thresholds['max'])
        ]
        if not atypical.empty:
            issues.append({
                'type': 'atypical_values',
                'count': len(atypical),
                'severity': 'medium',
                'message': f"{len(atypical)} valeurs inhabituelles (pics pollution possibles)",
                'action': 'review'
            })
        
        # Valeurs -9999 (erreur capteur)
        sensor_errors = df[df['value'] == -9999]
        if not sensor_errors.empty:
            issues.append({
                'type': 'sensor_error',
                'count': len(sensor_errors),
                'severity': 'high',
                'message': f"{len(sensor_errors)} erreurs capteur (-9999)",
                'action': 'delete'
            })
        
        # Doublons temporels
        duplicates = df[df.duplicated(subset=['timestamp'], keep=False)]
        if not duplicates.empty:
            issues.append({
                'type': 'duplicates',
                'count': len(duplicates),
                'severity': 'medium',
                'message': f"{len(duplicates)} timestamps dupliqués",
                'action': 'deduplicate'
            })
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'total_records': len(df),
            'valid_records': len(df) - sum(i['count'] for i in issues if i['action'] == 'delete')
        }
    
    @staticmethod
    def correct_dataframe(df: pd.DataFrame, corrections: List[str]) -> pd.DataFrame:
        """
        Applique corrections sélectionnées
        
        Args:
            corrections: Liste actions ('delete_negatives', 'delete_extremes', etc.)
        """
        df_corrected = df.copy()
        
        if 'delete_negatives' in corrections:
            df_corrected = df_corrected[df_corrected['value'] >= 0]
        
        if 'delete_extremes' in corrections:
            df_corrected = df_corrected[df_corrected['value'] < 500]
        
        if 'delete_sensor_errors' in corrections:
            df_corrected = df_corrected[df_corrected['value'] != -9999]
        
        if 'deduplicate' in corrections:
            df_corrected = df_corrected.drop_duplicates(subset=['timestamp'], keep='first')
        
        return df_corrected


def show_validation_ui(validation_report: Dict, pollutant: str) -> List[str]:
    """
    Affiche UI Streamlit pour validation interactive
    Retourne liste corrections à appliquer
    """
    if validation_report['valid']:
        st.success(f"✅ {pollutant.upper()}: Toutes les données sont valides")
        return []
    
    st.warning(f"⚠️ {pollutant.upper()}: {len(validation_report['issues'])} problèmes détectés")
    
    corrections = []
    
    for issue in validation_report['issues']:
        with st.expander(
            f"{'🔴' if issue['severity'] == 'high' else '🟡'} {issue['message']}"
        ):
            st.write(f"**Type:** {issue['type']}")
            st.write(f"**Enregistrements affectés:** {issue['count']}")
            st.write(f"**Action recommandée:** {issue['action']}")
            
            if issue['action'] == 'delete':
                if st.button(
                    f"🗑️ Supprimer ces {issue['count']} enregistrements",
                    key=f"fix_{pollutant}_{issue['type']}"
                ):
                    corrections.append(f"delete_{issue['type']}")
                    st.success("✅ Correction appliquée")
            
            elif issue['action'] == 'review':
                st.info("ℹ️ Valeurs conservées (pics pollution possibles)")
            
            elif issue['action'] == 'deduplicate':
                if st.button(
                    f"🔧 Dédupliquer ({issue['count']} doublons)",
                    key=f"fix_{pollutant}_{issue['type']}"
                ):
                    corrections.append('deduplicate')
                    st.success("✅ Déduplication appliquée")
    
    return corrections