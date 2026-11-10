- Re-test après correction : INSERT 'banane' refusé par ck_account_type,
  INSERT valide en SQL direct → is_active = true

  ### [Qualité] Exception trop large dans /health
- Détecté par : ruff (règle BLE001)
- Problème : except Exception masquerait aussi les bugs de programmation
- Correction : except SQLAlchemyError, seules les erreurs de base renvoient 503
- Note : règle B008 désactivée dans pyproject.toml (faux positif propre à FastAPI)

### [Ledger] Débits = crédits garanti par Postgres, ledger immuable
- Risque : une transaction déséquilibrée ou une écriture modifiée via SQL direct
- Protection : constraint trigger différé (vérifié au COMMIT) + triggers BEFORE UPDATE/DELETE
- Test A : INSERT d'une seule écriture de 500 en SQL → COMMIT refusé, 0 ligne restante
- Test B : UPDATE et DELETE sur le ledger → refusés ("use a reversal")
- Test C : transaction équilibrée via l'API → 201, l'API n'est pas affectée

### [Ledger] Tests manuels de l'API (12 scénarios)
| # | Scénario | Attendu | Obtenu |
|---|----------|---------|--------|
| 1 | Dépôt de 100 $ | 201 | 201 |
| 2 | Soldes Banque / Dépôts | 100.00 / 100.00 | 500, puis 100.00 / 100.00 après correction |
| 3 | Même requête, même clé | 200, pas de doublon | 200, solde inchangé |
| 4 | Même clé, autre montant | 409 | 409 |
| 5 | Débits ≠ crédits | 422 | 422 |
| 6 | Une seule écriture | 422 | 422 |
| 7 | Montant nul | 422 | 422 |
| 8 | Compte inconnu | 422 | 422 |
| 9 | Date sans fuseau | 422 | 422 |
| 10 | CAD et EUR mélangés | 422 | 422 |
| 11 | Inversion | 201, soldes à 0.00 | 201, 0.00 / 0.00 |
| 12 | Deuxième inversion | 200, même id | 200, id 3 |

cd ~/fin-blocks
git add .
git commit -m "Ledger: database-enforced balance and immutability"
git push

### [Tests] Suite automatique pytest : 29 tests
- Base de test dédiée (port 5433), vidée avant chaque test (TRUNCATE, qui ne
  déclenche pas les triggers d'immutabilité)
- Couvre : les 12 scénarios manuels, les règles en base (tests A/B), les
  contraintes CHECK, l'absence de clé d'idempotence, les 404
- Le test des soldes sert aussi de non-régression pour le bug Decimal
- Résultat : 29 passed en ~1 s
- Warning starlette (httpx → httpx2) masqué de façon ciblée dans pyproject.toml :
  il vient de la bibliothèque, pas de notre code ; migration à prévoir avec FastAPI