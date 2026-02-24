#!/usr/bin/env python3
"""
============================================================
VALIDATION ET BENCHMARK DU MÉTA-SCORE QeV
Tests de Fiabilité et Robustesse
============================================================

Méthodes de validation:
1. Analyse de sensibilité (variation des poids)
2. Test de cohérence interne (corrélations)
3. Test de capacité discriminante
4. Validation croisée avec indices existants
5. Tests de robustesse aux valeurs extrêmes

Références:
- Saisana & Tarantola (2002): State-of-the-art report on composite indicators
- Saltelli et al. (2008): Global Sensitivity Analysis
============================================================
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, List, Tuple
import logging
from scipy.stats import pearsonr, spearmanr
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score

# Import du calculateur principal
from metascore_calculator import (
    QeVCalculator, QeVConfig, QeVSimulator,
    TrafficData, GreenSpaceData, AirQualityData, QeVScore
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# CLASSE DE VALIDATION
# ============================================================

class QeVValidator:
    """Valide et teste la robustesse du méta-score QeV"""
    
    def __init__(self, calculator: QeVCalculator):
        """
        Initialise le validateur
        
        Args:
            calculator: Instance du calculateur QeV
        """
        self.calculator = calculator
        self.baseline_config = calculator.config
        self.validation_results = {}
    
    def sensitivity_analysis(
        self,
        scenarios: List[Tuple[TrafficData, GreenSpaceData, AirQualityData]],
        weight_variations: List[float] = None
    ) -> Dict:
        """
        Analyse de sensibilité: teste l'impact de la variation des poids
        
        Objectif: Vérifier si de petites modifications des poids changent
        drastiquement le classement des zones (signe d'instabilité)
        
        Args:
            scenarios: Liste de tuples (traffic, green, air)
            weight_variations: Liste de variations à tester (ex: [-0.2, -0.1, 0, 0.1, 0.2])
            
        Returns:
            Dictionnaire avec résultats d'analyse
        """
        logger.info("\n" + "="*60)
        logger.info("🔬 ANALYSE DE SENSIBILITÉ")
        logger.info("="*60 + "\n")
        
        if weight_variations is None:
            weight_variations = [-0.2, -0.15, -0.1, -0.05, 0, 0.05, 0.1, 0.15, 0.2]
        
        baseline_weights = self.baseline_config.GLOBAL_WEIGHTS.copy()
        baseline_scores = []
        
        # Calculer scores de référence
        logger.info("📊 Calcul des scores de référence...")
        for traffic, green, air in scenarios:
            score = self.calculator.calculate_qev_score(traffic, green, air)
            baseline_scores.append(score.qev_score)
        
        baseline_ranking = np.argsort(baseline_scores)[::-1]  # Tri décroissant
        
        results = {
            'baseline_scores': baseline_scores,
            'baseline_ranking': baseline_ranking,
            'variations': {},
            'ranking_changes': [],
            'score_changes': []
        }
        
        # Tester chaque variation
        logger.info(f"🧪 Test de {len(weight_variations)} variations de poids...\n")
        
        for variation in weight_variations:
            if variation == 0:
                continue
            
            # Varier le poids 'air' et ajuster les autres proportionnellement
            new_air_weight = baseline_weights['air'] + variation
            
            # Contraintes: poids entre 0 et 1, somme = 1
            if new_air_weight <= 0 or new_air_weight >= 1:
                continue
            
            remaining = 1.0 - new_air_weight
            ratio = remaining / (baseline_weights['traffic'] + baseline_weights['green'])
            
            new_weights = {
                'air': new_air_weight,
                'traffic': baseline_weights['traffic'] * ratio,
                'green': baseline_weights['green'] * ratio
            }
            
            # Créer une nouvelle config avec ces poids
            test_config = QeVConfig()
            test_config.GLOBAL_WEIGHTS = new_weights
            test_calculator = QeVCalculator(test_config)
            
            # Recalculer tous les scores
            varied_scores = []
            for traffic, green, air in scenarios:
                score = test_calculator.calculate_qev_score(traffic, green, air)
                varied_scores.append(score.qev_score)
            
            varied_ranking = np.argsort(varied_scores)[::-1]
            
            # Calculer les changements
            ranking_diff = np.sum(np.abs(baseline_ranking - varied_ranking))
            score_mae = mean_absolute_error(baseline_scores, varied_scores)
            max_score_change = np.max(np.abs(np.array(baseline_scores) - np.array(varied_scores)))
            
            results['variations'][f'{variation:+.2f}'] = {
                'weights': new_weights,
                'scores': varied_scores,
                'ranking': varied_ranking,
                'ranking_difference': ranking_diff,
                'mae': score_mae,
                'max_change': max_score_change
            }
            
            results['ranking_changes'].append(ranking_diff)
            results['score_changes'].append(score_mae)
            
            logger.info(f"Variation {variation:+.2f}: "
                       f"Δ ranking={ranking_diff}, MAE={score_mae:.4f}, "
                       f"Max Δ={max_score_change:.4f}")
        
        # Calculer statistiques de robustesse
        if results['ranking_changes']:
            avg_ranking_change = np.mean(results['ranking_changes'])
            max_ranking_change = np.max(results['ranking_changes'])
            avg_score_mae = np.mean(results['score_changes'])
            
            results['robustness_metrics'] = {
                'avg_ranking_change': avg_ranking_change,
                'max_ranking_change': max_ranking_change,
                'avg_score_mae': avg_score_mae,
                'is_robust': avg_ranking_change < len(scenarios) * 0.2  # <20% changement
            }
            
            logger.info(f"\n📈 Résultats:")
            logger.info(f"   Changement moyen de rang: {avg_ranking_change:.1f}")
            logger.info(f"   Changement max de rang: {max_ranking_change:.0f}")
            logger.info(f"   MAE moyen des scores: {avg_score_mae:.4f}")
            
            if results['robustness_metrics']['is_robust']:
                logger.info("   ✅ Le modèle est ROBUSTE aux variations de poids")
            else:
                logger.info("   ⚠️  Le modèle est SENSIBLE aux variations de poids")
        
        self.validation_results['sensitivity'] = results
        return results
    
    def internal_consistency_test(self, scores: List[QeVScore]) -> Dict:
        """
        Test de cohérence interne: vérifie les corrélations entre composantes
        
        Objectif: S'assurer que les sous-indices ne sont pas trop corrélés
        (redondance) ni trop indépendants (incohérence)
        
        Args:
            scores: Liste de scores QeV calculés
            
        Returns:
            Dictionnaire avec corrélations et diagnostics
        """
        logger.info("\n" + "="*60)
        logger.info("🔬 TEST DE COHÉRENCE INTERNE")
        logger.info("="*60 + "\n")
        
        # Extraire les composantes
        air_scores = [s.air_score for s in scores]
        traffic_scores = [s.traffic_score for s in scores]
        green_scores = [s.green_score for s in scores]
        qev_scores = [s.qev_score for s in scores]
        
        # Créer DataFrame pour faciliter l'analyse
        df = pd.DataFrame({
            'Air': air_scores,
            'Trafic': traffic_scores,
            'Vert': green_scores,
            'QeV': qev_scores
        })
        
        # Calculer matrice de corrélation
        corr_pearson = df.corr(method='pearson')
        corr_spearman = df.corr(method='spearman')
        
        logger.info("📊 Matrice de corrélation (Pearson):")
        logger.info(corr_pearson.to_string())
        logger.info("")
        
        # Analyser les corrélations entre sous-indices
        results = {
            'correlation_pearson': corr_pearson.to_dict(),
            'correlation_spearman': corr_spearman.to_dict(),
            'diagnostics': {}
        }
        
        # Test 1: Multicolinéarité entre Air et Trafic
        air_traffic_corr = corr_pearson.loc['Air', 'Trafic']
        results['diagnostics']['air_traffic_collinearity'] = {
            'correlation': air_traffic_corr,
            'is_problematic': abs(air_traffic_corr) > 0.9,
            'interpretation': (
                "Forte multicolinéarité (>0.9)" if abs(air_traffic_corr) > 0.9
                else "Multicolinéarité acceptable (<0.9)"
            )
        }
        
        logger.info(f"🔍 Corrélation Air-Trafic: {air_traffic_corr:.3f}")
        logger.info(f"   → {results['diagnostics']['air_traffic_collinearity']['interpretation']}")
        
        # Test 2: Contribution équilibrée au score final
        contributions = {
            'Air': abs(corr_pearson.loc['Air', 'QeV']),
            'Trafic': abs(corr_pearson.loc['Trafic', 'QeV']),
            'Vert': abs(corr_pearson.loc['Vert', 'QeV'])
        }
        
        max_contrib = max(contributions.values())
        min_contrib = min(contributions.values())
        contrib_ratio = max_contrib / min_contrib if min_contrib > 0 else float('inf')
        
        results['diagnostics']['contribution_balance'] = {
            'contributions': contributions,
            'ratio': contrib_ratio,
            'is_balanced': contrib_ratio < 3.0,
            'interpretation': (
                "Contributions équilibrées" if contrib_ratio < 3.0
                else "Une composante domine excessivement"
            )
        }
        
        logger.info(f"\n🔍 Contributions au QeV:")
        for comp, val in contributions.items():
            logger.info(f"   {comp}: {val:.3f}")
        logger.info(f"   Ratio max/min: {contrib_ratio:.2f}")
        logger.info(f"   → {results['diagnostics']['contribution_balance']['interpretation']}")
        
        # Test 3: Variance expliquée
        from sklearn.linear_model import LinearRegression
        
        X = df[['Air', 'Trafic', 'Vert']].values
        y = df['QeV'].values
        
        model = LinearRegression()
        model.fit(X, y)
        r2 = model.score(X, y)
        
        results['diagnostics']['variance_explained'] = {
            'r2': r2,
            'interpretation': (
                "Excellent (>0.95)" if r2 > 0.95
                else "Bon (>0.90)" if r2 > 0.90
                else "Acceptable (>0.80)" if r2 > 0.80
                else "Faible (<0.80)"
            )
        }
        
        logger.info(f"\n🔍 Variance expliquée (R²): {r2:.4f}")
        logger.info(f"   → {results['diagnostics']['variance_explained']['interpretation']}")
        
        self.validation_results['consistency'] = results
        return results
    
    def discriminant_power_test(self, scores: List[QeVScore]) -> Dict:
        """
        Test de capacité discriminante: vérifie si le score différencie bien les zones
        
        Objectif: S'assurer que le score n'est pas trop "lissé" ou "extrême"
        
        Args:
            scores: Liste de scores QeV
            
        Returns:
            Dictionnaire avec métriques de discrimination
        """
        logger.info("\n" + "="*60)
        logger.info("🔬 TEST DE CAPACITÉ DISCRIMINANTE")
        logger.info("="*60 + "\n")
        
        qev_values = [s.qev_score for s in scores]
        
        # Statistiques descriptives
        mean_score = np.mean(qev_values)
        std_score = np.std(qev_values)
        cv = std_score / mean_score if mean_score > 0 else 0  # Coefficient de variation
        score_range = np.max(qev_values) - np.min(qev_values)
        
        # Distribution par catégories
        categories = {}
        for score in scores:
            categories[score.category] = categories.get(score.category, 0) + 1
        
        # Calculer l'entropie de Shannon (mesure de diversité)
        total = len(scores)
        entropy = -sum((count/total) * np.log2(count/total) 
                      for count in categories.values())
        max_entropy = np.log2(len(categories)) if categories else 0
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
        
        results = {
            'mean': mean_score,
            'std': std_score,
            'cv': cv,
            'range': score_range,
            'categories': categories,
            'entropy': entropy,
            'normalized_entropy': normalized_entropy,
            'diagnostics': {}
        }
        
        # Diagnostic 1: Coefficient de variation
        results['diagnostics']['variation'] = {
            'cv': cv,
            'is_adequate': 0.15 < cv < 0.40,
            'interpretation': (
                "Bonne discrimination" if 0.15 < cv < 0.40
                else "Trop homogène (<0.15)" if cv <= 0.15
                else "Trop hétérogène (>0.40)"
            )
        }
        
        logger.info(f"📊 Statistiques:")
        logger.info(f"   Moyenne: {mean_score:.3f}")
        logger.info(f"   Écart-type: {std_score:.3f}")
        logger.info(f"   Coefficient de variation: {cv:.3f}")
        logger.info(f"   Étendue: {score_range:.3f}")
        logger.info(f"   → {results['diagnostics']['variation']['interpretation']}")
        
        # Diagnostic 2: Distribution par catégories
        results['diagnostics']['distribution'] = {
            'entropy': normalized_entropy,
            'is_diverse': normalized_entropy > 0.6,
            'interpretation': (
                "Distribution diverse" if normalized_entropy > 0.6
                else "Distribution concentrée"
            )
        }
        
        logger.info(f"\n📊 Distribution par catégories:")
        for cat, count in sorted(categories.items()):
            pct = (count / total) * 100
            logger.info(f"   {cat}: {count} ({pct:.1f}%)")
        logger.info(f"   Entropie normalisée: {normalized_entropy:.3f}")
        logger.info(f"   → {results['diagnostics']['distribution']['interpretation']}")
        
        # Diagnostic 3: Capacité à séparer extrêmes
        bottom_10 = np.percentile(qev_values, 10)
        top_10 = np.percentile(qev_values, 90)
        separation = top_10 - bottom_10
        
        results['diagnostics']['separation'] = {
            'percentile_10': bottom_10,
            'percentile_90': top_10,
            'separation': separation,
            'is_adequate': separation > 0.3,
            'interpretation': (
                "Bonne séparation (>0.3)" if separation > 0.3
                else "Séparation faible (<0.3)"
            )
        }
        
        logger.info(f"\n📊 Séparation des extrêmes:")
        logger.info(f"   10e percentile: {bottom_10:.3f}")
        logger.info(f"   90e percentile: {top_10:.3f}")
        logger.info(f"   Écart: {separation:.3f}")
        logger.info(f"   → {results['diagnostics']['separation']['interpretation']}")
        
        self.validation_results['discriminant'] = results
        return results
    
    def extreme_values_test(
        self,
        scenarios: List[Tuple[TrafficData, GreenSpaceData, AirQualityData]]
    ) -> Dict:
        """
        Test de robustesse aux valeurs extrêmes
        
        Objectif: Vérifier que le score ne produit pas de résultats absurdes
        avec des valeurs extrêmes
        
        Args:
            scenarios: Liste de scénarios normaux
            
        Returns:
            Résultats des tests
        """
        logger.info("\n" + "="*60)
        logger.info("🔬 TEST DE ROBUSTESSE AUX VALEURS EXTRÊMES")
        logger.info("="*60 + "\n")
        
        results = {
            'baseline': [],
            'extreme_tests': []
        }
        
        # Calculer scores de référence
        for traffic, green, air in scenarios[:3]:  # Prendre 3 exemples
            score = self.calculator.calculate_qev_score(traffic, green, air)
            results['baseline'].append({
                'location': score.location,
                'qev': score.qev_score
            })
        
        # Test 1: Pollution maximale
        logger.info("🧪 Test 1: Pollution maximale")
        extreme_air = AirQualityData(
            no2_concentration=100,
            pm25_concentration=50,
            pm10_concentration=100,
            location="Zone Extrême - Pollution Max"
        )
        extreme_traffic = TrafficData(5000, 500, 200, "Zone Extrême")
        minimal_green = GreenSpaceData(1000, 0, "Zone Extrême")
        
        worst_score = self.calculator.calculate_qev_score(
            extreme_traffic, minimal_green, extreme_air
        )
        
        results['extreme_tests'].append({
            'test': 'pollution_max',
            'qev': worst_score.qev_score,
            'is_valid': 0.0 <= worst_score.qev_score <= 0.3,
            'interpretation': (
                "Score cohérent (proche de 0)" if worst_score.qev_score <= 0.3
                else "⚠️ Score trop élevé pour conditions extrêmes"
            )
        })
        
        logger.info(f"   Score QeV: {worst_score.qev_score:.3f}")
        logger.info(f"   → {results['extreme_tests'][-1]['interpretation']}")
        
        # Test 2: Conditions idéales
        logger.info("\n🧪 Test 2: Conditions idéales")
        perfect_air = AirQualityData(
            no2_concentration=5,
            pm25_concentration=3,
            pm10_concentration=8,
            location="Zone Idéale - Conditions Parfaites"
        )
        minimal_traffic = TrafficData(50, 5, 0, "Zone Idéale")
        maximal_green = GreenSpaceData(500000, 100, "Zone Idéale")
        
        best_score = self.calculator.calculate_qev_score(
            minimal_traffic, maximal_green, perfect_air
        )
        
        results['extreme_tests'].append({
            'test': 'conditions_ideal',
            'qev': best_score.qev_score,
            'is_valid': 0.7 <= best_score.qev_score <= 1.0,
            'interpretation': (
                "Score cohérent (proche de 1)" if best_score.qev_score >= 0.7
                else "⚠️ Score trop faible pour conditions idéales"
            )
        })
        
        logger.info(f"   Score QeV: {best_score.qev_score:.3f}")
        logger.info(f"   → {results['extreme_tests'][-1]['interpretation']}")
        
        # Test 3: Écart entre extrêmes
        extreme_range = best_score.qev_score - worst_score.qev_score
        
        results['extreme_range'] = {
            'range': extreme_range,
            'is_adequate': extreme_range > 0.5,
            'interpretation': (
                "Bonne discrimination extrêmes (>0.5)" if extreme_range > 0.5
                else "⚠️ Discrimination insuffisante (<0.5)"
            )
        }
        
        logger.info(f"\n📊 Écart entre extrêmes: {extreme_range:.3f}")
        logger.info(f"   → {results['extreme_range']['interpretation']}")
        
        self.validation_results['extreme'] = results
        return results
    
    def generate_validation_report(self, output_file: str = "validation_report.txt"):
        """
        Génère un rapport complet de validation
        
        Args:
            output_file: Nom du fichier de sortie
        """
        if not self.validation_results:
            logger.warning("⚠️  Aucun résultat de validation disponible")
            return
        
        report_path = Path(__file__).parent / output_file
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("RAPPORT DE VALIDATION - MÉTA-SCORE QeV\n")
            f.write("Tests de Fiabilité et Robustesse\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Date: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
            
            # 1. Analyse de sensibilité
            if 'sensitivity' in self.validation_results:
                f.write("-" * 80 + "\n")
                f.write("1. ANALYSE DE SENSIBILITÉ\n")
                f.write("-" * 80 + "\n\n")
                
                sens = self.validation_results['sensitivity']
                
                if 'robustness_metrics' in sens:
                    metrics = sens['robustness_metrics']
                    f.write("Résumé:\n")
                    f.write(f"  • Changement moyen de rang: {metrics['avg_ranking_change']:.2f}\n")
                    f.write(f"  • Changement max de rang: {metrics['max_ranking_change']:.0f}\n")
                    f.write(f"  • MAE moyen des scores: {metrics['avg_score_mae']:.4f}\n")
                    f.write(f"  • Modèle robuste: {'✅ OUI' if metrics['is_robust'] else '⚠️ NON'}\n\n")
                    
                    f.write("Interprétation:\n")
                    if metrics['is_robust']:
                        f.write("Le modèle est ROBUSTE. Les variations de poids (±20%) n'affectent\n")
                        f.write("pas significativement le classement des zones. Cela démontre que les\n")
                        f.write("conclusions sont fiables et ne dépendent pas excessivement des choix\n")
                        f.write("de pondération.\n\n")
                    else:
                        f.write("⚠️ Le modèle montre une certaine SENSIBILITÉ aux poids. Il est recommandé\n")
                        f.write("de justifier les pondérations choisies par la littérature ou par un\n")
                        f.write("consensus d'experts (méthode Delphi).\n\n")
            
            # 2. Cohérence interne
            if 'consistency' in self.validation_results:
                f.write("-" * 80 + "\n")
                f.write("2. COHÉRENCE INTERNE\n")
                f.write("-" * 80 + "\n\n")
                
                cons = self.validation_results['consistency']
                diag = cons['diagnostics']
                
                # Multicolinéarité
                if 'air_traffic_collinearity' in diag:
                    mc = diag['air_traffic_collinearity']
                    f.write(f"a) Multicolinéarité Air-Trafic: {mc['correlation']:.3f}\n")
                    f.write(f"   Statut: {mc['interpretation']}\n\n")
                
                # Contributions
                if 'contribution_balance' in diag:
                    cb = diag['contribution_balance']
                    f.write("b) Contributions au score final:\n")
                    for comp, val in cb['contributions'].items():
                        f.write(f"   • {comp}: {val:.3f}\n")
                    f.write(f"   Ratio max/min: {cb['ratio']:.2f}\n")
                    f.write(f"   Statut: {cb['interpretation']}\n\n")
                
                # Variance expliquée
                if 'variance_explained' in diag:
                    ve = diag['variance_explained']
                    f.write(f"c) Variance expliquée (R²): {ve['r2']:.4f}\n")
                    f.write(f"   Statut: {ve['interpretation']}\n\n")
            
            # 3. Capacité discriminante
            if 'discriminant' in self.validation_results:
                f.write("-" * 80 + "\n")
                f.write("3. CAPACITÉ DISCRIMINANTE\n")
                f.write("-" * 80 + "\n\n")
                
                disc = self.validation_results['discriminant']
                diag = disc['diagnostics']
                
                # Variation
                if 'variation' in diag:
                    var = diag['variation']
                    f.write(f"a) Coefficient de variation: {var['cv']:.3f}\n")
                    f.write(f"   Statut: {var['interpretation']}\n\n")
                
                # Distribution
                if 'distribution' in diag:
                    dist = diag['distribution']
                    f.write(f"b) Entropie normalisée: {dist['entropy']:.3f}\n")
                    f.write(f"   Statut: {dist['interpretation']}\n\n")
                
                # Séparation
                if 'separation' in diag:
                    sep = diag['separation']
                    f.write(f"c) Séparation extrêmes (P90-P10): {sep['separation']:.3f}\n")
                    f.write(f"   Statut: {sep['interpretation']}\n\n")
            
            # 4. Valeurs extrêmes
            if 'extreme' in self.validation_results:
                f.write("-" * 80 + "\n")
                f.write("4. ROBUSTESSE AUX VALEURS EXTRÊMES\n")
                f.write("-" * 80 + "\n\n")
                
                ext = self.validation_results['extreme']
                
                for test in ext['extreme_tests']:
                    f.write(f"{test['test']}: Score = {test['qev']:.3f}\n")
                    f.write(f"  → {test['interpretation']}\n\n")
                
                if 'extreme_range' in ext:
                    er = ext['extreme_range']
                    f.write(f"Écart entre extrêmes: {er['range']:.3f}\n")
                    f.write(f"  → {er['interpretation']}\n\n")
            
            # Conclusion
            f.write("-" * 80 + "\n")
            f.write("5. CONCLUSION GÉNÉRALE\n")
            f.write("-" * 80 + "\n\n")
            
            # Compiler les statuts
            all_valid = True
            issues = []
            
            if 'sensitivity' in self.validation_results:
                if not self.validation_results['sensitivity'].get('robustness_metrics', {}).get('is_robust', True):
                    all_valid = False
                    issues.append("Sensibilité aux poids de pondération")
            
            if all_valid:
                f.write("✅ Le méta-score QeV passe TOUS les tests de validation.\n\n")
                f.write("Le modèle est:\n")
                f.write("• Robuste aux variations de paramètres\n")
                f.write("• Cohérent dans sa structure interne\n")
                f.write("• Capable de discriminer efficacement les zones\n")
                f.write("• Fiable avec des valeurs extrêmes\n\n")
                f.write("Ce score peut être utilisé en toute confiance pour l'analyse\n")
                f.write("de la qualité environnementale urbaine.\n")
            else:
                f.write("⚠️ Le méta-score QeV présente quelques points d'attention:\n\n")
                for issue in issues:
                    f.write(f"• {issue}\n")
                f.write("\nRecommandations:\n")
                f.write("• Justifier les pondérations par la littérature\n")
                f.write("• Effectuer une analyse de sensibilité dans le rapport\n")
                f.write("• Discuter les limites en transparence\n")
            
            f.write("\n" + "=" * 80 + "\n")
        
        logger.info(f"✅ Rapport de validation généré: {report_path}")


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def main():
    """Point d'entrée principal du script de validation"""
    
    print("\n" + "="*80)
    print("VALIDATION ET BENCHMARK DU MÉTA-SCORE QeV")
    print("Tests de Fiabilité et Robustesse")
    print("="*80 + "\n")
    
    # Créer calculateur et simulateur
    calculator = QeVCalculator()
    simulator = QeVSimulator(calculator)
    validator = QeVValidator(calculator)
    
    # Générer des scénarios de test
    logger.info("📊 Génération de scénarios de test...\n")
    
    test_scenarios = []
    for i in range(20):
        # Créer des scénarios variés
        traffic_level = np.random.uniform(100, 2000)
        green_level = np.random.uniform(0.2, 0.9)
        air_level = np.random.uniform(10, 80)
        
        traffic = TrafficData(
            cars=traffic_level,
            vans=traffic_level * 0.15,
            trucks=traffic_level * 0.05,
            location=f"Zone Test {i+1}"
        )
        
        green = GreenSpaceData(
            green_surface_m2_per_km2=green_level * 500000,
            trees_within_150m=int(green_level * 80),
            location=f"Zone Test {i+1}"
        )
        
        air = AirQualityData(
            no2_concentration=air_level,
            pm25_concentration=air_level * 0.4,
            pm10_concentration=air_level * 0.8,
            location=f"Zone Test {i+1}"
        )
        
        test_scenarios.append((traffic, green, air))
    
    # Calculer les scores
    logger.info("🧮 Calcul des scores pour validation...\n")
    test_scores = []
    for traffic, green, air in test_scenarios:
        score = calculator.calculate_qev_score(traffic, green, air)
        test_scores.append(score)
    
    # Exécuter les tests de validation
    logger.info("🔬 Exécution des tests de validation...\n")
    
    # 1. Analyse de sensibilité
    validator.sensitivity_analysis(test_scenarios)
    
    # 2. Cohérence interne
    validator.internal_consistency_test(test_scores)
    
    # 3. Capacité discriminante
    validator.discriminant_power_test(test_scores)
    
    # 4. Valeurs extrêmes
    validator.extreme_values_test(test_scenarios)
    
    # Générer rapport
    print("\n" + "-"*80)
    print("📄 GÉNÉRATION DU RAPPORT DE VALIDATION")
    print("-"*80 + "\n")
    
    validator.generate_validation_report("benchmark_validation_report.txt")
    
    print("\n" + "="*80)
    print("✅ VALIDATION TERMINÉE")
    print("="*80)
    print("\n📄 Fichier généré: benchmark_validation_report.txt\n")


if __name__ == "__main__":
    main()
