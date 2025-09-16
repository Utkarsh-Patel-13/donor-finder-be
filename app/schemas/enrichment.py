from pydantic import BaseModel
from typing import Optional, List, Dict, Any
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

    title: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    published_date: Optional[str] = None
    snippet: Optional[str] = None
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
    """Schema for comprehensive Apollo company data."""

    id: Optional[str] = None
    name: Optional[str] = None
    primary_domain: Optional[str] = None
    website_url: Optional[str] = None
    industry: Optional[str] = None
    estimated_num_employees: Optional[int] = None
    annual_revenue: Optional[float] = None
    founded_year: Optional[int] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    facebook_url: Optional[str] = None
    keywords: Optional[List[str]] = []
    technologies: Optional[List[str]] = []
    headquarters_address: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None


class CompanyMetrics(BaseModel):
    """Schema for extracted company metrics."""

    revenue: Optional[int] = None
    employees: Optional[int] = None
    industry: Optional[str] = None
    keywords: Optional[List[str]] = []
    technologies: Optional[List[str]] = []
    founded_year: Optional[int] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    facebook_url: Optional[str] = None


class EnrichmentResponse(BaseModel):
    """Response schema for comprehensive enrichment data."""

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
    apollo_company_data: Optional[Dict[str, Any]] = {}
    apollo_contacts: List[ApolloContact] = []
    company_metrics: Optional[CompanyMetrics] = None
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
    apollo_news_searched: int
    apollo_contacts_found: int
    failed: int
    pending: int
    in_progress: int
    total_apollo_credits_used: int
