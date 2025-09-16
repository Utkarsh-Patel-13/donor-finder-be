"""Apollo.io service for contact and organization enrichment."""

import httpx
import logging
from typing import Dict, List, Optional
from app.models.database import get_settings
import asyncio

logger = logging.getLogger(__name__)


class ApolloService:
    """Service for enriching contact and organization data using Apollo.io API."""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = "https://api.apollo.io/api/v1"

        if not self.settings.apollo_api_key:
            logger.error("Apollo API key is not configured")
            raise ValueError("Apollo API key is required")

        self.headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.settings.apollo_api_key,
        }
        self.client = httpx.AsyncClient(timeout=30.0, headers=self.headers)

    async def search_organizations(
        self,
        query: Optional[str] = None,
        organization_name: Optional[str] = None,
        domain: Optional[str] = None,
        website: Optional[str] = None,
        limit: int = 10,
    ) -> Dict:
        """Search for organizations using Apollo.io search API."""
        try:
            # Prepare search parameters
            search_params = {
                "page": 1,
                "per_page": min(limit, 25),  # Apollo API limit
            }

            # Ensure at least one search parameter is provided
            has_search_criteria = False

            if query and query.strip():
                search_params["q_organization_name"] = query.strip()
                has_search_criteria = True
            elif organization_name and organization_name.strip():
                search_params["q_organization_name"] = organization_name.strip()
                has_search_criteria = True

            if domain and domain.strip():
                search_params["q_organization_domains"] = [domain.strip().lower()]
                has_search_criteria = True
            elif website and website.strip():
                extracted_domain = self._extract_domain_from_url(website.strip())
                if extracted_domain:
                    search_params["q_organization_domains"] = [extracted_domain]
                    has_search_criteria = True

            # Apollo API requires at least one search parameter
            if not has_search_criteria:
                return {
                    "success": False,
                    "error": "At least one search parameter (organization name, domain, or website) is required",
                    "data": [],
                    "credits_used": "0",
                }

            url = f"{self.base_url}/organizations/search"

            logger.debug(f"Apollo search params: {search_params}")
            response = await self.client.post(url, json=search_params)
            response.raise_for_status()

            result = response.json()
            organizations = result.get("organizations", [])

            return {
                "success": True,
                "data": organizations,
                "total_results": len(organizations),
                "credits_used": response.headers.get("x-credits-used", "0"),
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Apollo organization search HTTP error: {e}")
            logger.error(f"Request URL: {url}")
            logger.error(f"Request params: {search_params}")
            logger.error(f"Response: {e.response.text}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "data": [],
                "credits_used": "0",
            }
        except Exception as e:
            logger.error(f"Apollo organization search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "credits_used": "0",
            }

    async def enrich_organization(
        self,
        organization_name: Optional[str] = None,
        domain: Optional[str] = None,
        website: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Dict:
        """Enrich organization data using Apollo.io Organization Enrichment API (GET)."""
        try:
            # Build query parameters for GET request
            params = {}

            if organization_id:
                params["id"] = organization_id
            elif domain:
                params["domain"] = domain
            elif website:
                # Extract domain from website URL
                extracted_domain = self._extract_domain_from_url(website)
                if extracted_domain:
                    params["domain"] = extracted_domain
            elif organization_name:
                params["name"] = organization_name
            else:
                return {
                    "success": False,
                    "error": "At least one identifier (name, domain, website, or organization_id) is required",
                    "credits_used": "0",
                }

            url = f"{self.base_url}/organizations/enrich"

            logger.debug(f"Apollo enrichment params: {params}")
            response = await self.client.get(url, params=params)
            response.raise_for_status()

            result = response.json()

            if result.get("organization"):
                return {
                    "success": True,
                    "data": result["organization"],
                    "credits_used": response.headers.get("x-credits-used", "0"),
                }
            else:
                return {
                    "success": False,
                    "error": "No organization data found",
                    "credits_used": response.headers.get("x-credits-used", "0"),
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Apollo organization enrichment HTTP error: {e}")
            logger.error(f"Request URL: {url}")
            logger.error(f"Request params: {params}")
            logger.error(f"Response: {e.response.text}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "credits_used": "0",
            }
        except Exception as e:
            logger.error(f"Apollo organization enrichment error: {e}")
            return {"success": False, "error": str(e), "credits_used": "0"}

    async def enrich_people_by_organization(
        self, organization_name: str, domain: Optional[str] = None, limit: int = 10
    ) -> Dict:
        """Find and enrich people associated with an organization."""
        try:
            # Search for people in the organization
            search_params = {
                "q_organization_name": organization_name,
                "page": 1,
                "per_page": min(limit, 25),  # Apollo API limit
            }

            if domain:
                search_params["q_organization_domains"] = [domain]

            # Search for people (using standard people/search endpoint)
            search_url = f"{self.base_url}/people/search"
            search_response = await self.client.post(search_url, json=search_params)
            search_response.raise_for_status()

            search_result = search_response.json()
            people = search_result.get("people", [])

            if not people:
                return {
                    "success": True,
                    "data": [],
                    "message": "No people found for this organization",
                    "credits_used": search_response.headers.get("x-credits-used", "0"),
                }

            # Enrich up to 10 people in batch
            enrichment_data = []
            for person in people[:10]:
                person_data = {
                    "first_name": person.get("first_name"),
                    "last_name": person.get("last_name"),
                    "email": person.get("email"),
                    "organization_name": organization_name,
                }

                if domain:
                    person_data["domain"] = domain

                enrichment_data.append(person_data)

            if enrichment_data:
                # Bulk enrich people
                bulk_enrich_result = await self.bulk_enrich_people(enrichment_data)
                return bulk_enrich_result
            else:
                return {
                    "success": True,
                    "data": people,
                    "message": "Found people but no enrichment data available",
                    "credits_used": search_response.headers.get("x-credits-used", "0"),
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Apollo people search HTTP error: {e}")
            logger.error(f"Request URL: {search_url}")
            logger.error(f"Request params: {search_params}")
            logger.error(f"Response: {e.response.text}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "credits_used": "0",
            }
        except Exception as e:
            logger.error(f"Apollo people search error: {e}")
            return {"success": False, "error": str(e), "credits_used": "0"}

    async def bulk_enrich_people(self, people_data: List[Dict]) -> Dict:
        """Bulk enrich up to 10 people at once."""
        try:
            if len(people_data) > 10:
                people_data = people_data[:10]  # Apollo limit

            enrichment_payload = {
                "details": people_data,
                "reveal_personal_emails": False,
                "reveal_phone_number": True,
            }

            url = f"{self.base_url}/people/bulk_match"
            response = await self.client.post(url, json=enrichment_payload)
            response.raise_for_status()

            result = response.json()

            return {
                "success": True,
                "data": result.get("matches", []),
                "total_enriched": len(result.get("matches", [])),
                "credits_used": response.headers.get("x-credits-used", "0"),
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Apollo bulk people enrichment HTTP error: {e}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "credits_used": "0",
            }
        except Exception as e:
            logger.error(f"Apollo bulk people enrichment error: {e}")
            return {"success": False, "error": str(e), "credits_used": "0"}

    async def enrich_person(
        self,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        domain: Optional[str] = None,
        organization_name: Optional[str] = None,
    ) -> Dict:
        """Enrich a single person's data."""
        try:
            params = {}

            if email:
                params["email"] = email
            if first_name:
                params["first_name"] = first_name
            if last_name:
                params["last_name"] = last_name
            if domain:
                params["domain"] = domain
            if organization_name:
                params["organization_name"] = organization_name

            params["reveal_personal_emails"] = False
            params["reveal_phone_number"] = True

            url = f"{self.base_url}/people/match"
            response = await self.client.post(url, params=params)
            response.raise_for_status()

            result = response.json()

            if result.get("person"):
                return {
                    "success": True,
                    "data": result["person"],
                    "credits_used": response.headers.get("x-credits-used", "0"),
                }
            else:
                return {
                    "success": False,
                    "error": "No person data found",
                    "credits_used": response.headers.get("x-credits-used", "0"),
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Apollo person enrichment HTTP error: {e}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "credits_used": "0",
            }
        except Exception as e:
            logger.error(f"Apollo person enrichment error: {e}")
            return {"success": False, "error": str(e), "credits_used": "0"}

    def _extract_domain_from_url(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            import re

            # Remove protocol and www, get domain
            domain_match = re.search(r"https?://(?:www\.)?([^/]+)", url)
            if domain_match:
                return domain_match.group(1).lower()
            return None
        except Exception:
            return None

    def _normalize_phone_number(self, phone: str) -> str:
        """Normalize phone number format."""
        import re

        # Remove all non-digits
        digits = re.sub(r"\D", "", phone)

        # Format as (XXX) XXX-XXXX for US numbers
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == "1":
            return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            return phone  # Return original if can't format

    async def search_and_enrich_organization(
        self, organization_name: str, domain: Optional[str] = None
    ) -> Dict:
        """Search for organization and then enrich the best match."""
        try:
            # First, search for organizations
            search_result = await self.search_organizations(
                organization_name=organization_name, domain=domain, limit=5
            )

            if not search_result.get("success") or not search_result.get("data"):
                return {
                    "success": False,
                    "error": f"No organizations found for '{organization_name}'",
                    "search_result": search_result,
                    "enriched_data": None,
                    "credits_used": search_result.get("credits_used", "0"),
                }

            # Get the best match (first result is usually the best)
            organizations = search_result["data"]
            best_match = organizations[0]

            # Extract domain from the best match for enrichment
            org_domain = None
            if best_match.get("primary_domain"):
                org_domain = best_match["primary_domain"]
            elif domain:
                org_domain = domain

            # Enrich the organization
            enrich_result = await self.enrich_organization(
                organization_name=organization_name, domain=org_domain
            )

            return {
                "success": True,
                "search_result": search_result,
                "enriched_data": enrich_result.get("data")
                if enrich_result.get("success")
                else None,
                "best_match": best_match,
                "total_credits_used": str(
                    int(search_result.get("credits_used", "0"))
                    + int(enrich_result.get("credits_used", "0"))
                ),
                "errors": []
                if enrich_result.get("success")
                else [enrich_result.get("error")],
            }

        except Exception as e:
            logger.error(f"Apollo search and enrich error: {e}")
            return {
                "success": False,
                "error": str(e),
                "search_result": None,
                "enriched_data": None,
                "credits_used": "0",
            }

    async def get_organization_contacts_summary(
        self, organization_name: str, domain: Optional[str] = None
    ) -> Dict:
        """Get a comprehensive summary of organization and its key contacts."""
        try:
            # Enrich organization and find people in parallel
            org_task = self.enrich_organization(organization_name, domain)
            people_task = self.enrich_people_by_organization(
                organization_name, domain, limit=5
            )

            org_result, people_result = await asyncio.gather(org_task, people_task)

            # Combine results
            summary = {
                "success": True,
                "organization": org_result.get("data")
                if org_result.get("success")
                else None,
                "key_contacts": people_result.get("data", [])
                if people_result.get("success")
                else [],
                "total_credits_used": str(
                    int(org_result.get("credits_used", "0"))
                    + int(people_result.get("credits_used", "0"))
                ),
                "errors": [],
            }

            if not org_result.get("success"):
                summary["errors"].append(
                    f"Organization enrichment: {org_result.get('error')}"
                )

            if not people_result.get("success"):
                summary["errors"].append(
                    f"People enrichment: {people_result.get('error')}"
                )

            return summary

        except Exception as e:
            logger.error(f"Apollo organization contacts summary error: {e}")
            return {
                "success": False,
                "error": str(e),
                "organization": None,
                "key_contacts": [],
                "total_credits_used": "0",
            }

    async def search_news_articles(
        self,
        organization_name: Optional[str] = None,
        domain: Optional[str] = None,
        organization_ids: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        date_range: Optional[Dict] = None,
        limit: int = 10,
    ) -> Dict:
        """Search for news articles related to organizations using Apollo.io News Articles Search API."""
        try:
            # Prepare search parameters
            search_params = {
                "page": 1,
                "per_page": min(limit, 50),  # Apollo API limit
            }

            # Add organization filters
            if organization_ids:
                search_params["organization_ids"] = organization_ids
            elif organization_name:
                search_params["q_organization_name"] = organization_name
            elif domain:
                search_params["q_organization_domains"] = [domain]

            # Add keyword filters
            if keywords:
                search_params["q_keywords"] = keywords

            # Add date range filter
            if date_range:
                if date_range.get("start_date"):
                    search_params["published_at_date_range"] = {
                        "min": date_range["start_date"]
                    }
                if date_range.get("end_date"):
                    if "published_at_date_range" not in search_params:
                        search_params["published_at_date_range"] = {}
                    search_params["published_at_date_range"]["max"] = date_range[
                        "end_date"
                    ]

            url = f"{self.base_url}/news_articles/search"

            logger.debug(f"Apollo news search params: {search_params}")
            response = await self.client.post(url, json=search_params)
            response.raise_for_status()

            result = response.json()
            articles = result.get("news_articles", [])

            return {
                "success": True,
                "data": articles,
                "total_results": len(articles),
                "pagination": result.get("pagination", {}),
                "credits_used": response.headers.get("x-credits-used", "0"),
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Apollo news search HTTP error: {e}")
            logger.error(f"Request URL: {url}")
            logger.error(f"Request params: {search_params}")
            logger.error(f"Response: {e.response.text}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "data": [],
                "credits_used": "0",
            }
        except Exception as e:
            logger.error(f"Apollo news search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "credits_used": "0",
            }

    async def get_complete_organization_info(
        self,
        organization_id: str,
        include_contacts: bool = True,
        include_news: bool = True,
    ) -> Dict:
        """Get complete organization information including contacts and news."""
        try:
            # Get organization details
            url = f"{self.base_url}/organizations/{organization_id}"

            params = {}
            if include_contacts:
                params["with_contacts"] = "true"

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            result = response.json()
            organization_data = result.get("organization", {})

            # Get news articles if requested
            news_data = []
            if include_news and organization_id:
                news_result = await self.search_news_articles(
                    organization_ids=[organization_id], limit=20
                )
                if news_result.get("success"):
                    news_data = news_result.get("data", [])

            return {
                "success": True,
                "organization": organization_data,
                "contacts": organization_data.get("contacts", []),
                "news_articles": news_data,
                "credits_used": response.headers.get("x-credits-used", "0"),
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Apollo complete org info HTTP error: {e}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "credits_used": "0",
            }
        except Exception as e:
            logger.error(f"Apollo complete org info error: {e}")
            return {"success": False, "error": str(e), "credits_used": "0"}

    async def comprehensive_organization_enrichment(
        self,
        organization_name: str,
        domain: Optional[str] = None,
        include_news: bool = True,
        include_contacts: bool = True,
    ) -> Dict:
        """Perform comprehensive organization enrichment using multiple Apollo APIs."""
        try:
            total_credits = 0
            results = {
                "success": True,
                "organization_data": None,
                "search_results": [],
                "enriched_data": None,
                "contacts": [],
                "news_articles": [],
                "errors": [],
            }

            # Step 1: Search for organizations
            search_result = await self.search_organizations(
                organization_name=organization_name, domain=domain, limit=10
            )

            if search_result.get("success") and search_result.get("data"):
                results["search_results"] = search_result["data"]
                total_credits += int(search_result.get("credits_used", "0"))

                # Get the best match
                best_match = search_result["data"][0]
                results["organization_data"] = best_match

                # Step 2: Enrich the organization
                org_domain = best_match.get("primary_domain") or domain
                enrich_result = await self.enrich_organization(
                    organization_name=organization_name, domain=org_domain
                )

                if enrich_result.get("success"):
                    results["enriched_data"] = enrich_result["data"]
                    total_credits += int(enrich_result.get("credits_used", "0"))
                else:
                    results["errors"].append(
                        f"Enrichment failed: {enrich_result.get('error')}"
                    )

                # Step 3: Get contacts if requested
                if include_contacts:
                    contacts_result = await self.enrich_people_by_organization(
                        organization_name=organization_name, domain=org_domain, limit=10
                    )

                    if contacts_result.get("success"):
                        results["contacts"] = contacts_result.get("data", [])
                        total_credits += int(contacts_result.get("credits_used", "0"))
                    else:
                        results["errors"].append(
                            f"Contacts search failed: {contacts_result.get('error')}"
                        )

                # Step 4: Get news articles if requested
                if include_news:
                    news_result = await self.search_news_articles(
                        organization_name=organization_name, domain=org_domain, limit=20
                    )

                    if news_result.get("success"):
                        results["news_articles"] = news_result.get("data", [])
                        total_credits += int(news_result.get("credits_used", "0"))
                    else:
                        results["errors"].append(
                            f"News search failed: {news_result.get('error')}"
                        )

            else:
                results["success"] = False
                results["errors"].append(
                    f"Organization search failed: {search_result.get('error')}"
                )

            results["total_credits_used"] = str(total_credits)
            return results

        except Exception as e:
            logger.error(f"Comprehensive enrichment error: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_credits_used": "0",
            }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
