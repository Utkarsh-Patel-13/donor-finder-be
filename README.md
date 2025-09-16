# Donor Finder Backend API

A comprehensive FastAPI application for finding and managing nonprofit donor/foundation data with advanced semantic search and enrichment capabilities.

## 🚀 Features

### Core Functionality
- **Data Ingestion**: Sync real foundation/grantmaker data from ProPublica Nonprofit Explorer API
- **Semantic Search**: Natural language search using sentence transformers and vector embeddings
- **Data Enrichment**: Enhance organization profiles with website scraping (Firecrawl) and contact data (Apollo.io)
- **Vector Storage**: Store embeddings in PostgreSQL with pgvector extension for fast similarity search
- **Hybrid Search**: Combines semantic similarity with traditional keyword matching
- **NTEE Code Expansion**: Comprehensive mapping of NTEE codes to descriptive keywords
- **Geographic Filtering**: Location-based search with state name expansion

### Technical Features
- **RESTful API**: Complete FastAPI with interactive Swagger documentation
- **Database Migrations**: Alembic for schema versioning and migrations  
- **Health Checks**: Built-in health monitoring for services
- **Docker Support**: Full containerization with docker-compose
- **Background Processing**: Batch operations for data sync and embedding generation

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │────│   PostgreSQL    │    │   External APIs │
│                 │    │                 │    │                 │
│  • Organizations│    │  • Organizations│    │  • ProPublica   │
│  • Semantic     │    │  • Filings      │    │  • Firecrawl    │
│  • Enrichment   │    │  • Enrichments  │    │  • Apollo.io    │
│  • Sync         │    │  • Embeddings   │    │                 │
│                 │    │  + pgvector     │    │                 │
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

## 🐳 Quick Start with Docker (Recommended)

### Prerequisites
- Docker and Docker Compose
- Optional: API keys for enrichment features

### 1. Clone and Setup
```bash
# Clone the repository
git clone <repository-url>
cd donor_finder_backend

# Create environment file (optional for basic functionality)
cp .env.example .env
# Edit .env with your API keys if you want enrichment features
```

### 2. Start Services
```bash
# Start all services (database + API)
docker-compose up -d

# Check service health
docker-compose ps
docker-compose logs -f app

# API will be available at http://localhost:8000
```

### 3. Initialize with Sample Data
```bash
# Sync sample organizations from California
curl -X POST "http://localhost:8000/api/v1/sync/search-and-sync?state=CA&max_orgs=5&c_code=3"

# Generate embeddings for semantic search
curl -X POST "http://localhost:8000/api/v1/semantic-search/update-embeddings?batch_size=50"

# Check stats
curl "http://localhost:8000/api/v1/stats"
```

## 💻 Local Development Setup

### Prerequisites
- Python 3.11+
- PostgreSQL with pgvector extension

### 1. Database Setup
```bash
# Start only the database
docker-compose up -d db

# Or install PostgreSQL with pgvector manually
# Follow: https://github.com/pgvector/pgvector#installation
```

### 2. Python Environment
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
```bash
# Create .env file
DATABASE_URL=postgresql://donor_user:donor_password@localhost:5432/donor_finder_db
PROPUBLICA_API_BASE_URL=https://projects.propublica.org/nonprofits/api/v2
DEBUG=true

# Optional: Add API keys for enrichment features
FIRECRAWL_API_KEY=your_firecrawl_api_key_here
APOLLO_API_KEY=your_apollo_api_key_here
```

### 4. Database Migration
```bash
# Run migrations to create tables
alembic upgrade head
```

### 5. Start Application
```bash
# Development server with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python module
python -m uvicorn app.main:app --reload
```

## 📚 API Documentation

Visit **http://localhost:8000/docs** for interactive Swagger documentation with examples and schema details.

### Core Endpoints

#### Data Management
- `GET /api/v1/organizations/` - Search organizations with filters
- `GET /api/v1/organizations/{ein}` - Get organization details by EIN
- `POST /api/v1/sync/organization/{ein}` - Sync specific organization
- `POST /api/v1/sync/search-and-sync` - Bulk sync organizations

#### Semantic Search
- `GET /api/v1/semantic-search/` - Natural language search
- `GET /api/v1/semantic-search/suggest` - Get search suggestions
- `POST /api/v1/semantic-search/update-embeddings` - Generate embeddings
- `GET /api/v1/semantic-search/explain` - Explain query processing

#### Enrichment
- `POST /api/v1/enrichment/organization/{id}` - Enrich organization data
- `GET /api/v1/enrichment/organization/{id}` - Get enrichment data
- `GET /api/v1/enrichment/organization/{id}/status` - Check enrichment status
- `GET /api/v1/enrichment/stats` - Enrichment statistics
- `POST /api/v1/enrichment/bulk-enrich` - Bulk enrichment

#### System
- `GET /` - API overview and examples
- `GET /api/v1/health` - Health check
- `GET /api/v1/stats` - Database statistics
- `GET /api/v1/recent-filings` - Recent organization filings

### Example API Usage

#### Search Organizations
```bash
# Basic search
curl "http://localhost:8000/api/v1/organizations/?name=foundation&state=CA&limit=10"

# Semantic search with natural language
curl "http://localhost:8000/api/v1/semantic-search/?query=foundations%20supporting%20education%20in%20California&limit=10"
```

#### Sync Data
```bash
# Sync specific organization by EIN
curl -X POST "http://localhost:8000/api/v1/sync/organization/123456789"

# Bulk sync organizations from California
curl -X POST "http://localhost:8000/api/v1/sync/search-and-sync?state=CA&max_orgs=100&c_code=3"
```

#### Enrichment
```bash
# Enrich organization with external data
curl -X POST "http://localhost:8000/api/v1/enrichment/organization/1"

# Check enrichment status
curl "http://localhost:8000/api/v1/enrichment/organization/1/status"
```

## 🔧 Configuration

### Environment Variables
Create a `.env` file in the project root:

```bash
# Database Configuration (Required)
DATABASE_URL=postgresql://donor_user:donor_password@localhost:5432/donor_finder_db

# API Configuration
PROPUBLICA_API_BASE_URL=https://projects.propublica.org/nonprofits/api/v2
DEBUG=true

# External API Keys (Optional - for enrichment features)
# Firecrawl: Get from https://firecrawl.dev (free: 500 scrapes/month)
FIRECRAWL_API_KEY=your_firecrawl_api_key_here

# Apollo.io: Get from https://apollo.io (free: 100 enrichments/month)  
APOLLO_API_KEY=your_apollo_api_key_here
```

### Docker Environment Variables
The `docker-compose.yml` automatically uses environment variables from `.env` file or defaults.

## 🗂️ Project Structure

```
donor_finder_backend/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── models/                 # Database models
│   │   ├── database.py         # Database configuration and settings
│   │   ├── organization.py     # Organization model
│   │   ├── filing.py          # Filing model
│   │   └── enrichment.py      # Enrichment model
│   ├── routers/               # API route handlers
│   │   ├── organizations.py   # Organization endpoints
│   │   ├── sync.py           # Data synchronization endpoints  
│   │   ├── semantic_search.py # Semantic search endpoints
│   │   └── enrichment.py     # Enrichment endpoints
│   ├── schemas/              # Pydantic schemas for API
│   │   ├── organization.py   
│   │   ├── filing.py
│   │   └── enrichment.py
│   └── services/             # Business logic services
│       ├── database_service.py    # Database operations
│       ├── propublica_api.py     # ProPublica API integration
│       ├── embedding_service.py  # Vector embedding generation
│       ├── ntee_service.py       # NTEE code mapping
│       ├── firecrawl_services.py # Website scraping
│       └── apollo_service.py     # Contact enrichment
├── alembic/                  # Database migrations
├── scripts/                  # Utility scripts
├── docker-compose.yml        # Docker services configuration
├── Dockerfile               # Application container
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## 🧠 Implementation Details

### Data Models

#### Organization
- **Source**: ProPublica Nonprofit Explorer API
- **Fields**: EIN, name, address, NTEE codes, revenue, assets
- **Enrichment**: Website content, contact information
- **Search**: Full-text search + semantic vector search

#### Filing  
- **Source**: IRS Form 990 data via ProPublica
- **Fields**: Tax year, form type, revenue, expenses, assets
- **Usage**: Financial analysis and organization validation

#### Enrichment
- **Website Scraping**: Firecrawl for leadership and contact info
- **Contact Enrichment**: Apollo.io for verified business contacts
- **Storage**: Structured JSON data with metadata

### Semantic Search Implementation

#### Vector Embeddings
- **Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Dimension**: 384-dimensional vectors
- **Storage**: PostgreSQL with pgvector extension
- **Indexing**: HNSW index for fast similarity search

#### Search Strategy
1. **Query Processing**: Extract location, keywords, NTEE codes
2. **NTEE Expansion**: Map codes to descriptive keywords
3. **Geographic Expansion**: Handle state names and abbreviations
4. **Vector Search**: Semantic similarity using cosine distance
5. **Hybrid Ranking**: Combine vector similarity with keyword relevance

#### Performance Optimization
```sql
-- Create vector index for fast similarity search
CREATE INDEX ON organizations USING hnsw (embedding vector_cosine_ops);

-- Full-text search index
CREATE INDEX ON organizations USING gin(searchable_text);
```

### Data Enrichment Pipeline

#### Website Scraping (Firecrawl)
1. Extract organization website from ProPublica data
2. Scrape website content for leadership and contact information
3. Parse structured data (names, titles, emails, phone numbers)
4. Store in `organization_enrichments` table

#### Contact Enrichment (Apollo.io)
1. Use scraped leadership names and organization info
2. Query Apollo.io B2B database for verified contact details
3. Enhance with social profiles, verified emails, phone numbers
4. Store enriched contact data with confidence scores

### Database Schema

#### Key Tables
- `organizations`: Core organization data with vector embeddings
- `filings`: IRS Form 990 filing data
- `organization_enrichments`: Scraped and enriched contact data

#### Migration Management
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Check current version
alembic current
```

## 🔍 Usage Examples

### Semantic Search Queries
```bash
# Education-focused foundations
curl "http://localhost:8000/api/v1/semantic-search/?query=foundations%20supporting%20early%20childhood%20education%20in%20California"

# Environmental organizations
curl "http://localhost:8000/api/v1/semantic-search/?query=environmental%20organizations%20in%20New%20York"

# Disaster relief nonprofits
curl "http://localhost:8000/api/v1/semantic-search/?query=disaster%20relief%20nonprofits"

# Youth development programs
curl "http://localhost:8000/api/v1/semantic-search/?query=youth%20development%20programs%20in%20Texas"
```

### Data Synchronization
```bash
# Sync organizations from multiple states
for state in CA NY TX FL; do
  curl -X POST "http://localhost:8000/api/v1/sync/search-and-sync?state=$state&max_orgs=50&c_code=3"
done

# Update embeddings for new organizations
curl -X POST "http://localhost:8000/api/v1/semantic-search/update-embeddings?batch_size=100"
```

## 🚀 Production Deployment

### Docker Production
```bash
# Build production image
docker build -t donor-finder-api .

# Run with production settings
docker run -d \
  --name donor-finder-api \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  -e FIRECRAWL_API_KEY=your_key \
  -e APOLLO_API_KEY=your_key \
  donor-finder-api
```

### Performance Tuning
```sql
-- Database optimization
ANALYZE organizations;
VACUUM ANALYZE organizations;

-- Index monitoring
SELECT schemaname, tablename, indexname, idx_scan 
FROM pg_stat_user_indexes 
WHERE schemaname = 'public';
```

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes and add tests
4. Commit changes: `git commit -m 'Add amazing feature'`
5. Push to branch: `git push origin feature/amazing-feature`
6. Open a Pull Request

### Code Style
- Follow PEP 8 for Python code
- Use type hints for function signatures
- Add docstrings for public functions
- Keep functions focused and testable

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health
- **API Stats**: http://localhost:8000/api/v1/stats

For issues and questions, please open a GitHub issue with detailed information about your setup and the problem you're experiencing.