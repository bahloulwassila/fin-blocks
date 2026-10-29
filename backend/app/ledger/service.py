from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ledger.models import Account, Entry
from app.ledger.schemas import AccountCreate

# Comptes dont le solde augmente avec un debit.
# Les autres (passif, capitaux propres, revenus) augmentent avec un credit.
DEBIT_NORMAL = {"asset", "expense"}


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    units, rest = divmod(abs(cents), 100)
    return f"{sign}{units}.{rest:02d}"


def create_account(db: Session, data: AccountCreate) -> Account:
    account = Account(**data.model_dump())
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="account code already exists")
    db.refresh(account)
    return account


def get_account(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    return account


def get_balance_cents(db: Session, account: Account) -> int:
    signed_amount = case(
        (Entry.direction == "debit", Entry.amount_cents),
        else_=-Entry.amount_cents,
    )
    debit_minus_credit = db.scalar(
        select(func.coalesce(func.sum(signed_amount), 0)).where(
            Entry.account_id == account.id
        )
    )
    if account.type in DEBIT_NORMAL:
        return debit_minus_credit
    return -debit_minus_credit
