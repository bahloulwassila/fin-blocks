from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.ledger import service
from app.ledger.models import Account
from app.ledger.schemas import (
    AccountCreate,
    AccountOut,
    BalanceOut,
    TransactionCreate,
    TransactionOut,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])
tx_router = APIRouter(prefix="/transactions", tags=["transactions"])


# ---------- Comptes ----------


@router.post("", response_model=AccountOut, status_code=201)
def create_account(data: AccountCreate, db: Session = Depends(get_db)):
    return service.create_account(db, data)


@router.get("", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return db.scalars(select(Account).order_by(Account.code)).all()


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: int, db: Session = Depends(get_db)):
    return service.get_account(db, account_id)


@router.get("/{account_id}/balance", response_model=BalanceOut)
def get_balance(account_id: int, db: Session = Depends(get_db)):
    account = service.get_account(db, account_id)
    cents = service.get_balance_cents(db, account)
    return BalanceOut(
        account_id=account.id,
        currency=account.currency,
        balance_cents=cents,
        balance=service.format_cents(cents),
    )


# ---------- Transactions ----------


@tx_router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(
    data: TransactionCreate,
    response: Response,
    idempotency_key: str = Header(min_length=8, max_length=64),
    db: Session = Depends(get_db),
):
    tx, created = service.create_transaction(db, data, idempotency_key)
    if not created:
        response.status_code = 200
    return TransactionOut.model_validate(tx)


@tx_router.get("", response_model=list[TransactionOut])
def list_transactions(
    account_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    txs = service.list_transactions(db, account_id, limit, offset)
    return [TransactionOut.model_validate(t) for t in txs]


@tx_router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    return TransactionOut.model_validate(service.get_transaction(db, transaction_id))


@tx_router.post(
    "/{transaction_id}/reverse", response_model=TransactionOut, status_code=201
)
def reverse_transaction(
    transaction_id: int, response: Response, db: Session = Depends(get_db)
):
    tx, created = service.reverse_transaction(db, transaction_id)
    if not created:
        response.status_code = 200
    return TransactionOut.model_validate(tx)
