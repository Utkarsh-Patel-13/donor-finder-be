from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List
from app.models.database import get_db
from app.models.organization import Organization
from app.models.enrichment import OrganizationEnrichment
from app.services.enrichment_service import EnrichmentService
from app.schemas.enrichment import (
    EnrichmentResponse,
    EnrichmentStatus,
    EnrichmentTriggerRequest,
    EnrichmentSummary,
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enrichment", tags=["enrichment"])


@router.post("/organization/{ein}", response_model=EnrichmentStatus)
async def enrich_organization_by_ein(
    ein: int,
    request: EnrichmentTriggerRequest = EnrichmentTriggerRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """
    Enrich organization data using EIN (Employer Identification Number).

    This endpoint will:
    1. Search for the organization using Apollo.io search API
    2. Enrich organization data using Apollo.io enrichment API
    3. Scrape the organization's website (from Apollo or fallback) using Firecrawl
    4. Store all enriched data for future reference

    - **ein**: The organization's EIN (Employer Identification Number)
    - **force_refresh**: Whether to re-enrich even if data already exists
    - **include_website_scraping**: Whether to scrape website data
    - **include_apollo_enrichment**: Whether to use Apollo.io enrichment
    """
    # Find organization by EIN
    organization = db.query(Organization).filter(Organization.ein == ein).first()

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Create enrichment service
    enrichment_service = EnrichmentService(db)

    try:
        # Run enrichment using the organization ID
        result = await enrichment_service.enrich_organization(
            organization_id=organization.id, force_refresh=request.force_refresh
        )

        if result.get("success"):
            return EnrichmentStatus(
                status=result.get("status", "completed"),
                organization_id=organization.id,
                enrichment_id=result.get("enrichment_id"),
                message="Enrichment completed successfully"
                if result.get("status") == "completed"
                else result.get("message", "Enrichment in progress"),
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Enrichment failed: {result.get('error', 'Unknown error')}",
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enrichment error: {str(e)}")
    finally:
        await enrichment_service.close()


@router.get("/organization/{ein}", response_model=EnrichmentResponse)
async def get_organization_enrichment(ein: int, db: Session = Depends(get_db)):
    """
    Get enriched data for a specific organization by EIN.

    Returns comprehensive enrichment data including:
    - Apollo.io organization search and enrichment results
    - Leadership information scraped from website
    - Contact details (emails, phones, addresses)
    - Recent news, grants, or announcements
    - Apollo.io company and contact data
    """
    # Find organization by EIN
    organization = db.query(Organization).filter(Organization.ein == ein).first()

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Get enrichment data
    enrichment_service = EnrichmentService(db)
    enriched_data = enrichment_service.get_enriched_data(organization.id)

    if not enriched_data:
        raise HTTPException(
            status_code=404,
            detail="No enrichment data found for this organization. Try enriching it first.",
        )

    return EnrichmentResponse(**enriched_data)
