from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AccountType = Literal["asset", "liability", "equity", "revenue", "expense"]


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
