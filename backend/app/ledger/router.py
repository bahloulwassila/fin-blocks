from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.ledger import service
from app.ledger.models import Account
from app.ledger.schemas import AccountCreate, AccountOut, BalanceOut

router = APIRouter(prefix="/accounts", tags=["accounts"])


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
