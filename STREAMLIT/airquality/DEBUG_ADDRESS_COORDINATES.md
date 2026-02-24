# 🐛 Débogage: Problème de Coordonnées d'Adresse sur la Carte

## Problème Rapporté

Lorsque vous changez d'adresse dans l'application, **la carte affiche toujours les mêmes coordonnées** même si les données téléchargées sont bien différentes pour chaque adresse.

## Diagnostic

Le problème vient probablement de l'un de ces points:

1. **Normalisation inconsistante des adresses** - Plusieurs adresses différentes sont normalisées au même format
2. **Coordonnées incorrectes dans la base** - Les coordonnées stockées dans PostgreSQL sont les mêmes pour plusieurs adresses
3. **Cache ou state Streamlit** - Les coordonnées sont mises en cache quelque part

## Logs de Débogage Ajoutés

Nous avons ajouté des logs détaillés dans:

### 1. `db_utils_postgres.py` - `get_location_data()`
```
🔍 get_location_data - Recherche adresse:
   Input address: '...'
   Normalized: '...'
   self.current_address: '...'
✅ Adresse trouvée: ID=..., coords=(lat, lon)
```

### 2. `db_async_wrapper.py` - `get_location_summary()`
```
📊 get_location_summary pour '...':
   Adresse recherchée: '...'
   Adresse normalisée: '...'
   Coordonnées du DataFrame: lat=..., lon=...
   Nombre de lignes dans DataFrame: ...
```

### 3. `air_quality_map.py` - `create_location_map()`
```
🗺️ Carte pour '...': lat=..., lon=...
   Adresse normalisée: '...'
   Total enregistrements: ...
```

## Comment Déboguer

### Étape 1: Lancer l'application avec les logs

```bash
cd /Users/macbook/Desktop/Master-Thésis/STREAMLIT/airquality/app
streamlit run app.py
```

Surveillez la console/terminal pour voir les logs.

### Étape 2: Tester avec 2 adresses différentes

1. Entrez la première adresse (ex: "Bruxelles")
2. Notez les coordonnées affichées dans les logs
3. Cliquez sur "🔄 Nouvelle analyse"
4. Entrez une deuxième adresse différente (ex: "Uccle")
5. Comparez les coordonnées dans les logs

### Étape 3: Vérifier la base de données

Connectez-vous à PostgreSQL et vérifiez les adresses stockées:

```sql
-- Voir toutes les adresses
SELECT id, "fullAddress", "normalizedAddress", latitude, longitude
FROM "Address"
ORDER BY "createdAt" DESC;

-- Compter les adresses avec les mêmes coordonnées
SELECT latitude, longitude, COUNT(*) as count
FROM "Address"
GROUP BY latitude, longitude
HAVING COUNT(*) > 1;
```

### Étape 4: Analyser les résultats

#### Cas A: Adresses normalisées identiques
Si deux adresses différentes ont le même `normalizedAddress`:
```
Adresse 1: "Bruxelles, Région de Bruxelles-Capitale, Belgique" → "1000_bruxelles"
Adresse 2: "1000 Bruxelles, BE" → "1000_bruxelles"
```

**Solution**: Les deux adresses pointent vers la même entrée dans la base. C'est le comportement attendu.

#### Cas B: Coordonnées identiques pour adresses différentes
Si plusieurs adresses ont des `normalizedAddress` différentes mais les mêmes coordonnées:
```
ID=1: normalizedAddress="1000_bruxelles", lat=50.8503, lon=4.3517
ID=2: normalizedAddress="1180_uccle", lat=50.8503, lon=4.3517  ← PROBLÈME!
```

**Solution**: Les coordonnées ont été mal enregistrées lors du téléchargement. Il faut les corriger:

```sql
-- Corriger manuellement les coordonnées
UPDATE "Address"
SET latitude = 50.7981, longitude = 4.3586
WHERE "normalizedAddress" = '1180_uccle';
```

#### Cas C: Logs montrent les bonnes coordonnées mais carte affiche les mauvaises
Si les logs montrent:
```
📊 Coordonnées du DataFrame: lat=50.7981, lon=4.3586
🗺️ Carte pour 'Uccle': lat=50.7981, lon=4.3586
```

Mais la carte affiche quand même Bruxelles (50.8503, 4.3517):

**Solution**: Problème de cache navigateur. Faire Ctrl+Shift+R pour vider le cache et recharger.

## Vérification Manuelle des Coordonnées

Pour chaque adresse, vous pouvez vérifier les coordonnées sur Google Maps:

1. Bruxelles centre: ~50.8503, 4.3517
2. Uccle: ~50.7981, 4.3586
3. Ixelles: ~50.8276, 4.3719
4. Molenbeek: ~50.8572, 4.3136

## Script de Test Python

Pour tester sans lancer Streamlit:

```python
cd /Users/macbook/Desktop/Master-Thésis/STREAMLIT/airquality/app

# Générer les bindings Prisma
cd ../../prisma
python -m prisma generate
cd ../STREAMLIT/airquality/app

# Test
python3 << 'EOF'
import asyncio
from db_utils_postgres import AirQualityDB, AddressManager

async def test_addresses():
    # Test adresse 1
    db1 = AirQualityDB(address="Bruxelles")
    df1 = await db1.get_location_data("Bruxelles")
    if not df1.empty:
        print(f"Bruxelles: lat={df1['latitude'].iloc[0]}, lon={df1['longitude'].iloc[0]}")
    else:
        print("Bruxelles: Pas de données")

    # Test adresse 2
    db2 = AirQualityDB(address="Uccle")
    df2 = await db2.get_location_data("Uccle")
    if not df2.empty:
        print(f"Uccle: lat={df2['latitude'].iloc[0]}, lon={df2['longitude'].iloc[0]}")
    else:
        print("Uccle: Pas de données")

    # Test cross-instance
    df_cross = await db1.get_location_data("Uccle")
    if not df_cross.empty:
        print(f"DB1→Uccle: lat={df_cross['latitude'].iloc[0]}, lon={df_cross['longitude'].iloc[0]}")

asyncio.run(test_addresses())
EOF
```

## Correction Possible

Si le problème persiste après vérification, la solution définitive est de s'assurer que `get_location_data()` utilise toujours l'adresse passée en paramètre plutôt que `self.current_address`.

Vérifier dans `db_utils_postgres.py` ligne 273-274:
```python
if address is None:
    address = self.current_address  # ← Utilise paramètre si fourni
```

## Checklist de Vérification

- [ ] Les logs montrent des adresses différentes entrées
- [ ] Les logs montrent des `normalizedAddress` différentes
- [ ] Les logs montrent des coordonnées différentes récupérées
- [ ] La carte affiche les bonnes coordonnées selon les logs
- [ ] Vider le cache navigateur (Ctrl+Shift+R)
- [ ] Vérifier la base PostgreSQL directement

## Contact

Si le problème persiste après ces vérifications, fournissez:
1. Les logs complets pour 2 adresses différentes
2. Le résultat de la requête SQL `SELECT * FROM "Address"`
3. Une capture d'écran de la carte affichée

---

**Dernière mise à jour**: 2026-01-09
**Version**: 1.0
