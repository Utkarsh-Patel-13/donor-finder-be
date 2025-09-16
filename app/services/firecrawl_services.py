"""Firecrawl service for website scraping and data extraction."""

import logging
from typing import Dict, List, Optional
from firecrawl import Firecrawl
from app.models.database import get_settings
import re
import json

logger = logging.getLogger(__name__)


class FirecrawlService:
    """Service for website scraping using Firecrawl API."""

    def __init__(self):
        self.settings = get_settings()
        try:
            self.app = Firecrawl(api_key=self.settings.firecrawl_api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Firecrawl: {e}")
            self.app = None

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and accessible."""
        if not url:
            return False

        # Basic URL validation
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        return url_pattern.match(url) is not None

    def scrape_organization_website(self, website_url: str) -> Dict:
        """Scrape organization website for leadership and contact information."""
        if not self.app:
            return {"error": "Firecrawl not initialized"}

        if not self._is_valid_url(website_url):
            return {"error": "Invalid URL provided"}

        try:
            # Scrape the main page
            scrape_result = self.app.scrape(
                website_url,
                formats=["markdown", "html"],
                only_main_content=True,
                include_tags=["h1", "h2", "h3", "p", "div", "span", "a"],
                timeout=30000,
            )

            # Firecrawl v2 returns a Document object directly
            if hasattr(scrape_result, "markdown"):
                # Direct Document object
                markdown_content = scrape_result.markdown or ""
                metadata = scrape_result.metadata or {}
            else:
                # Fallback for other response formats
                if not scrape_result.get("success", True):
                    return {"error": "Failed to scrape website"}
                content = scrape_result.get("data", {})
                markdown_content = content.get("markdown", "")
                metadata = content.get("metadata", {})

            # Extract structured data using AI
            leadership_info = self._extract_leadership_info(markdown_content)
            contact_info = self._extract_contact_info(markdown_content)
            recent_news = self._extract_recent_news(markdown_content)

            return {
                "success": True,
                "website_url": website_url,
                "content": markdown_content,
                "metadata": metadata,
                "leadership_info": leadership_info,
                "contact_info": contact_info,
                "recent_news": recent_news,
            }

        except Exception as e:
            logger.error(f"Error scraping website {website_url}: {e}")
            return {"error": f"Scraping failed: {str(e)}"}

    def extract_structured_data(
        self, website_url: str, extraction_schema: Dict
    ) -> Dict:
        """Extract structured data from website using AI-powered extraction."""
        if not self.app:
            return {"error": "Firecrawl not initialized"}

        if not self._is_valid_url(website_url):
            return {"error": "Invalid URL provided"}

        try:
            # Use Firecrawl's extract endpoint for structured data
            extract_result = self.app.extract(
                website_url,
                schema=extraction_schema,
                timeout=30000,
            )

            # Handle Firecrawl v2 extract response
            if hasattr(extract_result, "json"):
                # Direct Document object with extracted JSON data
                extracted_data = extract_result.json or {}
            else:
                # Fallback for other response formats
                if not extract_result.get("success", True):
                    return {"error": "Failed to extract structured data"}
                extracted_data = extract_result.get("data", {})

            return {
                "success": True,
                "extracted_data": extracted_data,
                "website_url": website_url,
            }

        except Exception as e:
            logger.error(f"Error extracting structured data from {website_url}: {e}")
            return {"error": f"Extraction failed: {str(e)}"}

    def crawl_organization_website(self, website_url: str, max_pages: int = 5) -> Dict:
        """Crawl multiple pages of organization website for comprehensive data."""
        if not self.app:
            return {"error": "Firecrawl not initialized"}

        if not self._is_valid_url(website_url):
            return {"error": "Invalid URL provided"}

        try:
            # Crawl the website
            crawl_result = self.app.crawl_url(
                website_url,
                params={
                    "formats": ["markdown"],
                    "crawl_limit": max_pages,
                    "only_main_content": True,
                    "timeout": 60000,
                },
            )

            if not crawl_result.get("success", True):
                return {"error": "Failed to crawl website"}

            crawled_pages = crawl_result.get("data", [])

            # Aggregate data from all pages
            all_content = ""
            all_leadership = []
            all_contacts = []
            all_news = []

            for page in crawled_pages:
                content = page.get("markdown", "")
                all_content += content + "\n\n"

                # Extract data from each page
                leadership = self._extract_leadership_info(content)
                contacts = self._extract_contact_info(content)
                news = self._extract_recent_news(content)

                all_leadership.extend(leadership)
                all_contacts.extend(contacts)
                all_news.extend(news)

            # Deduplicate extracted data
            unique_leadership = self._deduplicate_leadership(all_leadership)
            unique_contacts = self._deduplicate_contacts(all_contacts)
            unique_news = self._deduplicate_news(all_news)

            return {
                "success": True,
                "website_url": website_url,
                "pages_crawled": len(crawled_pages),
                "content": all_content,
                "leadership_info": unique_leadership,
                "contact_info": unique_contacts,
                "recent_news": unique_news,
            }

        except Exception as e:
            logger.error(f"Error crawling website {website_url}: {e}")
            return {"error": f"Crawling failed: {str(e)}"}

    def _extract_leadership_info(self, content: str) -> List[Dict]:
        """Extract leadership information from website content."""
        leadership = []

        # Common patterns for leadership information
        leadership_patterns = [
            r"(?i)(ceo|chief executive officer|president|director|founder|chairman|chairwoman)\s*:?\s*([a-zA-Z\s\.]+)",
            r"(?i)([a-zA-Z\s\.]+),?\s+(ceo|chief executive officer|president|director|founder|chairman|chairwoman)",
            r"(?i)(executive director|managing director|board member)\s*:?\s*([a-zA-Z\s\.]+)",
        ]

        for pattern in leadership_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match) == 2:
                    title, name = (
                        match
                        if match[0].lower()
                        in [
                            "ceo",
                            "president",
                            "director",
                            "founder",
                            "chairman",
                            "chairwoman",
                        ]
                        else (match[1], match[0])
                    )
                    leadership.append(
                        {
                            "name": name.strip(),
                            "title": title.strip(),
                            "source": "website",
                        }
                    )

        return leadership[:10]  # Limit to top 10 leadership members

    def _extract_contact_info(self, content: str) -> List[Dict]:
        """Extract contact information from website content."""
        contacts = []

        # Email pattern
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        emails = re.findall(email_pattern, content)

        # Phone pattern
        phone_pattern = (
            r"(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})"
        )
        phones = re.findall(phone_pattern, content)

        # Address pattern (basic)
        address_pattern = r"\d+\s+[A-Za-z\s,]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Court|Ct|Place|Pl)[A-Za-z\s,]*\d{5}"
        addresses = re.findall(address_pattern, content)

        for email in emails[:5]:  # Limit emails
            contacts.append({"type": "email", "value": email, "source": "website"})

        for phone in phones[:3]:  # Limit phones
            formatted_phone = f"({phone[0]}) {phone[1]}-{phone[2]}"
            contacts.append(
                {"type": "phone", "value": formatted_phone, "source": "website"}
            )

        for address in addresses[:2]:  # Limit addresses
            contacts.append(
                {"type": "address", "value": address.strip(), "source": "website"}
            )

        return contacts

    def _extract_recent_news(self, content: str) -> List[Dict]:
        """Extract recent news, grants, or announcements from website content."""
        news = []

        # Patterns for news/grants/announcements
        news_patterns = [
            r"(?i)(grant|award|funding|donation|announce|news|press release)\s*:?\s*([^.]{50,200})",
            r"(?i)(recently|latest|new|announced)\s+([^.]{30,150})",
            r"(?i)\$[\d,]+\s+(grant|donation|funding)\s+([^.]{30,150})",
        ]

        for pattern in news_patterns:
            matches = re.findall(pattern, content)
            for match in matches[:5]:  # Limit news items
                if len(match) == 2:
                    news_type, description = match
                    news.append(
                        {
                            "type": news_type.strip(),
                            "description": description.strip(),
                            "source": "website",
                        }
                    )

        return news

    def _deduplicate_leadership(self, leadership: List[Dict]) -> List[Dict]:
        """Remove duplicate leadership entries."""
        seen = set()
        unique = []
        for person in leadership:
            key = (person.get("name", "").lower(), person.get("title", "").lower())
            if key not in seen:
                seen.add(key)
                unique.append(person)
        return unique

    def _deduplicate_contacts(self, contacts: List[Dict]) -> List[Dict]:
        """Remove duplicate contact entries."""
        seen = set()
        unique = []
        for contact in contacts:
            key = (contact.get("type", ""), contact.get("value", "").lower())
            if key not in seen:
                seen.add(key)
                unique.append(contact)
        return unique

    def _deduplicate_news(self, news: List[Dict]) -> List[Dict]:
        """Remove duplicate news entries."""
        seen = set()
        unique = []
        for item in news:
            key = item.get("description", "").lower()[:100]  # First 100 chars as key
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique
