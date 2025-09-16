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


@router.post("/organization/{organization_id}", response_model=EnrichmentStatus)
async def enrich_organization(
    organization_id: int,
    request: EnrichmentTriggerRequest = EnrichmentTriggerRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """
    Enrich organization data using external sources (Apollo.io + Firecrawl).

    This endpoint will:
    1. Search for the organization using Apollo.io search API
    2. Enrich organization data using Apollo.io enrichment API
    3. Scrape the organization's website (from Apollo or fallback) using Firecrawl
    4. Store all enriched data for future reference

    - **organization_id**: The organization ID to enrich
    - **force_refresh**: Whether to re-enrich even if data already exists
    - **include_website_scraping**: Whether to scrape website data
    - **include_apollo_enrichment**: Whether to use Apollo.io enrichment
    """
    # Verify organization exists
    organization = (
        db.query(Organization).filter(Organization.id == organization_id).first()
    )

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Create enrichment service
    enrichment_service = EnrichmentService(db)

    try:
        # Run enrichment (async operation)
        result = await enrichment_service.enrich_organization(
            organization_id=organization_id, force_refresh=request.force_refresh
        )

        if result.get("success"):
            return EnrichmentStatus(
                status=result.get("status", "completed"),
                organization_id=organization_id,
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


@router.post("/organization/ein/{ein}", response_model=EnrichmentStatus)
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
        # Run enrichment (async operation) using the organization ID
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


@router.get("/organization/ein/{ein}", response_model=EnrichmentResponse)
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


@router.get("/organization/ein/{ein}/status", response_model=EnrichmentStatus)
async def get_enrichment_status(ein: int, db: Session = Depends(get_db)):
    """Get the current enrichment status for an organization by EIN."""
    # Find organization by EIN
    organization = db.query(Organization).filter(Organization.ein == ein).first()

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    enrichment = (
        db.query(OrganizationEnrichment)
        .filter(OrganizationEnrichment.organization_id == organization.id)
        .first()
    )

    if not enrichment:
        return EnrichmentStatus(
            status="not_enriched",
            organization_id=organization.id,
            message="Organization has not been enriched yet",
        )

    return EnrichmentStatus(
        status=enrichment.enrichment_status,
        organization_id=organization.id,
        enrichment_id=enrichment.id,
        message=enrichment.error_message
        if enrichment.enrichment_status == "failed"
        else None,
    )


@router.delete("/organization/ein/{ein}")
async def delete_organization_enrichment(ein: int, db: Session = Depends(get_db)):
    """Delete enrichment data for an organization by EIN."""
    # Find organization by EIN
    organization = db.query(Organization).filter(Organization.ein == ein).first()

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    enrichment = (
        db.query(OrganizationEnrichment)
        .filter(OrganizationEnrichment.organization_id == organization.id)
        .first()
    )

    if not enrichment:
        raise HTTPException(
            status_code=404, detail="No enrichment data found for this organization"
        )

    db.delete(enrichment)
    db.commit()

    return {
        "message": "Enrichment data deleted successfully",
        "organization_id": organization.id,
        "ein": ein,
    }


@router.get("/stats", response_model=EnrichmentSummary)
async def get_enrichment_stats(db: Session = Depends(get_db)):
    """Get enrichment statistics across all organizations."""
    total_enriched = db.query(OrganizationEnrichment).count()

    website_scraped = (
        db.query(OrganizationEnrichment)
        .filter(OrganizationEnrichment.website_scraped)
        .count()
    )

    apollo_searched = (
        db.query(OrganizationEnrichment)
        .filter(OrganizationEnrichment.apollo_searched)
        .count()
    )

    apollo_enriched = (
        db.query(OrganizationEnrichment)
        .filter(OrganizationEnrichment.apollo_enriched)
        .count()
    )

    failed = (
        db.query(OrganizationEnrichment)
        .filter(OrganizationEnrichment.enrichment_status == "failed")
        .count()
    )

    pending = (
        db.query(OrganizationEnrichment)
        .filter(OrganizationEnrichment.enrichment_status == "pending")
        .count()
    )

    in_progress = (
        db.query(OrganizationEnrichment)
        .filter(OrganizationEnrichment.enrichment_status == "in_progress")
        .count()
    )

    return EnrichmentSummary(
        total_enriched=total_enriched,
        website_scraped=website_scraped,
        apollo_searched=apollo_searched,
        apollo_enriched=apollo_enriched,
        failed=failed,
        pending=pending,
        in_progress=in_progress,
    )


@router.get("/recent", response_model=List[EnrichmentResponse])
async def get_recent_enrichments(
    limit: int = Query(10, le=50, description="Maximum number of results"),
    db: Session = Depends(get_db),
):
    """Get recently enriched organizations."""
    recent_enrichments = (
        db.query(OrganizationEnrichment)
        .filter(OrganizationEnrichment.enrichment_status == "completed")
        .order_by(OrganizationEnrichment.last_enriched_at.desc())
        .limit(limit)
        .all()
    )

    enrichment_service = EnrichmentService(db)
    results = []

    for enrichment in recent_enrichments:
        enriched_data = enrichment_service.get_enriched_data(enrichment.organization_id)
        if enriched_data:
            results.append(EnrichmentResponse(**enriched_data))

    return results


@router.post("/bulk-enrich")
async def bulk_enrich_organizations(
    organization_ids: List[int],
    background_tasks: BackgroundTasks,
    force_refresh: bool = Query(
        False, description="Force refresh existing enrichments"
    ),
    db: Session = Depends(get_db),
):
    """
    Enrich multiple organizations in bulk.

    This endpoint queues enrichment jobs for multiple organizations.
    Check individual organization status using /enrichment/organization/{id}/status
    """
    if len(organization_ids) > 50:
        raise HTTPException(
            status_code=400, detail="Cannot enrich more than 50 organizations at once"
        )

    # Verify all organizations exist
    existing_orgs = (
        db.query(Organization.id).filter(Organization.id.in_(organization_ids)).all()
    )
    existing_ids = [org.id for org in existing_orgs]

    missing_ids = set(organization_ids) - set(existing_ids)
    if missing_ids:
        raise HTTPException(
            status_code=404, detail=f"Organizations not found: {list(missing_ids)}"
        )

    # Queue enrichment tasks
    async def bulk_enrichment_task():
        enrichment_service = EnrichmentService(db)
        try:
            for org_id in organization_ids:
                try:
                    await enrichment_service.enrich_organization(
                        organization_id=org_id, force_refresh=force_refresh
                    )
                except Exception as e:
                    logger.error(f"Failed to enrich organization {org_id}: {e}")
        finally:
            await enrichment_service.close()

    background_tasks.add_task(bulk_enrichment_task)

    return {
        "message": f"Bulk enrichment started for {len(organization_ids)} organizations",
        "organization_ids": organization_ids,
        "status": "queued",
    }
