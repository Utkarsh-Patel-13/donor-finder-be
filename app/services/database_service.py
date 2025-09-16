from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text, func
from typing import List, Optional, Dict, Tuple
from app.models.organization import Organization
from app.models.filing import Filing
from app.schemas.organization import OrganizationCreate
from app.schemas.filing import FilingCreate
from app.services.ntee_service import NTEEService
from app.services.embedding_service import get_embedding_service
import logging

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for database operations."""

    def __init__(self, db: Session):
        self.db = db
        self.ntee_service = NTEEService()
        self.embedding_service = get_embedding_service()

    def create_organization(self, org_data: OrganizationCreate) -> Organization:
        """Create or update organization in database with embeddings."""
        # Check if organization exists
        existing_org = (
            self.db.query(Organization).filter(Organization.ein == org_data.ein).first()
        )

        # Build searchable text and generate embedding
        org_dict = org_data.dict()
        searchable_text = self.ntee_service.build_searchable_text(org_dict)
        embedding = self.embedding_service.generate_embedding(searchable_text)

        if existing_org:
            # Update existing organization
            for key, value in org_data.dict(exclude_unset=True).items():
                setattr(existing_org, key, value)

            # Update searchable text and embedding
            existing_org.searchable_text = searchable_text
            existing_org.embedding = embedding

            self.db.commit()
            self.db.refresh(existing_org)
            return existing_org
        else:
            # Create new organization
            org_dict_with_embedding = org_data.dict()
            org_dict_with_embedding["searchable_text"] = searchable_text
            org_dict_with_embedding["embedding"] = embedding

            db_org = Organization(**org_dict_with_embedding)
            self.db.add(db_org)
            self.db.commit()
            self.db.refresh(db_org)
            return db_org

    def create_filing(self, filing_data: FilingCreate) -> Filing:
        """Create or update filing in database."""
        # Check if filing exists (unique combination of ein + tax_prd)
        existing_filing = (
            self.db.query(Filing)
            .filter(
                Filing.ein == filing_data.ein, Filing.tax_prd == filing_data.tax_prd
            )
            .first()
        )

        if existing_filing:
            # Update existing filing
            for key, value in filing_data.dict(exclude_unset=True).items():
                setattr(existing_filing, key, value)
            self.db.commit()
            self.db.refresh(existing_filing)
            return existing_filing
        else:
            # Create new filing
            db_filing = Filing(**filing_data.dict())
            self.db.add(db_filing)
            self.db.commit()
            self.db.refresh(db_filing)
            return db_filing

    def get_organization_by_ein(self, ein: int) -> Optional[Organization]:
        """Get organization by EIN."""
        return self.db.query(Organization).filter(Organization.ein == ein).first()

    def search_organizations(
        self,
        query: Optional[str] = None,
        state: Optional[str] = None,
        subseccd: Optional[int] = None,
        limit: int = 50,
    ) -> List[Organization]:
        """Search organizations with filters."""
        db_query = self.db.query(Organization)

        if query:
            db_query = db_query.filter(Organization.name.ilike(f"%{query}%"))
        if state:
            db_query = db_query.filter(Organization.state == state)
        if subseccd:
            db_query = db_query.filter(Organization.subseccd == subseccd)

        return db_query.limit(limit).all()

    def get_organization_with_filings(self, ein: int) -> Optional[Organization]:
        """Get organization with all its filings."""
        return self.db.query(Organization).filter(Organization.ein == ein).first()

    def get_recent_filings(self, limit: int = 10) -> List[Filing]:
        """Get most recent filings."""
        return (
            self.db.query(Filing).order_by(Filing.tax_prd_yr.desc()).limit(limit).all()
        )

    def semantic_search_organizations(
        self,
        query: str,
        state: Optional[str] = None,
        subseccd: Optional[int] = None,
        ntee_codes: Optional[List[str]] = None,
        limit: int = 20,
        similarity_threshold: float = 0.1,
    ) -> List[Tuple[Organization, float]]:
        """Perform semantic search on organizations with optional filters."""

        # Generate query embedding
        query_embedding = self.embedding_service.generate_embedding(query)

        # Build base query
        db_query = self.db.query(Organization).filter(
            Organization.embedding.isnot(None)
        )

        # Apply filters
        if state:
            db_query = db_query.filter(Organization.state == state.upper())
        if subseccd:
            db_query = db_query.filter(Organization.subseccd == subseccd)
        if ntee_codes:
            db_query = db_query.filter(Organization.ntee_code.in_(ntee_codes))

        # Get all candidates (we'll filter by similarity after)
        candidates = db_query.limit(1000).all()

        if not candidates:
            return []

        # Compute similarities
        results = []
        for org in candidates:
            if org.embedding is not None:
                similarity = self.embedding_service.compute_similarity(
                    query_embedding, org.embedding
                )
                if similarity >= similarity_threshold:
                    results.append((org, similarity))

        # Sort by similarity (descending) and limit results
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def hybrid_search_organizations(
        self,
        query: str,
        state: Optional[str] = None,
        subseccd: Optional[int] = None,
        limit: int = 20,
    ) -> List[Tuple[Organization, float, str]]:
        """Perform hybrid search combining semantic and traditional search."""

        # Parse query for components
        query_components = self.ntee_service.extract_query_components(query)

        semantic_results = self.semantic_search_organizations(
            query=query,
            state=state
            or (
                query_components["geographic"][0]
                if query_components["geographic"]
                else None
            ),
            subseccd=subseccd,
            ntee_codes=None,
            limit=limit,
        )

        # Get traditional keyword search results
        keyword_results = self.search_organizations(
            query=query,
            state=state
            or (
                query_components["geographic"][0]
                if query_components["geographic"]
                else None
            ),
            subseccd=subseccd,
            limit=limit,
        )

        # Combine and deduplicate results
        combined_results = {}

        # Add semantic results with "semantic" match type
        for org, similarity in semantic_results:
            combined_results[org.ein] = (
                org,
                similarity * 0.8,
                "semantic",
            )  # Weight semantic results

        # Add keyword results with "keyword" match type, boost if already exists
        for org in keyword_results:
            if org.ein in combined_results:
                # Boost existing semantic result
                existing_org, existing_score, _ = combined_results[org.ein]
                combined_results[org.ein] = (
                    existing_org,
                    existing_score + 0.3,
                    "hybrid",
                )
            else:
                # Add as keyword-only result
                combined_results[org.ein] = (org, 0.5, "keyword")

        # Sort by combined score and return
        final_results = list(combined_results.values())
        final_results.sort(key=lambda x: x[1], reverse=True)

        return final_results[:limit]

    def update_organization_embedding(self, ein: int) -> bool:
        """Update embedding for a specific organization."""
        try:
            org = self.get_organization_by_ein(ein)
            if not org:
                return False

            # Rebuild searchable text and embedding
            org_dict = {
                "name": org.name,
                "sub_name": org.sub_name,
                "ntee_code": org.ntee_code,
                "subseccd": org.subseccd,
                "city": org.city,
                "state": org.state,
            }

            searchable_text = self.ntee_service.build_searchable_text(org_dict)
            embedding = self.embedding_service.generate_embedding(searchable_text)

            # Update database
            org.searchable_text = searchable_text
            org.embedding = embedding

            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to update embedding for EIN {ein}: {e}")
            self.db.rollback()
            return False

    def get_organizations_without_embeddings(
        self, limit: int = 100
    ) -> List[Organization]:
        """Get organizations that don't have embeddings yet."""
        return (
            self.db.query(Organization)
            .filter(Organization.embedding.is_(None))
            .limit(limit)
            .all()
        )

    def batch_update_embeddings(self, batch_size: int = 50) -> Dict[str, int]:
        """Update embeddings for organizations that don't have them."""
        stats = {"updated": 0, "errors": 0}

        orgs_without_embeddings = self.get_organizations_without_embeddings(batch_size)

        if not orgs_without_embeddings:
            return stats

        # Prepare texts for batch embedding generation
        org_texts = []
        for org in orgs_without_embeddings:
            org_dict = {
                "name": org.name,
                "sub_name": org.sub_name,
                "ntee_code": org.ntee_code,
                "subseccd": org.subseccd,
                "city": org.city,
                "state": org.state,
            }
            searchable_text = self.ntee_service.build_searchable_text(org_dict)
            org_texts.append(searchable_text)

        # Generate embeddings in batch
        try:
            embeddings = self.embedding_service.generate_embeddings_batch(org_texts)

            # Update organizations
            for org, text, embedding in zip(
                orgs_without_embeddings, org_texts, embeddings
            ):
                try:
                    org.searchable_text = text
                    org.embedding = embedding
                    stats["updated"] += 1
                except Exception as e:
                    logger.error(f"Failed to update org {org.ein}: {e}")
                    stats["errors"] += 1

            self.db.commit()

        except Exception as e:
            logger.error(f"Failed batch embedding generation: {e}")
            self.db.rollback()
            stats["errors"] = len(orgs_without_embeddings)

        return stats
