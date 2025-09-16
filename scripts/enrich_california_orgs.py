#!/usr/bin/env python3
"""
Script to fetch organizations from California (and other states if needed),
enrich them with Apollo.io data, and keep only those with good enrichment.

This script:
1. Fetches 500 organizations from California
2. Enriches them using Apollo.io (search + enrichment, no Firecrawl)
3. Removes organizations with poor Apollo enrichment
4. If less than 30 good organizations, fetches from other states
5. Saves good organizations to database
"""

import asyncio
import sys
import logging
from typing import List, Dict, Optional
from datetime import datetime

# Add the app directory to Python path
sys.path.append("/Users/utkarshpatel/Projects/df/donor_finder_backend")

from sqlalchemy.orm import Session
from app.models.database import SessionLocal, get_settings
from app.models.organization import Organization
from app.models.enrichment import OrganizationEnrichment
from app.schemas.organization import OrganizationCreate
from app.services.propublica_api import ProPublicaAPIService
from app.services.apollo_service import ApolloService
from app.services.database_service import DatabaseService

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# States to try if California doesn't have enough good organizations
FALLBACK_STATES = ["NY", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI", "NJ"]
TARGET_GOOD_ORGS = 30
INITIAL_FETCH_LIMIT = 500


class OrganizationEnricher:
    """Main class for fetching and enriching organizations."""

    def __init__(self):
        self.settings = get_settings()
        self.db = SessionLocal()
        self.propublica_service = ProPublicaAPIService()
        self.apollo_service = ApolloService()
        self.db_service = DatabaseService(self.db)

        self.good_organizations = []
        self.processed_eins = set()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def cleanup(self):
        """Clean up resources."""
        try:
            await self.propublica_service.client.aclose()
            await self.apollo_service.close()
            self.db.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def is_good_apollo_enrichment(self, apollo_data: Dict) -> bool:
        """
        Determine if Apollo enrichment data is good enough to keep.

        Criteria for good enrichment:
        - Has enriched organization data
        - Organization has website URL or primary domain
        - Has at least some contact information (email, phone, address)
        - Has basic company details (industry, employee count, etc.)
        """
        if not apollo_data.get("success"):
            return False

        enriched_data = apollo_data.get("enriched_data")
        best_match = apollo_data.get("best_match")

        # Check if we have enriched data or at least search results
        org_data = enriched_data or best_match
        if not org_data:
            return False

        score = 0
        max_score = 6

        # 1. Website/domain presence (critical)
        if org_data.get("website_url") or org_data.get("primary_domain"):
            score += 2

        # 2. Contact information
        if org_data.get("phone") or org_data.get("primary_phone"):
            score += 1

        # 3. Address information
        if (
            org_data.get("headquarters_address")
            or org_data.get("mailing_address")
            or org_data.get("street_address")
        ):
            score += 1

        # 4. Company details
        if org_data.get("industry") or org_data.get("keywords"):
            score += 1

        # 5. Employee count or revenue (business size indicators)
        if (
            org_data.get("employee_count")
            or org_data.get("estimated_num_employees")
            or org_data.get("annual_revenue")
        ):
            score += 1

        # Need at least 3 out of 6 criteria, with website being almost mandatory
        has_website = bool(
            org_data.get("website_url") or org_data.get("primary_domain")
        )
        return score >= 3 and has_website

    async def fetch_organizations_from_state(
        self, state: str, limit: int = 500
    ) -> List[Dict]:
        """Fetch organizations from a specific state using ProPublica API."""
        logger.info(f"Fetching up to {limit} organizations from {state}...")

        organizations = []
        page = 0

        while len(organizations) < limit:
            try:
                search_result = await self.propublica_service.search_organizations(
                    state=state,
                    c_code=3,  # 501(c)(3) organizations
                    page=page,
                )

                page_orgs = search_result.get("organizations", [])
                if not page_orgs:
                    logger.info(
                        f"No more organizations found on page {page} for {state}"
                    )
                    break

                # Filter out already processed organizations
                new_orgs = [
                    org
                    for org in page_orgs
                    if org.get("ein") not in self.processed_eins
                ]

                organizations.extend(new_orgs)
                logger.info(
                    f"Fetched {len(new_orgs)} new organizations from {state}, "
                    f"total: {len(organizations)}"
                )

                page += 1

                # Add small delay to respect ProPublica API limits
                await asyncio.sleep(1.5)

            except Exception as e:
                logger.error(f"Error fetching page {page} from {state}: {e}")
                break

        return organizations[:limit]

    def save_enrichment_to_db(self, organization: Organization, apollo_data: Dict):
        """Save Apollo enrichment data to database for an existing organization."""
        try:
            # Create or update enrichment record
            enrichment = (
                self.db.query(OrganizationEnrichment)
                .filter(OrganizationEnrichment.organization_id == organization.id)
                .first()
            )

            if not enrichment:
                enrichment = OrganizationEnrichment(organization_id=organization.id)
                self.db.add(enrichment)

            # Update enrichment with Apollo data
            enrichment.apollo_searched = True
            enrichment.apollo_enriched = True
            enrichment.enrichment_status = "completed"
            enrichment.last_enriched_at = datetime.utcnow()

            # Store Apollo data
            if apollo_data.get("enriched_data"):
                enrichment.apollo_company_data = apollo_data["enriched_data"]
            elif apollo_data.get("best_match"):
                enrichment.apollo_company_data = apollo_data["best_match"]

            # Extract website URL from Apollo data
            apollo_org_data = enrichment.apollo_company_data
            if apollo_org_data and apollo_org_data.get("website_url"):
                enrichment.website_url = apollo_org_data["website_url"]
            elif apollo_org_data and apollo_org_data.get("primary_domain"):
                enrichment.website_url = f"https://{apollo_org_data['primary_domain']}"

            self.db.commit()
            logger.debug(f"Saved enrichment data for {organization.name}")

        except Exception as e:
            logger.error(f"Error saving enrichment data for {organization.name}: {e}")
            self.db.rollback()

    def store_organizations_to_db(
        self, organizations: List[Dict]
    ) -> List[Organization]:
        """Store all organizations to database first, then return the stored organizations."""
        logger.info(f"Storing {len(organizations)} organizations to database...")

        stored_orgs = []

        for org_data in organizations:
            try:
                # Parse ProPublica data
                parsed_org_data = self.propublica_service.parse_organization_data(
                    org_data
                )

                # Check if organization already exists
                existing_org = self.db_service.get_organization_by_ein(
                    parsed_org_data["ein"]
                )

                if existing_org:
                    logger.debug(
                        f"Organization {parsed_org_data['name']} already exists"
                    )
                    stored_orgs.append(existing_org)
                else:
                    # Convert to Pydantic model and create new organization
                    org_create = OrganizationCreate(**parsed_org_data)
                    organization = self.db_service.create_organization(org_create)
                    logger.debug(f"Created new organization: {organization.name}")
                    stored_orgs.append(organization)

            except Exception as e:
                logger.error(
                    f"Error storing organization {org_data.get('name', 'Unknown')}: {e}"
                )
                continue

        logger.info(f"Successfully stored {len(stored_orgs)} organizations to database")
        return stored_orgs

    async def enrich_stored_organizations(
        self, organizations: List[Organization], needed_count: int
    ) -> int:
        """Enrich stored organizations with Apollo data."""
        logger.info(
            f"Starting Apollo enrichment for {len(organizations)} organizations..."
        )

        good_count = 0

        for i, org in enumerate(organizations):
            # Skip if already processed
            if org.ein in self.processed_eins:
                continue

            self.processed_eins.add(org.ein)

            logger.info(
                f"[{i + 1}/{len(organizations)}] Enriching {org.name} (EIN: {org.ein}) with Apollo..."
            )

            try:
                # Use Apollo search and enrich with rate limiting
                apollo_result = (
                    await self.apollo_service.search_and_enrich_organization(
                        organization_name=org.name
                    )
                )

                # Add 1.5 second delay between Apollo calls to avoid rate limiting
                await asyncio.sleep(1.5)

                # Check if enrichment is good enough
                if self.is_good_apollo_enrichment(apollo_result):
                    logger.info(f"✅ Good enrichment for {org.name}")

                    # Save enrichment data
                    self.save_enrichment_to_db(org, apollo_result)

                    enriched_data = {
                        "organization": org,
                        "apollo_data": apollo_result,
                        "enrichment_quality": "good",
                    }

                    self.good_organizations.append(enriched_data)
                    good_count += 1

                    logger.info(
                        f"Progress: {len(self.good_organizations)}/{TARGET_GOOD_ORGS} good organizations"
                    )

                    # Check if we have enough
                    if len(self.good_organizations) >= needed_count:
                        break
                else:
                    logger.info(f"❌ Poor enrichment for {org.name}, skipping...")

            except Exception as e:
                logger.error(f"Error enriching {org.name} (EIN: {org.ein}): {e}")
                # Still add delay even on error to respect rate limits
                await asyncio.sleep(1.5)
                continue

        logger.info(f"Found {good_count} good organizations with Apollo enrichment")
        return good_count

    async def process_organizations_from_state(
        self, state: str, needed_count: int
    ) -> int:
        """Process organizations from a specific state and return count of good ones found."""
        logger.info(
            f"Processing organizations from {state}, need {needed_count} more good orgs..."
        )

        # Step 1: Fetch organizations from state
        organizations_data = await self.fetch_organizations_from_state(
            state, INITIAL_FETCH_LIMIT
        )

        if not organizations_data:
            logger.warning(f"No organizations found in {state}")
            return 0

        # Step 2: Store all organizations to database first
        stored_orgs = self.store_organizations_to_db(organizations_data)

        # Step 3: Enrich stored organizations with Apollo
        good_count = await self.enrich_stored_organizations(stored_orgs, needed_count)

        logger.info(f"Found {good_count} good organizations from {state}")
        return good_count

    async def run(self):
        """Main execution method."""
        logger.info("Starting California organization enrichment script...")

        try:
            # Start with California
            await self.process_organizations_from_state("CA", TARGET_GOOD_ORGS)

            # If we don't have enough good organizations, try other states
            for state in FALLBACK_STATES:
                if len(self.good_organizations) >= TARGET_GOOD_ORGS:
                    break

                needed = TARGET_GOOD_ORGS - len(self.good_organizations)
                logger.info(f"Need {needed} more good organizations, trying {state}...")

                await self.process_organizations_from_state(state, TARGET_GOOD_ORGS)

            # Final summary
            logger.info(f"✅ Script completed!")
            logger.info(
                f"Total good organizations found: {len(self.good_organizations)}"
            )
            logger.info(f"Organizations processed: {len(self.processed_eins)}")

            if len(self.good_organizations) >= TARGET_GOOD_ORGS:
                logger.info(
                    f"🎉 Successfully found {TARGET_GOOD_ORGS}+ organizations with good Apollo data!"
                )
            else:
                logger.warning(
                    f"⚠️  Only found {len(self.good_organizations)} good organizations (target: {TARGET_GOOD_ORGS})"
                )

        except Exception as e:
            logger.error(f"Script failed with error: {e}")
            raise


async def main():
    """Main entry point."""
    async with OrganizationEnricher() as enricher:
        await enricher.run()


if __name__ == "__main__":
    asyncio.run(main())
