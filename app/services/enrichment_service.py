"""Main enrichment service that coordinates Firecrawl and Apollo.io."""

import logging
from typing import Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.organization import Organization
from app.models.enrichment import OrganizationEnrichment
from app.services.firecrawl_services import FirecrawlService
from app.services.apollo_service import ApolloService
import re

logger = logging.getLogger(__name__)


class EnrichmentService:
    """Main service for enriching organization data using multiple sources."""

    def __init__(self, db: Session):
        self.db = db
        self.firecrawl_service = FirecrawlService()
        self.apollo_service = ApolloService()

    async def enrich_organization(
        self, organization_id: int, force_refresh: bool = False
    ) -> Dict:
        """Enrich an organization with data from external sources."""
        try:
            # Get organization from database
            organization = (
                self.db.query(Organization)
                .filter(Organization.id == organization_id)
                .first()
            )

            if not organization:
                return {
                    "success": False,
                    "error": "Organization not found",
                    "organization_id": organization_id,
                }

            # Check if enrichment already exists
            enrichment = organization.enrichment
            if enrichment and not force_refresh:
                if enrichment.enrichment_status == "completed":
                    return {
                        "success": True,
                        "message": "Organization already enriched. Use force_refresh=True to re-enrich.",
                        "organization_id": organization_id,
                        "enrichment_id": enrichment.id,
                        "status": enrichment.enrichment_status,
                    }

            # Create or update enrichment record
            if not enrichment:
                enrichment = OrganizationEnrichment(organization_id=organization_id)
                self.db.add(enrichment)

            enrichment.enrichment_status = "in_progress"
            enrichment.error_message = None
            self.db.commit()

            logger.info(
                f"Starting enrichment for organization {organization.name} (ID: {organization_id})"
            )

            # Initialize results
            results = {
                "success": True,
                "organization_id": organization_id,
                "organization_name": organization.name,
                "apollo_searched": False,
                "apollo_enriched": False,
                "website_scraped": False,
                "errors": [],
            }

            # Step 1: Search and enrich with Apollo.io
            apollo_result = await self._search_and_enrich_with_apollo(organization)
            results.update(apollo_result)

            # Step 2: Get website URL from Apollo data or fallback to existing logic
            website_url = self._determine_website_url_from_apollo_or_fallback(
                organization, apollo_result
            )

            # Step 3: Enrich with Firecrawl (website scraping) if we have a URL
            if website_url:
                website_result = await self._enrich_with_firecrawl(
                    organization, website_url
                )
                results.update(website_result)
            else:
                results["errors"].append("No website URL available for scraping")

            # Update enrichment record with results
            self._update_enrichment_record(enrichment, results, website_url)

            # Determine final status
            if (
                results["apollo_searched"]
                or results["apollo_enriched"]
                or results["website_scraped"]
            ):
                enrichment.enrichment_status = "completed"
                enrichment.last_enriched_at = datetime.utcnow()
            else:
                enrichment.enrichment_status = "failed"
                enrichment.error_message = "; ".join(results["errors"])

            self.db.commit()

            logger.info(f"Enrichment completed for organization {organization.name}")

            return {
                **results,
                "enrichment_id": enrichment.id,
                "status": enrichment.enrichment_status,
            }

        except Exception as e:
            logger.error(f"Error enriching organization {organization_id}: {e}")

            # Update enrichment status to failed
            if "enrichment" in locals() and enrichment:
                enrichment.enrichment_status = "failed"
                enrichment.error_message = str(e)
                self.db.commit()

            return {
                "success": False,
                "error": str(e),
                "organization_id": organization_id,
            }

    def _determine_website_url(self, organization: Organization) -> Optional[str]:
        """Determine the best website URL to scrape for an organization."""
        # Priority order: guidestar_url -> derived from name

        if organization.guidestar_url:
            return organization.guidestar_url

        # Try to construct a likely website URL
        if organization.name:
            # Simple heuristic: convert org name to domain
            domain_name = self._name_to_domain(organization.name)
            if domain_name:
                for ext in [".org", ".com", ".net"]:
                    potential_url = f"https://www.{domain_name}{ext}"
                    # We could validate this URL, but for now just return the most likely one
                    if ext == ".org":  # Nonprofits usually use .org
                        return potential_url

        return None

    def _name_to_domain(self, org_name: str) -> Optional[str]:
        """Convert organization name to a potential domain name."""
        if not org_name:
            return None

        # Remove common nonprofit terms and clean up the name
        name_lower = org_name.lower()

        # Remove common words
        remove_words = [
            "foundation",
            "inc",
            "incorporated",
            "organization",
            "fund",
            "trust",
            "society",
            "association",
            "center",
            "centre",
            "institute",
            "the",
            "of",
            "for",
            "and",
            "company",
            "corp",
            "corporation",
            "llc",
            "ltd",
        ]

        words = re.sub(r"[^a-zA-Z\s]", "", name_lower).split()
        filtered_words = [w for w in words if w not in remove_words and len(w) > 2]

        if filtered_words:
            # Take first 2-3 words and join them
            domain_words = (
                filtered_words[:2] if len(filtered_words) >= 2 else filtered_words[:1]
            )
            domain_name = "".join(domain_words)
            return domain_name if len(domain_name) > 3 else None

        return None

    async def _enrich_with_firecrawl(
        self, organization: Organization, website_url: str
    ) -> Dict:
        """Enrich organization using Firecrawl website scraping."""
        try:
            logger.info(f"Scraping website {website_url} for {organization.name}")

            scrape_result = self.firecrawl_service.scrape_organization_website(
                website_url
            )

            if scrape_result.get("success"):
                return {
                    "website_scraped": True,
                    "website_data": scrape_result,
                    "website_url": website_url,
                }
            else:
                error_msg = f"Website scraping failed: {scrape_result.get('error', 'Unknown error')}"
                logger.warning(error_msg)
                return {"website_scraped": False, "website_error": error_msg}

        except Exception as e:
            error_msg = f"Firecrawl enrichment error: {str(e)}"
            logger.error(error_msg)
            return {"website_scraped": False, "website_error": error_msg}

    async def _search_and_enrich_with_apollo(self, organization: Organization) -> Dict:
        """Search for organization and enrich using Apollo.io."""
        try:
            logger.info(
                f"Searching and enriching with Apollo.io for {organization.name}"
            )

            # Use the new search and enrich method
            apollo_result = await self.apollo_service.search_and_enrich_organization(
                organization_name=organization.name
            )

            if apollo_result.get("success"):
                return {
                    "apollo_searched": True,
                    "apollo_enriched": apollo_result.get("enriched_data") is not None,
                    "apollo_data": apollo_result,
                    "apollo_credits_used": apollo_result.get("total_credits_used", "0"),
                }
            else:
                error_msg = f"Apollo search/enrichment failed: {apollo_result.get('error', 'Unknown error')}"
                logger.warning(error_msg)
                return {
                    "apollo_searched": False,
                    "apollo_enriched": False,
                    "apollo_error": error_msg,
                }

        except Exception as e:
            error_msg = f"Apollo search/enrichment error: {str(e)}"
            logger.error(error_msg)
            return {
                "apollo_searched": False,
                "apollo_enriched": False,
                "apollo_error": error_msg,
            }

    def _determine_website_url_from_apollo_or_fallback(
        self, organization: Organization, apollo_result: Dict
    ) -> Optional[str]:
        """Determine website URL from Apollo data or fallback to existing logic."""
        # Try to get website from Apollo enriched data first
        if apollo_result.get("apollo_data") and apollo_result["apollo_data"].get(
            "enriched_data"
        ):
            enriched_data = apollo_result["apollo_data"]["enriched_data"]
            if enriched_data.get("website_url"):
                return enriched_data["website_url"]
            elif enriched_data.get("primary_domain"):
                return f"https://{enriched_data['primary_domain']}"

        # Try to get website from Apollo search results
        if apollo_result.get("apollo_data") and apollo_result["apollo_data"].get(
            "best_match"
        ):
            best_match = apollo_result["apollo_data"]["best_match"]
            if best_match.get("website_url"):
                return best_match["website_url"]
            elif best_match.get("primary_domain"):
                return f"https://{best_match['primary_domain']}"

        # Fallback to existing logic
        return self._determine_website_url(organization)

    def _update_enrichment_record(
        self,
        enrichment: OrganizationEnrichment,
        results: Dict,
        website_url: Optional[str],
    ):
        """Update enrichment record with results."""
        enrichment.website_url = website_url
        enrichment.website_scraped = results.get("website_scraped", False)
        enrichment.apollo_searched = results.get("apollo_searched", False)
        enrichment.apollo_enriched = results.get("apollo_enriched", False)

        # Store website data
        if results.get("website_data"):
            website_data = results["website_data"]
            enrichment.website_content = website_data.get("content", "")
            enrichment.leadership_info = website_data.get("leadership_info", [])
            enrichment.contact_info = website_data.get("contact_info", [])
            enrichment.recent_news = website_data.get("recent_news", [])

        # Store Apollo data
        if results.get("apollo_data"):
            apollo_data = results["apollo_data"]
            # Handle new Apollo data structure
            enrichment.apollo_company_data = apollo_data.get(
                "enriched_data", {}
            ) or apollo_data.get("best_match", {})
            enrichment.apollo_contacts = apollo_data.get("key_contacts", [])

        # Store errors if any
        if results.get("errors"):
            enrichment.error_message = "; ".join(results["errors"])

    def get_enriched_data(self, organization_id: int) -> Optional[Dict]:
        """Get enriched data for an organization."""
        enrichment = (
            self.db.query(OrganizationEnrichment)
            .filter(OrganizationEnrichment.organization_id == organization_id)
            .first()
        )

        if not enrichment:
            return None

        return {
            "enrichment_id": enrichment.id,
            "organization_id": enrichment.organization_id,
            "status": enrichment.enrichment_status,
            "last_enriched": enrichment.last_enriched_at,
            "website_url": enrichment.website_url,
            "website_scraped": enrichment.website_scraped,
            "apollo_searched": enrichment.apollo_searched,
            "apollo_enriched": enrichment.apollo_enriched,
            "leadership_info": enrichment.leadership_info or [],
            "contact_info": enrichment.contact_info or [],
            "recent_news": enrichment.recent_news or [],
            "apollo_company_data": enrichment.apollo_company_data or {},
            "apollo_contacts": enrichment.apollo_contacts or [],
            "error_message": enrichment.error_message,
            "created_at": enrichment.created_at,
            "updated_at": enrichment.updated_at,
        }

    async def close(self):
        """Close external service connections."""
        await self.apollo_service.close()
