# Enrichment Scripts

## Overview
These scripts help you fetch and enrich organizations with Apollo.io data, keeping only those with high-quality enrichment.

## Scripts

### 1. `enrich_california_orgs.py`
Main enrichment script that:
- Fetches 500 organizations from California using ProPublica API
- **Stores ALL organizations to database first**
- Then enriches each stored organization using Apollo.io (search + enrichment)
- **Rate limited Apollo calls: 1 call per 1.5 seconds** to avoid "too many requests" errors
- Keeps only organizations with good Apollo data (website, contact info, etc.)
- If less than 30 good organizations found, fetches from other states
- **Does NOT perform Firecrawl website scraping**

#### Quality Criteria for "Good" Enrichment:
- Has website URL or primary domain (mandatory)
- Has contact information (phone, email, or address)
- Has business details (industry, employee count, etc.)
- Minimum score of 3/6 criteria met

#### Usage:
```bash
# Make sure you're in the project root directory
cd /Users/utkarshpatel/Projects/df/donor_finder_backend

# Activate virtual environment
source .venv/bin/activate

# Run the enrichment script
python scripts/enrich_california_orgs.py
```

### 2. `sync_organization_filings.py`
Script to sync filings for organizations already in the database:
- Fetches organizations from database (with optional filters)
- Calls ProPublica API to get detailed organization data including filings
- Updates the filings table with latest Form 990 data
- **Rate limited API calls: 0.5 seconds** between requests
- Processes organizations in batches for better performance
- Handles both new filings and updates to existing filings

#### Usage:
```bash
# Sync filings for all enriched organizations
python scripts/sync_organization_filings.py

# Sync filings for California organizations only
python scripts/sync_organization_filings.py --state CA

# Include organizations without Apollo enrichment
python scripts/sync_organization_filings.py --no-enrichment

# Process only first 100 organizations
python scripts/sync_organization_filings.py --limit 100

# Use smaller batch size
python scripts/sync_organization_filings.py --batch-size 25
```

### 3. `check_enrichment_results.py`
Helper script to analyze enrichment results:
- Shows enrichment statistics
- Displays examples of good enrichments
- Shows state distribution of enriched organizations
- Can show sample Apollo data structure

#### Usage:
```bash
# Check general statistics
python scripts/check_enrichment_results.py

# Show sample Apollo data structure
python scripts/check_enrichment_results.py --sample
```

### 4. `check_filing_results.py`
Helper script to analyze filing sync results:
- Shows filing statistics (total filings, form types, years)
- Displays organizations with most filings
- Shows which organizations still need filing sync
- Sample filing data with financial information

#### Usage:
```bash
# Check general filing statistics
python scripts/check_filing_results.py

# Show sample filing data
python scripts/check_filing_results.py --sample

# Show organizations that need filing sync
python scripts/check_filing_results.py --need-sync
```

## Configuration

The scripts use the same environment variables as the main application:
- `DATABASE_URL`: PostgreSQL database connection
- `APOLLO_API_KEY`: Apollo.io API key
- `PROPUBLICA_API_BASE_URL`: ProPublica API base URL

Make sure your `.env` file is properly configured.

## States Priority

Primary state: **California (CA)**

Fallback states (in order):
- New York (NY)
- Texas (TX)  
- Florida (FL)
- Illinois (IL)
- Pennsylvania (PA)
- Ohio (OH)
- Georgia (GA)
- North Carolina (NC)
- Michigan (MI)
- New Jersey (NJ)

## Output

The script will:
1. Log progress to console
2. **Store ALL fetched organizations to the `organizations` table first**
3. Then enrich stored organizations with Apollo (1.5 second delay between calls)
4. Save Apollo enrichment data to the `organization_enrichments` table
5. Set `apollo_searched=True` and `apollo_enriched=True` for good enrichments
6. Skip Firecrawl website scraping (`website_scraped=False`)

## Error Handling

- **Apollo rate limiting: 1.5 second delay between calls** to avoid "too many requests" errors
- ProPublica API rate limiting: 0.1 second delay between requests
- Duplicate organizations: Checks for existing EINs
- Failed enrichments: Logged but don't stop the process
- Database errors: Rolled back with error logging

## Monitoring

Use the check script to monitor progress:
```bash
# Check how many good organizations you have so far
python scripts/check_enrichment_results.py
```
