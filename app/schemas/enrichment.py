from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class LeadershipInfo(BaseModel):
    """Schema for leadership information."""

    name: str
    title: str
    source: str


class ContactInfo(BaseModel):
    """Schema for contact information."""

    type: str  # email, phone, address
    value: str
    source: str


class RecentNews(BaseModel):
    """Schema for recent news/grants."""

    type: str
    description: str
    source: str


class ApolloContact(BaseModel):
    """Schema for Apollo contact data."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None


class ApolloCompanyData(BaseModel):
    """Schema for Apollo company data."""

    name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    revenue: Optional[str] = None
    founded_year: Optional[int] = None
    headquarters_address: Optional[str] = None
    description: Optional[str] = None


class EnrichmentResponse(BaseModel):
    """Response schema for enrichment data."""

    enrichment_id: int
    organization_id: int
    status: str
    last_enriched: Optional[datetime] = None
    website_url: Optional[str] = None
    website_scraped: bool
    apollo_searched: bool
    apollo_enriched: bool
    leadership_info: List[LeadershipInfo] = []
    contact_info: List[ContactInfo] = []
    recent_news: List[RecentNews] = []
    apollo_company_data: Optional[ApolloCompanyData] = None
    apollo_contacts: List[ApolloContact] = []
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EnrichmentStatus(BaseModel):
    """Schema for enrichment status."""

    status: str
    organization_id: int
    enrichment_id: Optional[int] = None
    message: Optional[str] = None


class EnrichmentTriggerRequest(BaseModel):
    """Schema for triggering enrichment."""

    force_refresh: bool = False
    include_website_scraping: bool = True
    include_apollo_enrichment: bool = True


class EnrichmentSummary(BaseModel):
    """Schema for enrichment summary statistics."""

    total_enriched: int
    website_scraped: int
    apollo_searched: int
    apollo_enriched: int
    failed: int
    pending: int
    in_progress: int
