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