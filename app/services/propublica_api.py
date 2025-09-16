import httpx
from typing import Dict, Optional
from app.models.database import get_settings
import json
from datetime import datetime


class ProPublicaAPIService:
    """Service for interacting with ProPublica Nonprofit Explorer API."""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.propublica_api_base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def search_organizations(
        self,
        query: Optional[str] = None,
        state: Optional[str] = None,
        ntee_code: Optional[int] = None,
        c_code: Optional[int] = None,
        page: int = 0,
    ) -> Dict:
        """Search for organizations using ProPublica API."""
        params = {"page": page}

        if query:
            params["q"] = query
        if state:
            params["state[id]"] = state
        if ntee_code:
            params["ntee[id]"] = ntee_code
        if c_code:
            params["c_code[id]"] = c_code

        url = f"{self.base_url}/search.json"
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def get_organization_details(self, ein: int) -> Dict:
        """Get detailed organization data including filings."""
        url = f"{self.base_url}/organizations/{ein}.json"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    def parse_organization_data(self, org_data: Dict) -> Dict:
        """Parse organization data from API response."""
        parsed = {
            "ein": org_data.get("ein"),
            "strein": org_data.get("strein"),
            "name": org_data.get("name"),
            "sub_name": org_data.get("sub_name"),
            "address": org_data.get("address"),
            "city": org_data.get("city"),
            "state": org_data.get("state"),
            "zipcode": org_data.get("zipcode"),
            "subseccd": org_data.get("subseccd"),
            "ntee_code": org_data.get("ntee_code"),
            "guidestar_url": org_data.get("guidestar_url"),
            "nccs_url": org_data.get("nccs_url"),
        }

        # Parse updated timestamp
        if org_data.get("updated"):
            try:
                parsed["irs_updated"] = datetime.fromisoformat(
                    org_data["updated"].replace("Z", "+00:00")
                )
            except ValueError:
                parsed["irs_updated"] = None

        return parsed

    def parse_filing_data(self, filing_data: Dict, organization_id: int) -> Dict:
        """Parse filing data from API response."""
        parsed = {
            "organization_id": organization_id,
            "ein": filing_data.get("ein"),
            "tax_prd": filing_data.get("tax_prd"),
            "tax_prd_yr": filing_data.get("tax_prd_yr"),
            "formtype": filing_data.get("formtype"),
            "pdf_url": filing_data.get("pdf_url"),
            "totrevenue": filing_data.get("totrevenue"),
            "totfuncexpns": filing_data.get("totfuncexpns"),
            "totassetsend": filing_data.get("totassetsend"),
            "totliabend": filing_data.get("totliabend"),
            "pct_compnsatncurrofcr": filing_data.get("pct_compnsatncurrofcr"),
            "raw_data": json.dumps(filing_data),
        }

        # Parse updated timestamp
        if filing_data.get("updated"):
            try:
                parsed["irs_updated"] = datetime.fromisoformat(
                    filing_data["updated"].replace("Z", "+00:00")
                )
            except ValueError:
                parsed["irs_updated"] = None

        return parsed

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
