from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class OrganizationEnrichment(Base):
    """Store enriched data for organizations from external sources."""

    __tablename__ = "organization_enrichments"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign key to organization
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, unique=True
    )

    # Website data from Firecrawl
    website_url = Column(String(500))
    website_content = Column(Text)  # Markdown content from website
    leadership_info = Column(JSON)  # Extracted leadership names and titles
    contact_info = Column(JSON)  # Contact information from website
    recent_news = Column(JSON)  # Recent grants/news from website

    # Apollo.io enrichment data
    apollo_company_data = Column(JSON)  # Company information from Apollo
    apollo_contacts = Column(JSON)  # Contact information from Apollo
    apollo_news_articles = Column(JSON)  # News articles from Apollo
    apollo_search_results = Column(JSON)  # Raw search results from Apollo
    apollo_enrichment_metadata = Column(JSON)  # Credits used, errors, etc.

    # Enrichment status and metadata
    website_scraped = Column(Boolean, default=False)
    apollo_searched = Column(Boolean, default=False)
    apollo_enriched = Column(Boolean, default=False)
    apollo_news_searched = Column(Boolean, default=False)
    apollo_contacts_found = Column(Boolean, default=False)
    enrichment_status = Column(
        String(50), default="pending"
    )  # pending, in_progress, completed, failed
    apollo_credits_used = Column(Integer, default=0)
    error_message = Column(Text)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_enriched_at = Column(DateTime(timezone=True))

    # Relationship back to organization
    organization = relationship("Organization", back_populates="enrichment")

    def __repr__(self):
        return f"<OrganizationEnrichment(org_id={self.organization_id}, status='{self.enrichment_status}')>"
