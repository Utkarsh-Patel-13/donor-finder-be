# Donor Finder API with Semantic Search

A FastAPI application that syncs nonprofit organization data from ProPublica and provides semantic search capabilities for finding relevant donors and foundations using natural language queries.

## Features

- **Data Ingestion**: Pull real foundation/grantmaker data from ProPublica Nonprofit Explorer API
- **Semantic Search**: LLM-backed natural language search using sentence transformers
- **Vector Storage**: Store embeddings in PostgreSQL with pgvector extension
- **Hybrid Search**: Combines semantic similarity with traditional keyword matching
- **NTEE Expansion**: Comprehensive mapping of NTEE codes to descriptive keywords
- **Geographic Filtering**: Location-based search with state name expansion
- **RESTful API**: Complete API with interactive documentation

## Quick Start

### 1. Start with Docker (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd donor_finder

# Start database and application
docker-compose up -d

# Check if services are running
docker-compose logs -f app
```

### 2. Or Run Locally

```bash
# Start database only
docker-compose up -d db

# Install Python dependencies
pip install -r requirements.txt

# Run application
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Initialize Data

```bash
# Sync sample organizations (5 from California)
curl -X POST "http://localhost:8000/api/v1/sync/search-and-sync?state=CA&max_orgs=5&c_code=3"

# Generate embeddings for semantic search
curl -X POST "http://localhost:8000/api/v1/semantic-search/update-embeddings?batch_size=50"
```

## API Endpoints

### Core Data Operations
- `GET /api/v1/organizations/` - Search organizations with filters
- `GET /api/v1/organizations/{ein}` - Get organization details by EIN
- `POST /api/v1/sync/organization/{ein}` - Sync specific organization
- `POST /api/v1/sync/search-and-sync` - Bulk sync organizations

### Semantic Search
- `GET /api/v1/semantic-search/` - Natural language search
- `GET /api/v1/semantic-search/suggest` - Get search suggestions
- `POST /api/v1/semantic-search/update-embeddings` - Generate embeddings
- `GET /api/v1/semantic-search/explain` - Explain query processing

### Utilities
- `GET /api/v1/health` - Health check
- `GET /api/v1/stats` - Database statistics
- `GET /docs` - Interactive API documentation

## Semantic Search Usage

### Natural Language Queries

```bash
# Early childhood education in California
curl "http://localhost:8000/api/v1/semantic-search/?q=foundations%20supporting%20early%20childhood%20education%20in%20California&limit=5"

# Environmental organizations
curl "http://localhost:8000/api/v1/semantic-search/?q=environmental%20conservation%20nonprofits&search_type=hybrid"

# Youth development programs
curl "http://localhost:8000/api/v1/semantic-search/?q=youth%20development%20programs%20in%20Texas&limit=10"
```

### Search Types

- **`hybrid`** (default): Combines semantic similarity with keyword matching
- **`semantic`**: Pure vector similarity search
- **`keyword`**: Traditional text-based search

### Query Components Detected

The system automatically extracts:
- **Geographic terms**: "California", "NY", "San Francisco" → state filters
- **Cause areas**: "education", "environment", "health" → NTEE code filters
- **Organization types**: "foundation", "nonprofit", "charity"

## How Semantic Search Works

### 1. Data Preparation
- Organization data is enriched with NTEE code descriptions
- Searchable text combines: name + NTEE keywords + location + organization type
- Text is converted to 384-dimensional embeddings using `all-MiniLM-L6-v2`

### 2. Search Process
- User query is converted to embedding vector
- Cosine similarity computed against all organization embeddings
- Results filtered by geographic/categorical constraints
- Hybrid scoring combines semantic + keyword relevance

### 3. NTEE Code Expansion
```
NTEE B21 → "preschool early childhood education child development"
NTEE P20 → "disaster relief emergency response humanitarian aid"
NTEE C30 → "natural resources conservation wildlife"
```

## Example Usage

```python
import httpx

async def search_example():
    async with httpx.AsyncClient() as client:
        # Natural language search
        response = await client.get(
            "http://localhost:8000/api/v1/semantic-search/",
            params={
                "q": "foundations supporting early childhood education in California",
                "search_type": "hybrid",
                "limit": 10
            }
        )
        
        results = response.json()
        for result in results['results']:
            print(f"{result['name']} - Score: {result['relevance_score']:.3f}")
```

Run the example script:
```bash
python usage_example.py
```

## Database Schema

### Organizations Table
- Core nonprofit data from ProPublica API
- `searchable_text`: Expanded descriptive text
- `embedding`: 384-dimensional vector for similarity search

### Filings Table
- Form 990 financial data
- Linked to organizations via foreign key
- Financial metrics and PDF links

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │────│  Database Svc   │────│  PostgreSQL     │
│                 │    │                 │    │  + pgvector     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │
         │              ┌─────────────────┐    ┌─────────────────┐
         │              │  Embedding Svc  │────│ sentence-trans. │
         │              │                 │    │ all-MiniLM-L6   │
         │              └─────────────────┘    └─────────────────┘
         │
┌─────────────────┐    ┌─────────────────┐
│ ProPublica API  │────│     NTEE        │
│     Service     │    │    Service      │
└─────────────────┘    └─────────────────┘
```

## Configuration

Environment variables in `.env`:
```bash
DATABASE_URL=postgresql://donor_user:donor_password@localhost:5432/donor_finder_db
PROPUBLICA_API_BASE_URL=https://projects.propublica.org/nonprofits/api/v2
DEBUG=true
```

## Development

### Adding New NTEE Mappings
Edit `app/services/ntee_service.py` to add new NTEE code descriptions:

```python
"B99": "education other specialized programs"
```

### Improving Search Quality
1. Enhance NTEE descriptions with more synonyms
2. Add geographic aliases (e.g., "Bay Area" → ["San Francisco", "Oakland"])  
3. Tune similarity thresholds in `semantic_search_organizations()`
4. Experiment with different embedding models

### Performance Optimization
- Create vector indices: `CREATE INDEX ON organizations USING hnsw (embedding vector_cosine_ops);`
- Batch embedding generation during sync
- Cache frequent queries
- Use approximate search for large datasets

## API Documentation

Visit http://localhost:8000/docs for interactive API documentation with examples and schema details.

## License

MIT License - see LICENSE file for details.