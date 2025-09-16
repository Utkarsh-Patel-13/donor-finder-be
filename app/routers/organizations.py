from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.database import get_db
from app.services.database_service import DatabaseService
from app.schemas.organization import Organization, OrganizationWithFilings

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/", response_model=List[Organization])
async def search_organizations(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Search query for organization name"),
    state: Optional[str] = Query(None, description="State code (e.g., 'NY', 'CA')"),
    subseccd: Optional[int] = Query(None, description="501(c) subsection code"),
    limit: int = Query(50, le=100, description="Maximum number of results"),
):
    """Search organizations with optional filters."""
    db_service = DatabaseService(db)
    organizations = db_service.search_organizations(
        query=q, state=state, subseccd=subseccd, limit=limit
    )
    return organizations


@router.get("/{ein}", response_model=OrganizationWithFilings)
async def get_organization_details(ein: int, db: Session = Depends(get_db)):
    """Get organization details by EIN including filings."""
    db_service = DatabaseService(db)
    organization = db_service.get_organization_with_filings(ein)

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    return organization
