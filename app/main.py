from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.database import engine, get_db
from app.models.organization import Organization
from app.models.filing import Filing
from app.models.enrichment import OrganizationEnrichment
from app.routers import organizations, semantic_search, enrichment
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
OrganizationEnrichment.metadata.create_all(bind=engine)

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
    description="API for finding and managing nonprofit donor/foundation data with semantic search and enrichment",
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
app.include_router(semantic_search.router, prefix="/api/v1")
app.include_router(enrichment.router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        db_service = DatabaseService(db)
        # Simple database connectivity check
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
