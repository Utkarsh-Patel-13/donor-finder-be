from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class OrganizationBase(BaseModel):
    """Base schema for organization data."""

    ein: int
    strein: Optional[str] = None
    name: Optional[str] = None
    sub_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipcode: Optional[str] = None
    subseccd: Optional[int] = None
    ntee_code: Optional[str] = None
    guidestar_url: Optional[str] = None
    nccs_url: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    """Schema for creating new organization."""

    irs_updated: Optional[datetime] = None


class Organization(OrganizationBase):
    """Full organization schema with database fields."""

    id: int
    searchable_text: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    irs_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrganizationWithFilings(Organization):
    """Organization with filing data included."""

    filings: List["Filing"] = []

    class Config:
        from_attributes = True


class OrganizationSearchResult(Organization):
    """Organization search result with relevance score."""

    relevance_score: float
    match_type: str  # "semantic", "keyword", or "hybrid"

    class Config:
        from_attributes = True


# Import to resolve forward reference
from .filing import Filing

OrganizationWithFilings.model_rebuild()
