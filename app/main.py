from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.database import engine, get_db
from app.models.organization import Organization
from app.models.filing import Filing
from app.routers import organizations, sync, semantic_search
from app.services.database_service import DatabaseService
from app.schemas.filing import Filing as FilingSchema
from typing import List
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Organization.metadata.create_all(bind=engine)
Filing.metadata.create_all(bind=engine)

# Initialize pgvector extension
try:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
        logger.info("pgvector extension initialized")
except Exception as e:
    logger.warning(f"Could not initialize pgvector extension: {e}")

app = FastAPI(
    title="Donor Finder API",
    description="API for finding and managing nonprofit donor/foundation data with semantic search",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(organizations.router, prefix="/api/v1")
app.include_router(sync.router, prefix="/api/v1")
app.include_router(semantic_search.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Donor Finder API with Semantic Search",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "search_organizations": "/api/v1/organizations/",
            "get_organization": "/api/v1/organizations/{ein}",
            "sync_organization": "/api/v1/sync/organization/{ein}",
            "bulk_sync": "/api/v1/sync/search-and-sync",
            "semantic_search": "/api/v1/semantic-search/",
            "search_suggestions": "/api/v1/semantic-search/suggest",
            "update_embeddings": "/api/v1/semantic-search/update-embeddings",
            "explain_query": "/api/v1/semantic-search/explain",
        },
        "examples": {
            "semantic_search": [
                "foundations supporting early childhood education in California",
                "environmental organizations in New York",
                "disaster relief nonprofits",
                "youth development programs in Texas",
            ]
        },
    }


@app.get("/api/v1/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        db_service = DatabaseService(db)
        # Simple database connectivity check
        db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/api/v1/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get database statistics."""
    db_service = DatabaseService(db)

    org_count = db.query(Organization).count()
    filing_count = db.query(Filing).count()

    # Get stats by state
    state_stats = (
        db.query(Organization.state, db.func.count(Organization.id))
        .filter(Organization.state.isnot(None))
        .group_by(Organization.state)
        .all()
    )

    return {
        "total_organizations": org_count,
        "total_filings": filing_count,
        "organizations_by_state": {state: count for state, count in state_stats},
    }


@app.get("/api/v1/recent-filings", response_model=List[FilingSchema])
async def get_recent_filings(limit: int = 10, db: Session = Depends(get_db)):
    """Get most recent filings."""
    db_service = DatabaseService(db)
    filings = db_service.get_recent_filings(limit=limit)
    return filings


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
