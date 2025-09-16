#!/usr/bin/env python3
"""
Helper script to check the results of the enrichment process.
Shows statistics and examples of enriched organizations.
"""

import sys
import json
from typing import List, Dict

# Add the app directory to Python path
sys.path.append("/Users/utkarshpatel/Projects/df/donor_finder_backend")

from sqlalchemy.orm import Session
from app.models.database import SessionLocal
from app.models.organization import Organization
from app.models.enrichment import OrganizationEnrichment


def check_enrichment_results():
    """Check and display enrichment results."""
    db = SessionLocal()

    try:
        # Get enrichment statistics
        total_enriched = db.query(OrganizationEnrichment).count()
        apollo_searched = (
            db.query(OrganizationEnrichment)
            .filter(OrganizationEnrichment.apollo_searched == True)
            .count()
        )
        apollo_enriched = (
            db.query(OrganizationEnrichment)
            .filter(OrganizationEnrichment.apollo_enriched == True)
            .count()
        )
        completed = (
            db.query(OrganizationEnrichment)
            .filter(OrganizationEnrichment.enrichment_status == "completed")
            .count()
        )

        print("=== ENRICHMENT STATISTICS ===")
        print(f"Total enriched organizations: {total_enriched}")
        print(f"Apollo searched: {apollo_searched}")
        print(f"Apollo enriched: {apollo_enriched}")
        print(f"Completed enrichments: {completed}")
        print()

        # Get organizations with good Apollo data
        good_enrichments = (
            db.query(OrganizationEnrichment)
            .filter(
                OrganizationEnrichment.apollo_enriched == True,
                OrganizationEnrichment.enrichment_status == "completed",
            )
            .all()
        )

        print("=== GOOD ENRICHMENTS ===")
        print(f"Organizations with good Apollo data: {len(good_enrichments)}")
        print()

        # Show examples of good enrichments
        print("=== EXAMPLES OF GOOD ENRICHMENTS ===")
        for i, enrichment in enumerate(good_enrichments[:5]):  # Show first 5
            org = enrichment.organization
            apollo_data = enrichment.apollo_company_data or {}

            print(f"{i + 1}. {org.name} (EIN: {org.ein})")
            print(f"   State: {org.state}")
            print(f"   Website: {enrichment.website_url or 'N/A'}")
            print(f"   Apollo Domain: {apollo_data.get('primary_domain', 'N/A')}")
            print(f"   Industry: {apollo_data.get('industry', 'N/A')}")
            print(
                f"   Employees: {apollo_data.get('employee_count', apollo_data.get('estimated_num_employees', 'N/A'))}"
            )
            print(
                f"   Phone: {apollo_data.get('phone', apollo_data.get('primary_phone', 'N/A'))}"
            )
            print(
                f"   Address: {apollo_data.get('headquarters_address', apollo_data.get('mailing_address', 'N/A'))}"
            )
            print()

        # State distribution
        print("=== STATE DISTRIBUTION ===")
        state_counts = (
            db.query(Organization.state, db.func.count(OrganizationEnrichment.id))
            .join(OrganizationEnrichment)
            .filter(OrganizationEnrichment.apollo_enriched == True)
            .group_by(Organization.state)
            .all()
        )

        for state, count in sorted(state_counts, key=lambda x: x[1], reverse=True):
            print(f"{state}: {count} organizations")

    finally:
        db.close()


def show_apollo_data_sample():
    """Show a detailed sample of Apollo data structure."""
    db = SessionLocal()

    try:
        enrichment = (
            db.query(OrganizationEnrichment)
            .filter(
                OrganizationEnrichment.apollo_enriched == True,
                OrganizationEnrichment.apollo_company_data != None,
            )
            .first()
        )

        if enrichment:
            print("=== SAMPLE APOLLO DATA STRUCTURE ===")
            print(f"Organization: {enrichment.organization.name}")
            print("Apollo Company Data:")
            apollo_data = enrichment.apollo_company_data
            print(json.dumps(apollo_data, indent=2, default=str))
        else:
            print("No enriched organizations found with Apollo data.")

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check enrichment results")
    parser.add_argument(
        "--sample", action="store_true", help="Show sample Apollo data structure"
    )

    args = parser.parse_args()

    if args.sample:
        show_apollo_data_sample()
    else:
        check_enrichment_results()
