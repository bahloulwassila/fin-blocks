import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.ledger.models import Account, Entry, Transaction
from app.ledger.schemas import AccountCreate, EntryIn, TransactionCreate

# Comptes dont le solde augmente avec un debit.
# Les autres (passif, capitaux propres, revenus) augmentent avec un credit.
DEBIT_NORMAL = {"asset", "expense"}
FLIP = {"debit": "credit", "credit": "debit"}


# ---------- Comptes ----------


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


# ---------- Transactions ----------


def request_fingerprint(data: TransactionCreate) -> str:
    """Empreinte du contenu de la requete, pour detecter une cle reutilisee."""
    payload = json.dumps(data.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def get_transaction(db: Session, transaction_id: int) -> Transaction:
    tx = db.scalar(
        select(Transaction)
        .options(selectinload(Transaction.entries))
        .where(Transaction.id == transaction_id)
    )
    if tx is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    return tx


def find_by_key(db: Session, key: str) -> Transaction | None:
    return db.scalar(
        select(Transaction)
        .options(selectinload(Transaction.entries))
        .where(Transaction.idempotency_key == key)
    )


def check_replay(existing: Transaction, fingerprint: str) -> Transaction:
    if existing.request_hash != fingerprint:
        raise HTTPException(
            status_code=409,
            detail="idempotency key already used with a different request",
        )
    return existing


def validate_entries(db: Session, data: TransactionCreate) -> None:
    debits = sum(e.amount_cents for e in data.entries if e.direction == "debit")
    credits = sum(e.amount_cents for e in data.entries if e.direction == "credit")
    if debits != credits:
        raise HTTPException(
            status_code=422,
            detail=f"unbalanced transaction: debits {debits} != credits {credits}",
        )

    account_ids = {e.account_id for e in data.entries}
    accounts = db.scalars(select(Account).where(Account.id.in_(account_ids))).all()

    missing = account_ids - {a.id for a in accounts}
    if missing:
        raise HTTPException(
            status_code=422, detail=f"unknown accounts: {sorted(missing)}"
        )

    inactive = sorted(a.id for a in accounts if not a.is_active)
    if inactive:
        raise HTTPException(status_code=422, detail=f"inactive accounts: {inactive}")

    if len({a.currency for a in accounts}) > 1:
        raise HTTPException(
            status_code=422, detail="all entries must use the same currency"
        )


def create_transaction(
    db: Session, data: TransactionCreate, key: str
) -> tuple[Transaction, bool]:
    """Renvoie (transaction, creee_maintenant)."""
    fingerprint = request_fingerprint(data)

    # 1. Cle deja vue : on renvoie l'existante (ou 409 si le contenu differe).
    existing = find_by_key(db, key)
    if existing is not None:
        return check_replay(existing, fingerprint), False

    # 2. Regles metier.
    validate_entries(db, data)

    # 3. Transaction + ecritures en un seul commit : tout ou rien.
    tx = Transaction(
        description=data.description,
        occurred_at=data.occurred_at,
        idempotency_key=key,
        request_hash=fingerprint,
        entries=[
            Entry(
                account_id=e.account_id,
                direction=e.direction,
                amount_cents=e.amount_cents,
            )
            for e in data.entries
        ],
    )
    db.add(tx)
    try:
        db.commit()
    except IntegrityError:
        # Deux requetes simultanees avec la meme cle : la base a refuse la seconde.
        db.rollback()
        existing = find_by_key(db, key)
        if existing is None:
            raise
        return check_replay(existing, fingerprint), False

    return get_transaction(db, tx.id), True


def reverse_transaction(db: Session, transaction_id: int) -> tuple[Transaction, bool]:
    original = get_transaction(db, transaction_id)
    key = f"reversal-of-{original.id}"

    already = find_by_key(db, key)
    if already is not None:
        return already, False

    data = TransactionCreate(
        description=f"Reversal of #{original.id}: {original.description}"[:255],
        occurred_at=datetime.now(UTC),
        entries=[
            EntryIn(
                account_id=e.account_id,
                direction=FLIP[e.direction],
                amount_cents=e.amount_cents,
            )
            for e in original.entries
        ],
    )
    return create_transaction(db, data, key)


def list_transactions(
    db: Session, account_id: int | None, limit: int, offset: int
) -> list[Transaction]:
    query = select(Transaction).options(selectinload(Transaction.entries))
    if account_id is not None:
        query = query.where(
            Transaction.id.in_(
                select(Entry.transaction_id).where(Entry.account_id == account_id)
            )
        )
    query = query.order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
    return list(db.scalars(query.limit(limit).offset(offset)).all())
