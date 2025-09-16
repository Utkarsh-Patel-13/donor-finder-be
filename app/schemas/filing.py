from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal


class FilingBase(BaseModel):
    """Base schema for filing data."""

    ein: int
    tax_prd: Optional[int] = None
    tax_prd_yr: Optional[int] = None
    formtype: Optional[int] = None
    pdf_url: Optional[str] = None
    totrevenue: Optional[Decimal] = None
    totfuncexpns: Optional[Decimal] = None
    totassetsend: Optional[Decimal] = None
    totliabend: Optional[Decimal] = None
    pct_compnsatncurrofcr: Optional[Decimal] = None
    raw_data: Optional[str] = None


class FilingCreate(FilingBase):
    """Schema for creating new filing."""

    organization_id: int
    irs_updated: Optional[datetime] = None


class Filing(FilingBase):
    """Full filing schema with database fields."""

    id: int
    organization_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    irs_updated: Optional[datetime] = None

    class Config:
        from_attributes = True
