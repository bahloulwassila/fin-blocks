from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db
from app.ledger import models  # noqa: F401
from app.ledger.router import router as accounts_router
from app.ledger.router import tx_router as transactions_router

RULES_SQL = Path(__file__).parent / "ledger" / "db_rules.sql"


def apply_database_rules() -> None:
    """Installe les triggers du ledger (idempotent : relancable sans risque)."""
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            cur.execute(RULES_SQL.read_text())
        raw.commit()
    finally:
        raw.close()


app = FastAPI(title="fin-blocks")

Base.metadata.create_all(bind=engine)
apply_database_rules()

app.include_router(accounts_router)
app.include_router(transactions_router)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ok", "database": "ok"}
