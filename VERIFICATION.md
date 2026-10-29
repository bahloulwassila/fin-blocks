- Re-test après correction : INSERT 'banane' refusé par ck_account_type,
  INSERT valide en SQL direct → is_active = true

  ### [Qualité] Exception trop large dans /health
- Détecté par : ruff (règle BLE001)
- Problème : except Exception masquerait aussi les bugs de programmation
- Correction : except SQLAlchemyError, seules les erreurs de base renvoient 503
- Note : règle B008 désactivée dans pyproject.toml (faux positif propre à FastAPI)