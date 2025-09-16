from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from app.models.database import get_db
from app.services.propublica_api import ProPublicaAPIService
from app.services.database_service import DatabaseService
from app.schemas.organization import OrganizationCreate
from app.schemas.filing import FilingCreate

router = APIRouter(prefix="/sync", tags=["synchronization"])


@router.post("/organization/{ein}")
async def sync_organization(
    ein: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """Sync organization data from ProPublica API."""
    api_service = ProPublicaAPIService()
    db_service = DatabaseService(db)

    try:
        # Fetch organization details from API
        api_response = await api_service.get_organization_details(ein)

        if not api_response.get("organization"):
            raise HTTPException(status_code=404, detail="Organization not found in API")

        # Parse organization data
        org_data = api_service.parse_organization_data(api_response["organization"])
        org_create = OrganizationCreate(**org_data)

        # Save organization to database
        db_org = db_service.create_organization(org_create)

        # Process filings if available
        filings_count = 0
        if api_response.get("filings_with_data"):
            for filing_data in api_response["filings_with_data"]:
                filing_parsed = api_service.parse_filing_data(filing_data, db_org.id)
                filing_create = FilingCreate(**filing_parsed)
                db_service.create_filing(filing_create)
                filings_count += 1

        return {
            "status": "success",
            "organization_id": db_org.id,
            "ein": ein,
            "filings_synced": filings_count,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
    finally:
        await api_service.close()


@router.post("/search-and-sync")
async def search_and_sync_organizations(
    background_tasks: BackgroundTasks,
    q: Optional[str] = None,
    state: Optional[str] = None,
    c_code: Optional[int] = 3,  # Default to 501(c)(3)
    max_orgs: int = 10,
    db: Session = Depends(get_db),
):
    """Search and sync multiple organizations."""
    api_service = ProPublicaAPIService()
    db_service = DatabaseService(db)

    try:
        # Search organizations
        search_results = await api_service.search_organizations(
            query=q, state=state, c_code=c_code, page=0
        )

        if not search_results.get("organizations"):
            return {"status": "no_results", "synced_count": 0}

        synced_count = 0
        errors = []

        # Sync each organization (limited by max_orgs)
        for org in search_results["organizations"][:max_orgs]:
            try:
                ein = org.get("ein")
                if not ein:
                    continue

                # Get detailed data for organization
                org_details = await api_service.get_organization_details(ein)

                if org_details.get("organization"):
                    # Parse and save organization
                    org_data = api_service.parse_organization_data(
                        org_details["organization"]
                    )
                    org_create = OrganizationCreate(**org_data)
                    db_org = db_service.create_organization(org_create)

                    # Process filings
                    if org_details.get("filings_with_data"):
                        for filing_data in org_details["filings_with_data"]:
                            filing_parsed = api_service.parse_filing_data(
                                filing_data, db_org.id
                            )
                            filing_create = FilingCreate(**filing_parsed)
                            db_service.create_filing(filing_create)

                    synced_count += 1

            except Exception as e:
                errors.append(f"EIN {ein}: {str(e)}")

        return {
            "status": "completed",
            "synced_count": synced_count,
            "errors": errors,
            "total_found": len(search_results["organizations"]),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk sync failed: {str(e)}")
    finally:
        await api_service.close()
