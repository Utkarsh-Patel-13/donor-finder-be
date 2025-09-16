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
    - "environmental organizations in New York"
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

        else:  # hybrid (default)
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


@router.get("/suggest")
async def get_search_suggestions(
    db: Session = Depends(get_db),
    q: str = Query(..., description="Partial query for suggestions"),
):
    """Get search suggestions based on NTEE categories and common terms."""
    ntee_service = NTEEService()

    # Extract potential components from partial query
    query_components = ntee_service.extract_query_components(q)

    suggestions = {"cause_areas": [], "geographic": [], "organization_types": []}

    # Suggest cause areas based on partial matches
    common_causes = [
        "education",
        "early childhood education",
        "health",
        "mental health",
        "environmental conservation",
        "arts and culture",
        "disaster relief",
        "youth development",
        "elderly services",
        "homeless services",
        "animal welfare",
        "civil rights",
        "community development",
    ]

    q_lower = q.lower()
    for cause in common_causes:
        if q_lower in cause or cause.startswith(q_lower):
            suggestions["cause_areas"].append(cause)

    # Suggest geographic terms
    common_states = ["California", "New York", "Texas", "Florida", "Illinois"]
    for state in common_states:
        if q_lower in state.lower() or state.lower().startswith(q_lower):
            suggestions["geographic"].append(state)

    # Suggest organization types
    org_types = ["foundation", "nonprofit", "charity", "organization"]
    for org_type in org_types:
        if q_lower in org_type or org_type.startswith(q_lower):
            suggestions["organization_types"].append(org_type)

    return suggestions


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


@router.get("/explain")
async def explain_search_query(
    q: str = Query(..., description="Query to explain"),
):
    """Explain how a search query would be processed."""
    ntee_service = NTEEService()

    # Parse query components
    components = ntee_service.extract_query_components(q)

    # Generate example searchable text
    sample_org = {
        "name": "Sample Organization",
        "ntee_code": "B21" if "education" in q.lower() else "P20",
        "subseccd": 3,
        "city": "San Francisco",
        "state": "CA",
    }

    example_searchable_text = ntee_service.build_searchable_text(sample_org)

    explanation = {
        "original_query": q,
        "detected_components": components,
        "search_strategy": {
            "semantic_matching": "Query will be converted to embedding and compared with organization embeddings",
            "geographic_filters": f"State filter: {components['geographic']}"
            if components["geographic"]
            else "No geographic filter detected",
            "cause_area_filters": f"NTEE codes: {components['cause_areas']}"
            if components["cause_areas"]
            else "No specific cause areas detected",
            "hybrid_approach": "Results will combine semantic similarity with keyword matching",
        },
        "example_organization_text": {
            "sample_org": sample_org,
            "searchable_text": example_searchable_text,
        },
        "tips": [
            "Be specific about cause areas (e.g., 'early childhood education' vs 'education')",
            "Include geographic terms (e.g., 'California', 'San Francisco Bay Area')",
            "Use descriptive terms (e.g., 'disaster relief' vs 'emergency')",
            "Try different phrasings if initial results aren't relevant",
        ],
    }

    return explanation
