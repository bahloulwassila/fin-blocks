import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Def de l'adresse de la base (var d'environnement + valeur par defaut)
# Connexion a postgres (databricks env)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://fin:fin@localhost:5432/fin_blocks",
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


# Classe mere pr les futures tables
class Base(DeclarativeBase):
    pass


# Permet de preter une session à l'API
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
