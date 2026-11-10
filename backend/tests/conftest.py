import os

# Les tests utilisent TOUJOURS la base de test (port 5433), jamais celle de dev.
# Cette ligne doit passer avant tout import de l'application.
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://fin:fin@localhost:5433/fin_blocks_test",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    """Vide la base avant chaque test. TRUNCATE ne declenche pas les triggers
    d'immutabilite, contrairement a DELETE."""
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE entries, transactions, accounts RESTART IDENTITY CASCADE")
        )
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def accounts(client):
    """Cree Banque (actif) et Depots clients (passif), renvoie leurs id."""

    def create(code, name, type_, currency="CAD"):
        r = client.post(
            "/accounts",
            json={"code": code, "name": name, "type": type_, "currency": currency},
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    return {
        "bank": create("1000", "Banque", "asset"),
        "deposits": create("2000", "Dépôts clients", "liability"),
    }
