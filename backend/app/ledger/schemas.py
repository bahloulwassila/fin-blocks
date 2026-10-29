from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

AccountType = Literal["asset", "liability", "equity", "revenue", "expense"]
Direction = Literal["debit", "credit"]


class AccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    type: AccountType
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    type: AccountType
    currency: str
    is_active: bool
    created_at: datetime


class BalanceOut(BaseModel):
    account_id: int
    currency: str
    balance_cents: int
    balance: str


class EntryIn(BaseModel):
    account_id: int
    direction: Direction
    amount_cents: int = Field(gt=0, le=10**15)


class TransactionCreate(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    occurred_at: AwareDatetime
    entries: list[EntryIn] = Field(min_length=2)


class EntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    direction: Direction
    amount_cents: int


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    occurred_at: datetime
    idempotency_key: str
    created_at: datetime
    entries: list[EntryOut]
