from sqlalchemy import Column, Integer, DateTime, Text, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Filing(Base):
    """Filing model for Form 990 data from ProPublica API."""

    __tablename__ = "filings"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign key to organization
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)

    # Core filing identifiers
    ein = Column(Integer, index=True, nullable=False)
    tax_prd = Column(Integer, index=True)  # YYYYMM format
    tax_prd_yr = Column(Integer, index=True)  # Year only
    formtype = Column(Integer)  # 0=990, 1=990-EZ, 2=990-PF
    pdf_url = Column(Text)

    # Basic financial data (convenience fields from API)
    totrevenue = Column(Numeric(precision=15, scale=2))  # Total revenue
    totfuncexpns = Column(Numeric(precision=15, scale=2))  # Total functional expenses
    totassetsend = Column(Numeric(precision=15, scale=2))  # Total assets, end of year
    totliabend = Column(
        Numeric(precision=15, scale=2)
    )  # Total liabilities, end of year
    pct_compnsatncurrofcr = Column(
        Numeric(precision=8, scale=6)
    )  # Compensation percentage

    # Additional financial fields (store as JSON or individual columns as needed)
    # Note: Full 990 data contains 40-120 additional fields depending on form type
    raw_data = Column(Text)  # Store complete API response as JSON

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    irs_updated = Column(DateTime(timezone=True))  # From API 'updated' field

    # Relationship back to organization
    organization = relationship("Organization", back_populates="filings")

    def __repr__(self):
        return (
            f"<Filing(ein={self.ein}, tax_period={self.tax_prd}, form={self.formtype})>"
        )
