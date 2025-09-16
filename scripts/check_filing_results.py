#!/usr/bin/env python3
"""
Helper script to check filing sync results.
Shows statistics about filings in the database.
"""

import sys
from typing import List, Dict

# Add the app directory to Python path
sys.path.append("/Users/utkarshpatel/Projects/df/donor_finder_backend")

from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.models.database import SessionLocal
from app.models.organization import Organization
from app.models.filing import Filing
from app.models.enrichment import OrganizationEnrichment


def check_filing_statistics():
    """Check and display filing statistics."""
    db = SessionLocal()

    try:
        # Basic filing statistics
        total_filings = db.query(Filing).count()
        total_orgs_with_filings = db.query(Filing.organization_id).distinct().count()
        total_organizations = db.query(Organization).count()

        print("=== FILING STATISTICS ===")
        print(f"Total filings in database: {total_filings}")
        print(f"Organizations with filings: {total_orgs_with_filings}")
        print(f"Total organizations: {total_organizations}")
        print(
            f"Organizations without filings: {total_organizations - total_orgs_with_filings}"
        )
        print()

        # Filing by form type
        print("=== FILINGS BY FORM TYPE ===")
        form_types = {0: "Form 990", 1: "Form 990-EZ", 2: "Form 990-PF"}

        for form_code, form_name in form_types.items():
            count = db.query(Filing).filter(Filing.formtype == form_code).count()
            print(f"{form_name}: {count} filings")

        unknown_forms = db.query(Filing).filter(~Filing.formtype.in_([0, 1, 2])).count()
        print(f"Unknown form types: {unknown_forms} filings")
        print()

        # Filing by year
        print("=== FILINGS BY YEAR (Latest 10 years) ===")
        year_counts = (
            db.query(Filing.tax_prd_yr, func.count(Filing.id))
            .group_by(Filing.tax_prd_yr)
            .order_by(desc(Filing.tax_prd_yr))
            .limit(10)
            .all()
        )

        for year, count in year_counts:
            print(f"{year}: {count} filings")
        print()

        # Organizations with enrichment and filings
        print("=== ENRICHED ORGANIZATIONS WITH FILINGS ===")
        enriched_with_filings = (
            db.query(Organization)
            .join(OrganizationEnrichment)
            .join(Filing)
            .filter(OrganizationEnrichment.apollo_enriched == True)
            .distinct()
            .count()
        )

        enriched_total = (
            db.query(Organization)
            .join(OrganizationEnrichment)
            .filter(OrganizationEnrichment.apollo_enriched == True)
            .count()
        )

        print(f"Enriched organizations with filings: {enriched_with_filings}")
        print(f"Total enriched organizations: {enriched_total}")
        print(
            f"Enriched organizations without filings: {enriched_total - enriched_with_filings}"
        )
        print()

        # Top organizations by filing count
        print("=== TOP 10 ORGANIZATIONS BY FILING COUNT ===")
        top_orgs = (
            db.query(
                Organization.name,
                Organization.state,
                Organization.ein,
                func.count(Filing.id).label("filing_count"),
            )
            .join(Filing)
            .group_by(
                Organization.id, Organization.name, Organization.state, Organization.ein
            )
            .order_by(desc("filing_count"))
            .limit(10)
            .all()
        )

        for org_name, state, ein, count in top_orgs:
            print(f"{org_name} ({state}) - EIN: {ein} - {count} filings")
        print()

        # State distribution of organizations with filings
        print("=== STATE DISTRIBUTION (Organizations with filings) ===")
        state_counts = (
            db.query(Organization.state, func.count(Organization.id).label("org_count"))
            .join(Filing)
            .group_by(Organization.state)
            .order_by(desc("org_count"))
            .limit(15)
            .all()
        )

        for state, count in state_counts:
            print(f"{state}: {count} organizations")

    finally:
        db.close()


def show_sample_filings():
    """Show sample filing data."""
    db = SessionLocal()

    try:
        print("=== SAMPLE FILING DATA ===")

        # Get a few sample filings with organization info
        sample_filings = (
            db.query(Filing, Organization)
            .join(Organization)
            .order_by(desc(Filing.tax_prd_yr))
            .limit(5)
            .all()
        )

        for filing, org in sample_filings:
            print(f"\nOrganization: {org.name} ({org.state})")
            print(f"EIN: {filing.ein}")
            print(f"Tax Period: {filing.tax_prd} (Year: {filing.tax_prd_yr})")
            print(f"Form Type: {filing.formtype}")
            print(
                f"Total Revenue: ${filing.totrevenue:,}"
                if filing.totrevenue
                else "Total Revenue: N/A"
            )
            print(
                f"Total Assets: ${filing.totassetsend:,}"
                if filing.totassetsend
                else "Total Assets: N/A"
            )
            print(
                f"PDF URL: {filing.pdf_url[:80]}..."
                if filing.pdf_url
                else "PDF URL: N/A"
            )

    finally:
        db.close()


def check_organizations_needing_filings():
    """Check which organizations still need filing sync."""
    db = SessionLocal()

    try:
        print("=== ORGANIZATIONS NEEDING FILING SYNC ===")

        # Enriched organizations without filings
        orgs_without_filings = (
            db.query(Organization)
            .join(OrganizationEnrichment)
            .outerjoin(Filing)
            .filter(OrganizationEnrichment.apollo_enriched == True, Filing.id == None)
            .limit(20)
            .all()
        )

        print(
            f"Found {len(orgs_without_filings)} enriched organizations without filings (showing first 20):"
        )
        print()

        for org in orgs_without_filings:
            print(f"- {org.name} ({org.state}) - EIN: {org.ein}")

        # Count by state
        print("\n=== COUNT BY STATE (Enriched orgs without filings) ===")
        state_counts = (
            db.query(Organization.state, func.count(Organization.id))
            .join(OrganizationEnrichment)
            .outerjoin(Filing)
            .filter(OrganizationEnrichment.apollo_enriched == True, Filing.id == None)
            .group_by(Organization.state)
            .order_by(desc(func.count(Organization.id)))
            .all()
        )

        for state, count in state_counts:
            print(f"{state}: {count} organizations")

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check filing sync results")
    parser.add_argument("--sample", action="store_true", help="Show sample filing data")
    parser.add_argument(
        "--need-sync",
        action="store_true",
        help="Show organizations that need filing sync",
    )

    args = parser.parse_args()

    if args.sample:
        show_sample_filings()
    elif args.need_sync:
        check_organizations_needing_filings()
    else:
        check_filing_statistics()
