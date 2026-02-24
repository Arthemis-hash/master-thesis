# 📊 Calculateur de Méta-Score QeV

## Qualité Environnementale de Vie - Analyse et Validation

Ce module implémente un système complet de calcul, simulation et validation d'un méta-score de qualité environnementale de vie (QeV) basé sur des méthodologies scientifiques reconnues.

---

## 🎯 Objectifs

1. **Calculer** un indicateur composite QeV basé sur :
   - 🚗 Trafic routier (nuisances)
   - 🌳 Espaces verts (bien-être)
   - 💨 Qualité de l'air (santé)

2. **Simuler** des scénarios à partir de données réelles ou fictives

3. **Valider** la robustesse et la fiabilité du méta-score avec des techniques de benchmark

---

## 📁 Structure des Fichiers

```
airquality/
├── metascore_calculator.py      # Calculateur principal du méta-score QeV
├── benchmark_validation.py      # Tests de validation et robustesse
├── README_METASCORE.md          # Ce fichier
└── app/
    └── databases/               # Bases de données SQLite avec données réelles
```

---

## 🔬 Méthodologie Scientifique

### Cadre Théorique

Le méta-score QeV est construit selon les principes suivants :

| Source | Application |
|--------|-------------|
| **OECD/JRC (2008)** | Méthodologie de construction d'indicateurs composites |
| **IRCEL-CELINE** | Approche BelAQI pour la qualité de l'air |
| **EMEP/EEA** | Facteurs d'émission (PCU - Passenger Car Units) |
| **WHO (2016)** | Impact des espaces verts sur la santé |

### Formule Mathématique

```
QeV = W_air × S_air + W_traffic × S_traffic + W_green × S_green

Où :
- W_air = 0.40 (40% - Impact vital direct)
- W_traffic = 0.30 (30% - Nuisances)
- W_green = 0.30 (30% - Impact psychologique)
```

### Sous-Indices

#### 1. Indice de Trafic (I_traffic)
```
I_traffic = (N_cars × 1) + (N_vans × 3) + (N_trucks × 10)
```
Basé sur les facteurs d'émission PCU (conservateurs)

#### 2. Indice de Verdure (I_green)
```
I_green = 0.5 × (Surface_verte/km²) + 0.5 × (Arbres_150m)
```
Combine densité globale et proximité immédiate

#### 3. Indice de Qualité de l'Air (I_air)
```
I_air = moyenne(NO2_normalisé, PM2.5_normalisé, PM10_normalisé)
```
Concentration normalisée des polluants majeurs

### Normalisation Min-Max

Tous les indicateurs sont normalisés entre 0 et 1 :
```
S_x = (x - min) / (max - min)
```

Pour les indicateurs négatifs (trafic, pollution) :
```
S_x_inversé = 1 - S_x
```
(Pour que 1 = Bon et 0 = Mauvais)

---

## 🚀 Installation et Utilisation

### Prérequis

```bash
# Activer l'environnement virtuel
source /Users/macbook/Desktop/Master-Thésis/env/bin/activate

# Installer les dépendances (si nécessaire)
pip install numpy pandas matplotlib seaborn scipy scikit-learn
```

### Utilisation

#### 1. Calculer le Méta-Score QeV

```bash
cd /Users/macbook/Desktop/Master-Thésis/STREAMLIT/airquality
python metascore_calculator.py
```

**Sortie :**
- `rapport_metascore_qev.txt` : Rapport détaillé avec méthodologie et résultats
- `analyse_qev.png` : Visualisations graphiques

**Ce script va :**
- ✅ Extraire les données depuis les bases SQLite
- ✅ Calculer les sous-indices (Trafic, Verdure, Air)
- ✅ Normaliser et agréger les scores
- ✅ Générer un rapport complet avec sources bibliographiques
- ✅ Créer des visualisations

#### 2. Valider et Tester la Robustesse

```bash
python benchmark_validation.py
```

**Sortie :**
- `benchmark_validation_report.txt` : Rapport de validation complet

**Ce script va :**
- 🔬 Analyse de sensibilité (variation des poids ±20%)
- 🔬 Test de cohérence interne (corrélations)
- 🔬 Test de capacité discriminante
- 🔬 Test de robustesse aux valeurs extrêmes

---

## 📊 Exemples de Résultats

### Scénarios Fictifs

| Zone | Trafic | Verdure | Air | Score QeV | Catégorie |
|------|--------|---------|-----|-----------|-----------|
| Zone A - Viaduc | Élevé | Faible | Mauvais | 0.136 | ⚠️ Critique |
| Zone B - Parc | Faible | Élevé | Bon | 0.861 | ✅ Excellent |
| Zone C - Centre | Moyen | Moyen | Moyen | 0.520 | 🟡 Médiocre |

### Interprétation

L'écart entre Zone A (0.136) et Zone B (0.861) démontre :
- ✅ **Capacité discriminante** : Le modèle différencie fortement les zones
- ✅ **Cohérence** : Pénalise "Trafic + Mauvais Air", valorise "Nature + Calme"
- ✅ **Robustesse** : Résultats stables aux variations de paramètres

---

## 🔍 Tests de Validation

### 1. Analyse de Sensibilité

**Question** : Le classement des zones change-t-il si on modifie légèrement les poids ?

**Méthode** : Variation de ±20% des pondérations

**Résultat attendu** :
- ✅ **Robuste** : Changement de rang < 20%
- ⚠️ **Sensible** : Changement de rang > 20%

### 2. Cohérence Interne

**Question** : Les sous-indices sont-ils trop corrélés (redondance) ?

**Méthode** : Matrice de corrélation de Pearson/Spearman

**Critères** :
- ✅ Corrélation Air-Trafic < 0.9 (acceptable)
- ✅ R² > 0.90 (variance expliquée)
- ✅ Contributions équilibrées (ratio < 3.0)

### 3. Capacité Discriminante

**Question** : Le score différencie-t-il suffisamment les zones ?

**Méthode** : Coefficient de variation, entropie de Shannon

**Critères** :
- ✅ Coefficient de variation : 0.15 < CV < 0.40
- ✅ Entropie normalisée > 0.6 (distribution diverse)
- ✅ Séparation P90-P10 > 0.3

### 4. Valeurs Extrêmes

**Question** : Le score reste-t-il cohérent avec des données extrêmes ?

**Tests** :
- 🧪 Pollution maximale → Score ≈ 0.0 attendu
- 🧪 Conditions idéales → Score ≈ 1.0 attendu
- 🧪 Écart entre extrêmes > 0.5

---

## 📈 Catégories de Qualité

| Score QeV | Catégorie | Couleur | Interprétation |
|-----------|-----------|---------|----------------|
| 0.8 - 1.0 | Excellent | 🟢 Vert | Qualité de vie optimale |
| 0.6 - 0.8 | Bon | 🟢 Vert clair | Bonne qualité de vie |
| 0.4 - 0.6 | Médiocre | 🟡 Jaune | Qualité de vie moyenne |
| 0.2 - 0.4 | Mauvais | 🟠 Orange | Zone à améliorer |
| 0.0 - 0.2 | Critique | 🔴 Rouge | Zone prioritaire d'intervention |

---

## 📚 Limites et Discussion

### 1. Multicolinéarité Air-Trafic

**Problème** : Le trafic génère de la pollution, donc ces indicateurs sont naturellement corrélés.

**Justification** : Ils mesurent des impacts **distincts** :
- **Air** : Toxicité physiologique (santé respiratoire)
- **Trafic** : Nuisances non-chimiques (bruit, insécurité, espace public)

### 2. Subjectivité de la Pondération

**Problème** : Les poids (40% air, 30% trafic, 30% vert) sont normatifs.

**Solution** : 
- Justifier par la littérature épidémiologique
- Analyse de sensibilité (variation ±10%)
- Consultation d'experts (méthode Delphi)

### 3. Linéarité vs Effets de Seuil

**Problème** : La normalisation Min-Max est linéaire, mais les effets sanitaires ne le sont pas toujours.

**Exemple** : Passer de 40 à 50 µg/m³ de NO₂ a plus d'impact que de 10 à 20 µg/m³ (seuils critiques OMS).

**Amélioration possible** : Fonction logarithmique pour hautes doses.

---

## 📖 Références Bibliographiques

1. **OECD/JRC (2008)**. *Handbook on Constructing Composite Indicators: Methodology and User Guide*. OECD Publishing, Paris.

2. **IRCEL-CELINE**. *Documentation technique sur l'indice BelAQI*. Cellule Interrégionale de l'Environnement, Belgique.

3. **EMEP/EEA (2019)**. *Air Pollutant Emission Inventory Guidebook*. European Environment Agency, Copenhagen.

4. **WHO (2016)**. *Urban green spaces and health*. Copenhagen: WHO Regional Office for Europe.

5. **Saisana, M., & Tarantola, S. (2002)**. *State-of-the-art report on current methodologies and practices for composite indicator development*. EUR 20408 EN, European Commission-JRC.

6. **Saltelli, A. et al. (2008)**. *Global Sensitivity Analysis: The Primer*. John Wiley & Sons.

---

## 💡 Applications Possibles

### Pour la Recherche
- ✅ Identifier les zones prioritaires d'intervention
- ✅ Évaluer l'impact de politiques d'aménagement
- ✅ Comparer différents quartiers/villes
- ✅ Études épidémiologiques spatiales

### Pour les Décideurs
- ✅ Outil d'aide à la décision pour urbanisme
- ✅ Priorisation des investissements publics
- ✅ Monitoring de l'évolution de la qualité environnementale

### Pour la Communication
- ✅ Communiquer simplement une réalité complexe au public
- ✅ Sensibilisation aux enjeux environnementaux
- ✅ Tableaux de bord interactifs

---

## 🛠️ Personnalisation

### Modifier les Pondérations

Dans `metascore_calculator.py`, ligne ~130 :

```python
class QeVConfig:
    GLOBAL_WEIGHTS = {
        'air': 0.40,      # Modifier ici
        'traffic': 0.30,  # Modifier ici
        'green': 0.30     # Modifier ici
    }
```

### Ajuster les Bornes de Normalisation

Ligne ~145 :

```python
NORMALIZATION_BOUNDS = {
    'traffic_nuisance': (0, 5000),  # Modifier selon contexte
    'green_surface': (0, 500000),   # Modifier selon contexte
    'no2': (0, 100),                # Modifier selon limites locales
    # ...
}
```

### Ajouter des Polluants

Dans la méthode `calculate_air_index()`, ligne ~400 :

```python
def calculate_air_index(self, air: AirQualityData) -> float:
    # Ajouter O3, SO2, CO, etc.
    scores = [no2_norm, pm25_norm, pm10_norm, o3_norm, ...]
    air_score = np.mean(scores)
    return air_score
```

---

## 🐛 Dépannage

### Erreur : "Aucune base de données trouvée"

**Solution** : Vérifier que le dossier `app/databases/` contient des fichiers `.db`

```bash
ls -la app/databases/
```

### Erreur : "Module not found"

**Solution** : Installer les dépendances manquantes

```bash
pip install numpy pandas matplotlib seaborn scipy scikit-learn
```

### Scores tous identiques

**Solution** : Vérifier les bornes de normalisation (peut-être trop larges/étroites)

---

## 📞 Support

Pour toute question ou amélioration, consulter :
- 📄 Le code source commenté
- 📊 Les rapports générés
- 📚 Les références bibliographiques

---

## ✅ Checklist Avant Utilisation

- [ ] Environnement virtuel activé
- [ ] Dépendances installées
- [ ] Bases de données disponibles dans `app/databases/`
- [ ] Permissions d'écriture dans le dossier
- [ ] Python 3.8+ installé

---

## 🎓 Pour votre Rapport de Thèse

### À Inclure dans "Méthodes"
1. ✅ Formulation mathématique complète
2. ✅ Justification des pondérations par la littérature
3. ✅ Processus de normalisation Min-Max
4. ✅ Tableau de synthèse des indicateurs

### À Inclure dans "Résultats"
1. ✅ Statistiques descriptives (moyenne, écart-type, distribution)
2. ✅ Comparaison de scénarios (meilleur vs pire)
3. ✅ Visualisations (graphiques en barres, radar, histogrammes)

### À Inclure dans "Discussion"
1. ✅ Analyse de sensibilité
2. ✅ Limites (multicolinéarité, subjectivité, linéarité)
3. ✅ Recommandations pour amélioration future

### À Inclure dans "Validation"
1. ✅ Tests de robustesse
2. ✅ Cohérence interne (corrélations)
3. ✅ Capacité discriminante
4. ✅ Comportement avec valeurs extrêmes

---

**Bonne chance avec votre thèse ! 🎓📊**
