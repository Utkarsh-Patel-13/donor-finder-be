from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from .database import Base


class Organization(Base):
    """Organization model based on ProPublica API structure."""

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    ein = Column(
        Integer, unique=True, index=True, nullable=False
    )  # Employer Identification Number
    strein = Column(String(12), index=True)  # EIN in XX-XXXXXXX format
    name = Column(String(500), index=True)
    sub_name = Column(String(500))
    address = Column(String(500))
    city = Column(String(100))
    state = Column(String(2), index=True)
    zipcode = Column(String(15))
    subseccd = Column(Integer, index=True)  # 501(c)(X) code
    ntee_code = Column(String(10))  # NTEE classification code
    guidestar_url = Column(Text)
    nccs_url = Column(Text)

    # Searchable text and embedding
    searchable_text = Column(Text)  # Expanded text for embedding
    embedding = Column(Vector(384))  # 384-dimensional embedding (all-MiniLM-L6-v2)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    irs_updated = Column(DateTime(timezone=True))  # From API 'updated' field

    # Relationship to filings
    filings = relationship(
        "Filing", back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Organization(ein={self.ein}, name='{self.name}')>"
