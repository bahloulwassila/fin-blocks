"""Les regles tiennent meme en SQL direct, sans passer par l'API."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import engine


# Test A
def test_db_rejects_unbalanced_transaction(accounts):
    with pytest.raises(IntegrityError, match="unbalanced"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO transactions "
                    "(description, occurred_at, idempotency_key, request_hash) "
                    "VALUES ('sql', now(), 'sql-1', 'x')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO entries "
                    "(transaction_id, account_id, direction, amount_cents) "
                    "VALUES (currval('transactions_id_seq'), :acc, 'debit', 500)"
                ),
                {"acc": accounts["bank"]},
            )
    # Le rollback a tout annule : rien n'est reste en base.
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM transactions")) == 0


# Test B
@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE entries SET amount_cents = 1",
        "DELETE FROM entries",
        "UPDATE transactions SET description = 'modifie'",
        "DELETE FROM transactions",
    ],
)
def test_ledger_is_immutable(client, accounts, sql):
    client.post(
        "/transactions",
        headers={"Idempotency-Key": "depot-0001"},
        json={
            "description": "Dépôt",
            "occurred_at": "2026-11-09T10:00:00-05:00",
            "entries": [
                {
                    "account_id": accounts["bank"],
                    "direction": "debit",
                    "amount_cents": 100,
                },
                {
                    "account_id": accounts["deposits"],
                    "direction": "credit",
                    "amount_cents": 100,
                },
            ],
        },
    )
    with pytest.raises(IntegrityError, match="immutable"):
        with engine.begin() as conn:
            conn.execute(text(sql))


def test_db_rejects_unknown_account_type():
    with pytest.raises(IntegrityError, match="ck_account_type"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO accounts (code, name, type, currency) "
                    "VALUES ('X1', 'Test', 'banane', 'CAD')"
                )
            )


def test_db_rejects_non_positive_amount(accounts):
    with pytest.raises(IntegrityError, match="ck_entry_amount_positive"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO transactions "
                    "(description, occurred_at, idempotency_key, request_hash) "
                    "VALUES ('sql', now(), 'sql-2', 'x')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO entries "
                    "(transaction_id, account_id, direction, amount_cents) "
                    "VALUES (currval('transactions_id_seq'), :acc, 'debit', 0)"
                ),
                {"acc": accounts["bank"]},
            )
