import pytest


def tx_body(
    debit_account,
    credit_account,
    debit=10000,
    credit=10000,
    occurred_at="2026-11-09T10:00:00-05:00",
):
    return {
        "description": "Dépôt client",
        "occurred_at": occurred_at,
        "entries": [
            {"account_id": debit_account, "direction": "debit", "amount_cents": debit},
            {
                "account_id": credit_account,
                "direction": "credit",
                "amount_cents": credit,
            },
        ],
    }


def post_tx(client, body, key):
    return client.post("/transactions", json=body, headers={"Idempotency-Key": key})


def balance(client, account_id):
    return client.get(f"/accounts/{account_id}/balance").json()["balance"]


# Test 1
def test_balanced_deposit_is_created(client, accounts):
    r = post_tx(client, tx_body(accounts["bank"], accounts["deposits"]), "depot-0001")
    assert r.status_code == 201
    assert len(r.json()["entries"]) == 2


# Test 2 (et non-regression du bug Decimal : le solde plantait en 500)
def test_balances_follow_account_type(client, accounts):
    post_tx(client, tx_body(accounts["bank"], accounts["deposits"]), "depot-0001")
    assert balance(client, accounts["bank"]) == "100.00"  # actif : le debit augmente
    assert (
        balance(client, accounts["deposits"]) == "100.00"
    )  # passif : le credit augmente


# Test 3
def test_same_key_same_body_returns_existing(client, accounts):
    body = tx_body(accounts["bank"], accounts["deposits"])
    first = post_tx(client, body, "depot-0001")
    second = post_tx(client, body, "depot-0001")
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert balance(client, accounts["bank"]) == "100.00"  # pas de doublon


# Test 4
def test_same_key_different_body_is_conflict(client, accounts):
    post_tx(client, tx_body(accounts["bank"], accounts["deposits"]), "depot-0001")
    r = post_tx(
        client,
        tx_body(accounts["bank"], accounts["deposits"], debit=5000, credit=5000),
        "depot-0001",
    )
    assert r.status_code == 409


# Test 5
def test_unbalanced_transaction_is_rejected(client, accounts):
    r = post_tx(
        client,
        tx_body(accounts["bank"], accounts["deposits"], debit=10000, credit=9000),
        "test-desequilibre",
    )
    assert r.status_code == 422
    assert "unbalanced" in r.json()["detail"]


# Test 6
def test_single_entry_is_rejected(client, accounts):
    body = tx_body(accounts["bank"], accounts["deposits"])
    body["entries"] = body["entries"][:1]
    assert post_tx(client, body, "test-une-ecriture").status_code == 422


# Test 7 : montants nuls ET negatifs
@pytest.mark.parametrize("amount", [0, -100])
def test_non_positive_amount_is_rejected(client, accounts, amount):
    r = post_tx(
        client,
        tx_body(accounts["bank"], accounts["deposits"], debit=amount, credit=amount),
        f"test-montant-{amount}",
    )
    assert r.status_code == 422


# Test 8
def test_unknown_account_is_rejected(client, accounts):
    r = post_tx(client, tx_body(accounts["bank"], 999), "test-compte-inconnu")
    assert r.status_code == 422
    assert "unknown accounts" in r.json()["detail"]


# Test 9
def test_datetime_without_timezone_is_rejected(client, accounts):
    r = post_tx(
        client,
        tx_body(
            accounts["bank"], accounts["deposits"], occurred_at="2026-11-09T10:00:00"
        ),
        "test-sans-fuseau",
    )
    assert r.status_code == 422


# Test 10
def test_mixed_currencies_are_rejected(client, accounts):
    r = client.post(
        "/accounts",
        json={"code": "1100", "name": "Banque EUR", "type": "asset", "currency": "EUR"},
    )
    eur_id = r.json()["id"]
    r = post_tx(client, tx_body(eur_id, accounts["deposits"]), "test-devises")
    assert r.status_code == 422
    assert "currency" in r.json()["detail"]


# Test 11
def test_reversal_cancels_the_transaction(client, accounts):
    tx = post_tx(client, tx_body(accounts["bank"], accounts["deposits"]), "depot-0001")
    r = client.post(f"/transactions/{tx.json()['id']}/reverse")
    assert r.status_code == 201
    directions = {e["account_id"]: e["direction"] for e in r.json()["entries"]}
    assert directions[accounts["bank"]] == "credit"
    assert directions[accounts["deposits"]] == "debit"
    assert balance(client, accounts["bank"]) == "0.00"
    assert balance(client, accounts["deposits"]) == "0.00"


# Test 12
def test_double_reversal_is_idempotent(client, accounts):
    tx = post_tx(client, tx_body(accounts["bank"], accounts["deposits"]), "depot-0001")
    first = client.post(f"/transactions/{tx.json()['id']}/reverse")
    second = client.post(f"/transactions/{tx.json()['id']}/reverse")
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert balance(client, accounts["bank"]) == "0.00"  # et pas -100.00


# Bonus
def test_missing_idempotency_key_is_rejected(client, accounts):
    r = client.post(
        "/transactions", json=tx_body(accounts["bank"], accounts["deposits"])
    )
    assert r.status_code == 422


def test_reverse_unknown_transaction_returns_404(client):
    assert client.post("/transactions/999/reverse").status_code == 404
