#!/usr/bin/env python3
"""
Script to sync filings for organizations already in the database.

This script:
1. Fetches organizations from the database (optionally filtered)
2. For each organization, calls ProPublica API to get detailed data including filings
3. Updates the filings table with the latest filing data
4. Handles rate limiting and error recovery
"""

import asyncio
import sys
import logging
from typing import List, Dict, Optional
from datetime import datetime

# Add the app directory to Python path
sys.path.append("/Users/utkarshpatel/Projects/df/donor_finder_backend")

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.database import SessionLocal, get_settings
from app.models.organization import Organization
from app.models.filing import Filing
from app.schemas.filing import FilingCreate
from app.services.propublica_api import ProPublicaAPIService
from app.services.database_service import DatabaseService

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 50  # Process organizations in batches
API_DELAY = 0.5  # Delay between API calls to respect rate limits


class FilingSyncService:
    """Service for syncing organization filings from ProPublica API."""

    def __init__(self):
        self.settings = get_settings()
        self.db = SessionLocal()
        self.propublica_service = ProPublicaAPIService()
        self.db_service = DatabaseService(self.db)

        self.stats = {
            "organizations_processed": 0,
            "organizations_updated": 0,
            "filings_created": 0,
            "filings_updated": 0,
            "errors": 0,
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def cleanup(self):
        """Clean up resources."""
        try:
            await self.propublica_service.client.aclose()
            self.db.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def get_organizations_to_sync(
        self,
        state: Optional[str] = None,
        has_enrichment: bool = True,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Organization]:
        """Get organizations from database that need filing sync."""
        query = self.db.query(Organization)

        # Filter by state if specified
        if state:
            query = query.filter(Organization.state == state)

        # Filter by enrichment status if specified
        if has_enrichment:
            from app.models.enrichment import OrganizationEnrichment

            query = query.join(OrganizationEnrichment).filter(
                OrganizationEnrichment.apollo_enriched == True
            )

        # Add ordering for consistent results
        query = query.order_by(Organization.id)

        # Apply limit and offset
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        return query.all()

    def get_filing_stats_for_org(self, organization: Organization) -> Dict:
        """Get current filing statistics for an organization."""
        filing_count = (
            self.db.query(Filing)
            .filter(Filing.organization_id == organization.id)
            .count()
        )

        latest_filing = (
            self.db.query(Filing)
            .filter(Filing.organization_id == organization.id)
            .order_by(Filing.tax_prd_yr.desc())
            .first()
        )

        return {
            "filing_count": filing_count,
            "latest_year": latest_filing.tax_prd_yr if latest_filing else None,
        }

    async def sync_organization_filings(self, organization: Organization) -> Dict:
        """Sync filings for a single organization."""
        try:
            logger.info(
                f"Syncing filings for {organization.name} (EIN: {organization.ein})"
            )

            # Get current filing stats
            current_stats = self.get_filing_stats_for_org(organization)
            logger.debug(
                f"Current filings: {current_stats['filing_count']}, "
                f"Latest year: {current_stats['latest_year']}"
            )

            # Fetch detailed organization data from ProPublica API
            api_response = await self.propublica_service.get_organization_details(
                organization.ein
            )

            # Add delay to respect API rate limits
            await asyncio.sleep(API_DELAY)

            if not api_response.get("organization"):
                logger.warning(f"No organization data found for EIN {organization.ein}")
                return {
                    "success": False,
                    "error": "No organization data found in API",
                    "filings_processed": 0,
                }

            # Process filings if available
            filings_created = 0
            filings_updated = 0

            if api_response.get("filings_with_data"):
                for filing_data in api_response["filings_with_data"]:
                    try:
                        # Parse filing data
                        filing_parsed = self.propublica_service.parse_filing_data(
                            filing_data, organization.id
                        )
                        filing_create = FilingCreate(**filing_parsed)

                        # Check if filing already exists
                        existing_filing = (
                            self.db.query(Filing)
                            .filter(
                                Filing.ein == filing_create.ein,
                                Filing.tax_prd == filing_create.tax_prd,
                            )
                            .first()
                        )

                        if existing_filing:
                            # Update existing filing
                            for key, value in filing_create.dict(
                                exclude_unset=True
                            ).items():
                                if key != "organization_id":  # Don't update org ID
                                    setattr(existing_filing, key, value)
                            filings_updated += 1
                            logger.debug(
                                f"Updated filing for {organization.ein}, tax period {filing_create.tax_prd}"
                            )
                        else:
                            # Create new filing
                            self.db_service.create_filing(filing_create)
                            filings_created += 1
                            logger.debug(
                                f"Created filing for {organization.ein}, tax period {filing_create.tax_prd}"
                            )

                    except Exception as e:
                        logger.error(
                            f"Error processing filing for {organization.ein}: {e}"
                        )
                        continue

                # Commit all filing changes for this organization
                self.db.commit()

            # Get updated stats
            updated_stats = self.get_filing_stats_for_org(organization)

            logger.info(
                f"✅ Synced {organization.name}: "
                f"{filings_created} new, {filings_updated} updated filings. "
                f"Total: {updated_stats['filing_count']} filings"
            )

            return {
                "success": True,
                "filings_created": filings_created,
                "filings_updated": filings_updated,
                "total_filings": updated_stats["filing_count"],
                "latest_year": updated_stats["latest_year"],
            }

        except Exception as e:
            logger.error(f"Error syncing filings for {organization.name}: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e),
                "filings_processed": 0,
            }

    async def sync_batch(self, organizations: List[Organization]):
        """Sync filings for a batch of organizations."""
        logger.info(f"Processing batch of {len(organizations)} organizations...")

        for i, org in enumerate(organizations):
            logger.info(
                f"[{i + 1}/{len(organizations)}] Processing {org.name} (EIN: {org.ein})"
            )

            result = await self.sync_organization_filings(org)

            # Update statistics
            self.stats["organizations_processed"] += 1
            if result["success"]:
                self.stats["organizations_updated"] += 1
                self.stats["filings_created"] += result.get("filings_created", 0)
                self.stats["filings_updated"] += result.get("filings_updated", 0)
            else:
                self.stats["errors"] += 1

            # Log progress
            if (i + 1) % 10 == 0:
                logger.info(
                    f"Progress: {i + 1}/{len(organizations)} organizations processed"
                )

    async def run(
        self,
        state: Optional[str] = None,
        has_enrichment: bool = True,
        limit: Optional[int] = None,
        batch_size: int = BATCH_SIZE,
    ):
        """Main execution method."""
        logger.info("Starting organization filing sync...")

        if state:
            logger.info(f"Filtering by state: {state}")
        if has_enrichment:
            logger.info("Only syncing organizations with Apollo enrichment")
        if limit:
            logger.info(f"Processing maximum {limit} organizations")

        try:
            offset = 0
            total_processed = 0

            while True:
                # Get batch of organizations
                organizations = self.get_organizations_to_sync(
                    state=state,
                    has_enrichment=has_enrichment,
                    limit=batch_size,
                    offset=offset,
                )

                if not organizations:
                    logger.info("No more organizations to process")
                    break

                # Check if we've reached the limit
                if limit and total_processed + len(organizations) > limit:
                    organizations = organizations[: limit - total_processed]

                # Process the batch
                await self.sync_batch(organizations)

                total_processed += len(organizations)
                offset += batch_size

                logger.info(
                    f"Batch completed. Total processed: {total_processed} organizations"
                )

                # Check if we've reached the limit
                if limit and total_processed >= limit:
                    break

            # Final summary
            logger.info("✅ Filing sync completed!")
            logger.info(
                f"Organizations processed: {self.stats['organizations_processed']}"
            )
            logger.info(f"Organizations updated: {self.stats['organizations_updated']}")
            logger.info(f"New filings created: {self.stats['filings_created']}")
            logger.info(f"Existing filings updated: {self.stats['filings_updated']}")
            logger.info(f"Errors encountered: {self.stats['errors']}")

            if self.stats["errors"] > 0:
                logger.warning(
                    f"⚠️  {self.stats['errors']} organizations had errors during sync"
                )

        except Exception as e:
            logger.error(f"Filing sync failed with error: {e}")
            raise


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync organization filings from ProPublica API"
    )
    parser.add_argument(
        "--state", type=str, help="Filter by state code (e.g., 'CA', 'NY')"
    )
    parser.add_argument(
        "--no-enrichment",
        action="store_true",
        help="Include organizations without Apollo enrichment",
    )
    parser.add_argument(
        "--limit", type=int, help="Maximum number of organizations to process"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Number of organizations to process per batch (default: {BATCH_SIZE})",
    )

    args = parser.parse_args()

    async with FilingSyncService() as sync_service:
        await sync_service.run(
            state=args.state,
            has_enrichment=not args.no_enrichment,
            limit=args.limit,
            batch_size=args.batch_size,
        )


if __name__ == "__main__":
    asyncio.run(main())
