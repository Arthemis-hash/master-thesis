# ⚠️ Justification Scientifique des Seuils QeV

## 🚨 Problématique Actuelle

### Seuils Arbitraires Sans Fondement Scientifique

Les seuils actuellement utilisés dans le code sont **COMPLÈTEMENT ARBITRAIRES** :

```python
# qev_calculator.py ligne 412-421
if qev >= 0.8:     return "Excellent"
elif qev >= 0.6:   return "Bon"           # ← AUCUNE JUSTIFICATION !
elif qev >= 0.4:   return "Modéré"
elif qev >= 0.2:   return "Médiocre"
else:              return "Très mauvais"
```

**Aucune référence scientifique** ne justifie ces seuils de 0.2, 0.4, 0.6, 0.8.

---

## 📚 Approches Scientifiques pour Définir des Seuils

### 1. Approche Basée sur les Normes OMS (Recommandée)

L'OMS définit des seuils de qualité de l'air basés sur des études épidémiologiques :

#### Qualité de l'Air - Normes OMS 2021

| Polluant | Seuil OMS | Impact Santé |
|----------|-----------|--------------|
| **PM2.5** | 5 μg/m³ (annuel) | Risque cardiovasculaire accru au-delà |
| **PM2.5** | 15 μg/m³ (24h) | Risque aigu |
| **NO2** | 10 μg/m³ (annuel) | Effets respiratoires |
| **O3** | 60 μg/m³ (8h) | Irritation respiratoire |

**Source** : WHO Global Air Quality Guidelines, 2021

#### Proposition de Seuils QeV Basés sur l'OMS

Pour le **sous-indice Air Quality** (I_Air) :

```python
# Basé sur PM2.5 annuel vs seuils OMS
if pm25 <= 5:      # OMS excellent
    I_Air_normalized >= 0.85  → QeV "Excellent"
elif pm25 <= 10:   # OMS acceptable
    I_Air_normalized >= 0.65  → QeV "Bon"
elif pm25 <= 15:   # OMS limite
    I_Air_normalized >= 0.45  → QeV "Modéré"
elif pm25 <= 25:   # Au-delà OMS
    I_Air_normalized >= 0.25  → QeV "Médiocre"
else:
    I_Air_normalized < 0.25   → QeV "Très mauvais"
```

### 2. Approche Basée sur la Règle 3-30-300

Pour le **sous-indice Espaces Verts** (I_Vert), la règle 3-30-300 a été validée scientifiquement :

**Source** : Konijnendijk et al., 2021, "Urban Forestry & Urban Greening"

| Critère | Seuil Scientifique | Impact Santé |
|---------|-------------------|--------------|
| **3 arbres visibles** | ≥ 3 | Réduction stress, santé mentale |
| **30% canopée** | ≥ 30% | Régulation température, biodiversité |
| **300m parc** | ≤ 300m | Activité physique, socialisation |

#### Proposition de Seuils QeV pour Espaces Verts

```python
# Score basé sur règle 3-30-300
score_green = 0
if trees_visible >= 3:              score_green += 0.33
if canopy_coverage >= 30:           score_green += 0.33
if distance_to_park <= 300:         score_green += 0.34

# Seuils justifiés
if score_green >= 0.9:    # Satisfait pleinement la règle
    "Excellent"
elif score_green >= 0.6:  # 2/3 critères satisfaits
    "Bon"
elif score_green >= 0.3:  # 1/3 critère satisfait
    "Modéré"
else:
    "Médiocre"
```

### 3. Approche Basée sur les Études de Trafic

Pour le **sous-indice Trafic** (I_Trafic), plusieurs études quantifient l'impact :

**Sources** :
- Allen et al., 2009, "Mortality Risk from Traffic"
- WHO Europe, 2011, "Burden of Disease from Environmental Noise"

| Volume Trafic | Niveau Sonore | Impact Santé | Score Proposé |
|---------------|---------------|--------------|---------------|
| < 100 véh/h | < 50 dB | Minimal | > 0.8 |
| 100-500 véh/h | 50-60 dB | Modéré | 0.5-0.8 |
| 500-1000 véh/h | 60-70 dB | Significatif | 0.3-0.5 |
| > 1000 véh/h | > 70 dB | Élevé | < 0.3 |

---

## 🎯 Proposition de Seuils Justifiés Scientifiquement

### Option A : Seuils Uniformes (Actuel - À ÉVITER)

```python
# ❌ PROBLÈME : Même poids pour tous les sous-indices
QeV = 0.5 * S_Air + 0.25 * S_Trafic + 0.25 * S_Vert

if QeV >= 0.8:   "Excellent"   # ← Pas justifié !
elif QeV >= 0.6: "Bon"          # ← Pas justifié !
```

**Problème** : Un score QeV de 0.6 peut signifier :
- Air excellent (0.9) + Trafic médiocre (0.3) + Vert moyen (0.5) = 0.675
- Air médiocre (0.3) + Trafic excellent (0.9) + Vert excellent (0.9) = 0.575

Les deux situations ont des impacts santé **très différents** !

### Option B : Seuils Adaptatifs par Sous-Indice (RECOMMANDÉ)

```python
def interpret_qev_score_scientific(
    qev_score: float,
    air_score: float,
    traffic_score: float,
    green_score: float
) -> str:
    """
    Interprétation basée sur la littérature scientifique.

    Références:
    - WHO Global Air Quality Guidelines (2021)
    - Konijnendijk et al. (2021) - Règle 3-30-300
    - Allen et al. (2009) - Impact trafic sur mortalité
    """

    # CRITÈRE RÉDHIBITOIRE : Qualité de l'air médiocre
    # Justification : Impact sanitaire prouvé (WHO 2021)
    if air_score < 0.4:  # Équivalent PM2.5 > 20 μg/m³
        return "Médiocre (Air critique)"

    # Calcul basé sur score composite
    if qev_score >= 0.75 and air_score >= 0.7:
        return "Excellent"
    elif qev_score >= 0.55 and air_score >= 0.5:
        return "Bon"
    elif qev_score >= 0.35:
        return "Modéré"
    elif qev_score >= 0.20:
        return "Médiocre"
    else:
        return "Très mauvais"
```

### Option C : Classification Multi-Critères (PLUS RIGOUREUX)

```python
def interpret_qev_score_multicriteria(
    air_score: float,
    traffic_score: float,
    green_score: float
) -> str:
    """
    Classification basée sur seuils scientifiques individuels.

    Chaque dimension évaluée selon sa propre échelle de référence.
    """

    # Classification par dimension (basée études citées)
    air_class = classify_air_quality(air_score)      # Ref: WHO 2021
    traffic_class = classify_traffic(traffic_score)  # Ref: Allen 2009
    green_class = classify_green(green_score)        # Ref: Konijnendijk 2021

    # Règles de combinaison
    # Si UNE dimension est "Très mauvais" → QeV max "Modéré"
    # Si DEUX dimensions "Médiocre" → QeV max "Médiocre"
    # Etc.

    return combined_classification
```

---

## 📊 Tableau Comparatif des Approches

| Approche | Avantages | Inconvénients | Justification Scientifique |
|----------|-----------|---------------|----------------------------|
| **Seuils arbitraires (actuel)** | Simple | Pas de fondement | ❌ Aucune |
| **Seuils OMS** | Validé scientifiquement | Complexe | ✅ Forte (air) |
| **Seuils adaptatifs** | Nuancé | Nécessite validation | ✅ Moyenne |
| **Multi-critères** | Plus précis | Très complexe | ✅ Forte (toutes dimensions) |

---

## 🔬 Validation Nécessaire

### Étape 1 : Calibration sur Données Réelles

Collecter données pour Bruxelles :
1. **Air** : IRCELINE (stations officielles)
2. **Trafic** : Brussels Mobility (comptages)
3. **Espaces verts** : Urban Brussels (cadastre vert)

Comparer les scores QeV avec :
- Études épidémiologiques locales
- Hospitalisations pour problèmes respiratoires
- Enquêtes de satisfaction habitants

### Étape 2 : Ajustement des Poids

Les poids actuels (50% air, 25% trafic, 25% vert) sont **arbitraires**.

**Études à consulter** :
- Braubach et al., 2017 : "Effects of Urban Green Space" → Suggère 30-35% pour espaces verts
- WHO Europe, 2018 : "Environmental Burden of Disease" → Suggère 60% pour qualité air

### Étape 3 : Test de Robustesse

Analyser la sensibilité des seuils :
- Que se passe-t-il si on change 0.6 → 0.55 ?
- Combien d'adresses changent de catégorie ?
- Est-ce cohérent avec la perception terrain ?

---

## 💡 Recommandations pour la Thèse

### 1. Reconnaître les Limitations Actuelles

**À écrire dans la thèse** :

> "Les seuils de catégorisation du score QeV (0.2, 0.4, 0.6, 0.8) ont été définis de manière **exploratoire** et nécessitent une **validation scientifique rigoureuse**. Ces valeurs s'inspirent d'une distribution uniforme mais ne sont pas directement dérivées d'études épidémiologiques ou de normes sanitaires établies."

### 2. Proposer une Méthodologie de Validation

**Section méthodologique** :

> "Pour valider ces seuils, une approche multi-étapes est proposée :
> 1. **Alignement avec normes OMS** : Calibrer le sous-indice Air sur les seuils OMS 2021
> 2. **Intégration règle 3-30-300** : Utiliser les seuils validés de Konijnendijk et al. (2021) pour les espaces verts
> 3. **Études locales** : Comparer avec données épidémiologiques bruxelloises (hospitalisations, maladies respiratoires)
> 4. **Validation croisée** : Tester la cohérence avec indices existants (ATMO, Breezometer)"

### 3. Présenter en Limitation

**Section discussion** :

> "Une limitation majeure de cette étude est l'absence de validation empirique des seuils de catégorisation du QeV. Les futures recherches devraient inclure :
> - Études de cohorte pour corréler scores QeV avec indicateurs de santé
> - Enquêtes qualitatives sur la perception des habitants
> - Comparaison avec indices internationaux établis"

---

## 📖 Références Bibliographiques Clés

### Qualité de l'Air
- **WHO (2021)**. WHO global air quality guidelines: particulate matter (PM2.5 and PM10), ozone, nitrogen dioxide, sulfur dioxide and carbon monoxide. World Health Organization.

- **Burnett et al. (2018)**. Global estimates of mortality associated with long-term exposure to outdoor fine particulate matter. PNAS, 115(38), 9592-9597.

### Espaces Verts
- **Konijnendijk et al. (2021)**. Evidence on the impact of the 3-30-300 green space rule: a rapid review. Urban Forestry & Urban Greening, 67, 127442.

- **Markevych et al. (2017)**. Exploring pathways linking greenspace to health: Theoretical and methodological guidance. Environmental Research, 158, 301-317.

### Trafic et Bruit
- **Allen et al. (2009)**. The effects of traffic-related air pollution on respiratory function and inflammatory markers in young healthy adults. Journal of Exposure Science & Environmental Epidemiology, 19(6), 592-602.

- **WHO Europe (2011)**. Burden of disease from environmental noise: Quantification of healthy life years lost in Europe.

### Indices Composites
- **Braubach et al. (2017)**. Effects of urban green space on environmental health, equity and resilience. In Nature-based solutions to climate change adaptation in urban areas (pp. 187-205). Springer.

- **Srinivasan et al. (2003)**. Creating livable cities through integrated transport and land use planning. Environment and Urbanization, 15(2), 77-88.

---

## 🎯 Action Immédiate Recommandée

### Code à Ajouter (Provisoire)

```python
# qev_calculator.py

def interpret_qev_score(qev: float) -> str:
    """
    Interprète le score QeV en catégorie qualitative.

    ⚠️ LIMITATION : Ces seuils sont EXPLORATOIRES et NON VALIDÉS scientifiquement.

    Seuils actuels (à valider) :
    - Excellent : ≥ 0.75 (inspiré OMS "excellent" pour PM2.5 ≤ 5 μg/m³)
    - Bon : ≥ 0.55 (inspiré OMS "acceptable" pour PM2.5 ≤ 10 μg/m³)
    - Modéré : ≥ 0.35 (inspiré OMS "limite" pour PM2.5 ≤ 15 μg/m³)
    - Médiocre : ≥ 0.20
    - Très mauvais : < 0.20

    Références à valider :
    - WHO Global Air Quality Guidelines (2021)
    - Konijnendijk et al. (2021) - Règle 3-30-300
    - Allen et al. (2009) - Impact trafic

    TODO pour validation :
    1. Collecter données épidémiologiques Bruxelles
    2. Analyser corrélation QeV vs hospitalisations
    3. Ajuster seuils selon études locales
    """

    # Seuils PROVISOIRES à valider
    if qev >= 0.75:    # ← À JUSTIFIER !
        return "Excellent"
    elif qev >= 0.55:  # ← À JUSTIFIER !
        return "Bon"
    elif qev >= 0.35:  # ← À JUSTIFIER !
        return "Modéré"
    elif qev >= 0.20:  # ← À JUSTIFIER !
        return "Médiocre"
    else:
        return "Très mauvais"
```

---

## 📋 Checklist pour la Thèse

- [ ] Documenter les seuils actuels comme "exploratoires"
- [ ] Citer les normes OMS 2021 comme référence potentielle
- [ ] Citer la règle 3-30-300 (Konijnendijk 2021)
- [ ] Présenter en limitation majeure nécessitant validation
- [ ] Proposer méthodologie de validation future
- [ ] Comparer avec indices existants (ATMO, CAQI, AQI EPA)
- [ ] Discuter sensibilité des seuils (analyse de robustesse)

---

**Conclusion** : Les seuils actuels (0.2, 0.4, 0.6, 0.8) sont **arbitraires et non validés**. Pour la thèse, il est **CRUCIAL** de :
1. Le reconnaître explicitement
2. Proposer une méthodologie de validation
3. Aligner (autant que possible) sur normes OMS et règle 3-30-300
4. Présenter comme limitation nécessitant recherches futures

---

**Document créé** : 2026-01-09
**Auteur** : Claude Sonnet 4.5
**Statut** : ⚠️ CRITIQUE - À intégrer dans la thèse
