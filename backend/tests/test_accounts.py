def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_create_account(client):
    r = client.post(
        "/accounts",
        json={"code": "1000", "name": "Banque", "type": "asset", "currency": "CAD"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["code"] == "1000"
    assert data["is_active"] is True


def test_duplicate_code_is_rejected(client, accounts):
    r = client.post(
        "/accounts",
        json={"code": "1000", "name": "Autre", "type": "asset", "currency": "CAD"},
    )
    assert r.status_code == 409


def test_unknown_account_type_is_rejected(client):
    r = client.post(
        "/accounts",
        json={"code": "3000", "name": "Test", "type": "banane", "currency": "CAD"},
    )
    assert r.status_code == 422


def test_lowercase_currency_is_rejected(client):
    r = client.post(
        "/accounts",
        json={"code": "3001", "name": "Test", "type": "asset", "currency": "cad"},
    )
    assert r.status_code == 422


def test_new_account_has_zero_balance(client, accounts):
    r = client.get(f"/accounts/{accounts['bank']}/balance")
    assert r.status_code == 200
    assert r.json()["balance"] == "0.00"


def test_unknown_account_returns_404(client):
    assert client.get("/accounts/999").status_code == 404
