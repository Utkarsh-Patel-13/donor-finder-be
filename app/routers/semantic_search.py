from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.database import get_db
from app.services.database_service import DatabaseService
from app.services.ntee_service import NTEEService
from app.schemas.organization import OrganizationSearchResult
from pydantic import BaseModel

router = APIRouter(prefix="/semantic-search", tags=["semantic search"])


class SearchResponse(BaseModel):
    """Response model for search results."""

    results: List[OrganizationSearchResult]
    total_results: int
    query: str
    query_components: dict
    search_type: str


class EmbeddingUpdateResponse(BaseModel):
    """Response model for embedding updates."""

    updated: int
    errors: int
    message: str


@router.get("/", response_model=SearchResponse)
async def semantic_search_organizations(
    db: Session = Depends(get_db),
    q: str = Query(..., description="Natural language search query"),
    state: Optional[str] = Query(
        None, description="Filter by state (e.g., 'NY', 'CA')"
    ),
    subseccd: Optional[int] = Query(
        None, description="Filter by 501(c) subsection code"
    ),
    search_type: str = Query(
        "hybrid", description="Search type: 'semantic', 'keyword', or 'hybrid'"
    ),
    limit: int = Query(20, le=50, description="Maximum number of results"),
):
    """
    Perform semantic search on organizations using natural language queries.

    Examples:
    - "foundations supporting early childhood education in California"
    - "disaster relief nonprofits"
    - "youth development programs"
    """
    db_service = DatabaseService(db)
    ntee_service = NTEEService()

    # Extract query components for response metadata
    query_components = ntee_service.extract_query_components(q)

    try:
        if search_type == "semantic":
            # Pure semantic search
            results = db_service.semantic_search_organizations(
                query=q, state=state, subseccd=subseccd, limit=limit
            )
            # Convert to search result format
            search_results = []
            for org, score in results:
                search_result = OrganizationSearchResult(
                    **org.__dict__, relevance_score=score, match_type="semantic"
                )
                search_results.append(search_result)

        elif search_type == "keyword":
            # Traditional keyword search
            orgs = db_service.search_organizations(
                query=q, state=state, subseccd=subseccd, limit=limit
            )
            # Convert to search result format
            search_results = []
            for org in orgs:
                search_result = OrganizationSearchResult(
                    **org.__dict__,
                    relevance_score=0.7,  # Fixed score for keyword matches
                    match_type="keyword",
                )
                search_results.append(search_result)

        else:  # hybrid
            # Hybrid search combining semantic and keyword
            results = db_service.hybrid_search_organizations(
                query=q, state=state, subseccd=subseccd, limit=limit
            )
            # Convert to search result format
            search_results = []
            for org, score, match_type in results:
                search_result = OrganizationSearchResult(
                    **org.__dict__, relevance_score=score, match_type=match_type
                )
                search_results.append(search_result)

        return SearchResponse(
            results=search_results,
            total_results=len(search_results),
            query=q,
            query_components=query_components,
            search_type=search_type,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/update-embeddings", response_model=EmbeddingUpdateResponse)
async def update_embeddings(
    db: Session = Depends(get_db),
    batch_size: int = Query(
        50, le=200, description="Number of organizations to process"
    ),
):
    """Update embeddings for organizations that don't have them."""
    db_service = DatabaseService(db)

    try:
        stats = db_service.batch_update_embeddings(batch_size=batch_size)

        message = f"Successfully updated {stats['updated']} embeddings"
        if stats["errors"] > 0:
            message += f", {stats['errors']} errors occurred"

        return EmbeddingUpdateResponse(
            updated=stats["updated"], errors=stats["errors"], message=message
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Embedding update failed: {str(e)}"
        )
