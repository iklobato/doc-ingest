# Doc Ingest

## Background

Eve is an AI assistant for Plaintiff law, specializing in Personal Injury and Labor & Employment. Plaintiff matters are typically 1:1 with individual clients. This project automates the ingestion of invoice document data into Eve.

Each invoice PDF contains a "Bill To" field representing the client's name. The automation:
1. Extracts the client name from each invoice
2. Creates a matter in Eve for each unique client
3. Uploads each invoice to the appropriate matter

## Requirements

- Extract "Bill To" client name from each PDF invoice
- Create a matter in Eve API for each distinct client (matter name = client name)
- Upload each invoice to the matching matter via Eve API
- Use Python
- Use sensitive `.env` for API credentials (never commit)
- Docker Compose for local execution

## What Was Built

### Core Functionality

| Step | Description |
|------|-------------|
| 1 | Scan `/files/file_*.pdf` for invoice PDFs |
| 2 | Extract "Bill To" client name from each PDF using `pdfplumber` |
| 3 | Group files by unique client name |
| 4 | Create/verify matter in Eve API for each client |
| 5 | Upload each invoice to its matter via the 3-step document sync process |

### Eve API Integration

The document upload uses a 3-step process:
1. `POST /v1/documents/batch-sync` - Get signed upload URL
2. `PUT` file to signed URL
3. `POST /v1/documents/confirm-upload` - Finalize upload

### Architecture

```
doc-ingest/
├── main.py         # Orchestration (depends on abstraction)
├── config.py       # Settings (reads from .env)
├── models.py       # Data classes: Client, Invoice, UploadResult
├── services.py     # MatterService Protocol + EveMatterService
├── extractors.py   # PDF extraction only
├── utils.py        # slugify() helper
├── Dockerfile      # Docker image definition
├── docker-compose.yml
├── .env            # Sensitive config (gitignored)
├── .env.example    # Template for users
├── .gitignore      # Excludes .env
└── requirements.txt
```

### Code Patterns

- **Imports at top** - All imports moved to module top level
- **Early returns** - Functions use guard clauses and early returns for cleaner flow
- **Type hints** - Not added per user request

## Setup

### Prerequisites

- Python 3.11+ (or Docker)
- API key from Eve

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Copy env template and add your API key
cp .env.example .env
# Edit .env with your EVE_API_KEY

# Run
python main.py
```

### Docker Compose

```bash
# Build and run
docker compose up --build

# Or run detached
docker compose up -d --build
```

The `./files` directory is mounted to `/app/files` in the container. Place your PDF invoices there.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EVE_API_KEY` | Bearer token for Eve API | (required) |
| `EVE_API_URL` | Base URL for API | `https://staging.eve.legal/api` |
| `USER_EMAIL` | Email to associate with matters | (required) |
| `FILES_DIR` | Directory containing PDFs | `/app/files` |
| `INVOICE_PATTERN` | Glob pattern for invoices | `file_*.pdf` |

## Files

- **config.py** - Configuration loader from environment
- **extractors.py** - PDF text extraction using `pdfplumber`
- **services.py** - Eve API client with MatterService Protocol
- **models.py** - Dataclasses: Client, Invoice, UploadResult
- **utils.py** - Helper: slugify() for creating URL-safe matter IDs
- **main.py** - Main orchestration: scan → extract → create matters → upload

## API Reference

Base URL: `https://staging.eve.legal/api`

### Endpoints Used

- `PUT /v1/matters/{external_matter_id}` - Create/update matter
- `POST /v1/documents/batch-sync` - Get signed upload URL
- `POST /v1/documents/confirm-upload` - Confirm document upload
- `GET /v1/matters` - List matters
- `GET /v1/documents` - List documents

## Notes

- The script is idempotent - running multiple times will skip already-uploaded documents
- Matter IDs are URL-safe slugs derived from client names (e.g., "John Smith" → "john-smith")
- Documents are matched by filename (e.g., "file_001.pdf")