# Multi-Tenant Change Data Management System (CDMS) & Unified Mock Platform

[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D.svg)](https://redis.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An enterprise-grade **Change Data Management System (CDMS)** designed for multi-tenant environments. The platform synchronizes product and inventory data from heterogeneous data sources (**Shopify PULL** via scheduled cron batches and **Vietful PUSH** via real-time messaging) into isolated per-tenant databases and a unified global master product database.

---

## 🌟 Key System Capabilities

- **Multi-Tenant Data Isolation**: Tenant product data is isolated into dynamic PostgreSQL tables (`products_{tenant_id}`) to ensure strict tenant boundaries.
- **Heterogeneous Connector Modes**:
  - **Vietful Connector (PUSH Mode)**: Event-driven subscriber maintaining persistent connection to Redis Pub/Sub channels (`vietful_tenant_{tenant_id}`) for real-time inventory updates.
  - **Shopify Connector (PULL Mode)**: Each worker stores its tenant-specific mock endpoint in `worker_configs.config_json.domain`. The mock keeps a separate product collection per tenant. A scheduled worker fetches consecutive batches of **5 products**, saves `last_since_id` after each completed batch, and resumes from that cursor after a restart. An empty response resets the cursor to `0` for the next cron run.
- **Unified Data Normalization Engine (`DataNormalizer`)**: Transforms raw, diverse JSON payloads from Shopify (nested GraphQL/REST schemas) and Vietful (flat inventory push events) into a standardized `UnifiedProduct` model before persistence.
- **Deduplication & Master Product Storage**: Implements PostgreSQL `UPSERT` (`ON CONFLICT DO UPDATE`) logic. Tenant tables deduplicate by SKU; the shared `master_products` table uses the composite `(barcode, sku)` key, so only an identical barcode and SKU pair is updated while either value may appear in multiple master products.
- **Worker Lifecycle & Checkpointing**:
  - Full CRUD control over workers (Create, Start, Stop, Delete).
  - Resilient checkpointing storing `last_since_id` and `last_event_id`.
  - **Automatic Startup Recovery**: Restores and re-activates all `RUNNING` workers directly from PostgreSQL (`worker_configs`) upon application startup.
- **Built-in Local Mock Services & Pre-Seeded Data**:
  - Built-in unified Mock APIs for both Shopify and Vietful.
  - **Pre-seeded with 15 dummy Shopify products for `tenant01`** and 15 dummy Vietful events on application startup. Other Shopify tenants start with an empty mock catalog.
- **Structured JSON Logging**: Enterprise-ready JSON logging for all system events, API requests, and worker execution logs.

---

## 📐 System Architecture

```text
                                   +------------------------------------+
                                   |          CDMS PLATFORM             |
                                   |                                    |
+--------------------------+       |   +----------------------------+   |       +------------------------------------+
|  Shopify Mock Service    | <====== PULL = ShopifyWorker (Cron)    |   | =====>|  Tenant DB: products_{tenant_id}   |
|  (HTTP GET Batch = 5)    |       |   |  - Batch Size: 5 items     |   |       |  (Strict Tenant Isolation)         |
+--------------------------+       |   |  - Checkpoint: since_id    |   |       +------------------------------------+
                                   |   +-------------+--------------+   |                          ||
                                   |                 |                  |                          ||
+--------------------------+       |                 v                  |                          || UPSERT
|  Vietful Mock Service    |       |   +----------------------------+   |                          || (ON CONFLICT)
|  (Redis Pub/Sub Channel) | ===== PUSH => VietfulWorker (Subscriber) |   |                          v
+--------------------------+       |   |  - Real-time Listener      |   |       +------------------------------------+
                                   |   |  - Checkpoint: event_id    |   |       |   Master Database: master_products |
                                   |   +-------------+--------------+   |       |   (Global Deduplicated View)       |
                                   |                 |                  |       +------------------------------------+
                                   |                 v                  |
                                   |   +----------------------------+   |
                                   |   |   DataNormalizer Engine    |   |
                                   |   | (Maps to UnifiedProduct)   |   |
                                   |   +----------------------------+   |
                                   +------------------------------------+
```

---

## 📋 Architecture Decision Record (ADR)

### ADR 1: Tenant Data Isolation via Dynamic Tables
- **Decision**: Store tenant data in dedicated PostgreSQL tables named `products_{tenant_id}` rather than a shared table with a `tenant_id` column.
- **Rationale**: Meets the strict non-negotiable requirement of the assignment ("Data of different tenants is not stored in the same table"), guarantees zero data leakage risk between tenants, and allows per-tenant index optimization.

### ADR 2: Unified Data Normalization Layer (`DataNormalizer`)
- **Decision**: Require all incoming data payloads (regardless of source) to pass through a stateless `DataNormalizer` module before hitting the database.
- **Rationale**: Decouples connector-specific payload parsing from database persistence logic, allowing new data sources to be added without altering database schemas.

### ADR 3: State-Driven Worker Lifecycle with Database-Backed Checkpoints
- **Decision**: Store worker configurations, schedules, and cursor states inside the `worker_configs` PostgreSQL table.
- **Rationale**: Ensures high resiliency. If the CDMS service restarts or crashes, the `WorkerManager` queries the database during the FastAPI startup lifespan and seamlessly resumes active workers from their last saved checkpoints.

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Language & Web Framework** | Python 3.13+, FastAPI, Uvicorn |
| **Database & ORM** | PostgreSQL 15, SQLAlchemy 2.0 (AsyncIO & Sync), Asyncpg |
| **Database Migrations** | Alembic |
| **In-Memory & Messaging** | Redis 7, redis-py (Pub/Sub) |
| **Scheduling Engine** | APScheduler (AsyncIOScheduler) |
| **HTTP Client** | HTTPX (Async HTTP Client) |
| **Containerization** | Docker & Docker Compose |
| **Logging** | Structured JSON Logger (`JSONFormatter`) |

---

## 🚀 Quick Start Guide (Local Setup)

### 1. Prerequisites
Ensure you have the following installed on your machine:
- **Docker & Docker Compose**
- **Python 3.13+** and `pip`

### 2. Clone Repository & Setup Environment
```bash
git clone https://github.com/thoaiky1992/ksynerx
cd ksynerx
```

Create `.env` file (already configured for local docker defaults):
```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=cdms_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cdms_db
SYNC_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/cdms_db

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379/0

PORT=8001
LOG_LEVEL=INFO
```

### 3. Start Whole Platform (1-Click Docker Launch)
Build and start PostgreSQL, Redis, and CDMS Application container:
```bash
docker compose up --build -d
```

Verify containers are running smoothly:
```bash
docker compose ps
```

The application will automatically wait for PostgreSQL, run Alembic database migrations, seed initial dummy data (15 Shopify & 15 Vietful items), and start listening on port `8001`!

### 4. Alternative: Run Application Locally (Without Containerizing App)
If you prefer running Python directly on your host machine while using Docker for Postgres & Redis:
```bash
# 1. Start Postgres & Redis only
docker compose up -d postgres redis

# 2. Install dependencies & run migrations
python3 -m pip install -r requirements.txt
python3 -m alembic upgrade head

# 3. Start FastAPI application
python3 -m uvicorn app.main:app --port 8001 --reload
```

---

## 🧪 Interactive Testing Guide

You can test all endpoints using **Swagger UI** (`http://localhost:8001/docs`) or directly via **cURL commands** in your terminal:

### 1. System Health Check
```bash
curl -s http://localhost:8001/
```

### 2. Mock Services (Shopify & Vietful Product Management)

- **Fetch Shopify Products (PULL Batch size = 5)**:
  ```bash
  curl -s "http://localhost:8001/mock/shopify/admin/api/tenant01/products.json?since_id=0&limit=5"
  ```

- **Create a New Product on Shopify Mock for `tenant01`**:
  ```bash
  curl -X POST "http://localhost:8001/mock/shopify/tenant01/products" \
    -H "Content-Type: application/json" \
    -d '{
      "title": "Air Jordan 1 Retro High",
      "vendor": "Nike",
      "product_type": "Footwear",
      "variants": [
        {
          "sku": "NK-AJ1-RED-42",
          "price": "4500000",
          "inventory_quantity": 30,
          "barcode": "888999111222",
          "weight": 0.8
        }
      ]
    }'
  ```

- **Trigger/Push New Inventory Product Event on Vietful Mock (Publishes Event via Redis)**:
  ```bash
  curl -X POST "http://localhost:8001/mock/vietful/inventory-event" \
    -H "Content-Type: application/json" \
    -d '{
      "tenant_code": "tenant01",
      "product_code": "VF-SKU-999",
      "product_name": "Premium Running Shoes",
      "barcode": "999888777666",
      "brand_name": "Nike",
      "category_name": "Footwear",
      "quantity": 150,
      "weight_kg": 0.6,
      "corrupt_data": false
    }'
  ```

- **Simulate Corrupted/Invalid Vietful Event (Testing Error Handling)**:
  ```bash
  curl -X POST "http://localhost:8001/mock/vietful/inventory-event" \
    -H "Content-Type: application/json" \
    -d '{
      "tenant_code": "tenant01",
      "product_code": "",
      "product_name": "Corrupt Item",
      "barcode": "000000",
      "quantity": 0,
      "corrupt_data": true
    }'
  ```

### 3. Worker Management APIs

- **List All Workers**:
  ```bash
  curl -s http://localhost:8001/api/workers
  ```

- **Create a Shopify Worker (PULL, Cron Scheduled, Batch size = 5)**:
  ```bash
  curl -X POST "http://localhost:8001/api/workers" \
    -H "Content-Type: application/json" \
    -d '{
      "worker_id": "worker-shopify-tenant01",
      "tenant_id": "tenant01",
      "source_type": "SHOPIFY",
      "schedule_cron": "*/1 * * * *",
      "domain": "http://localhost:8001/mock/shopify/admin/api/tenant01/products.json"
    }'
  ```

  The `domain` value is saved in `worker_configs.config_json` and must contain the same `tenant_id` as the worker. If omitted, the application generates this URL using `PORT`. Existing Shopify workers without a saved domain also use the generated URL. This endpoint is a local tenant-scoped mock, not Shopify's production GraphQL API.

- **Create a Vietful Worker (PUSH, Real-Time Redis Subscriber)**:
  ```bash
  curl -X POST "http://localhost:8001/api/workers" \
    -H "Content-Type: application/json" \
    -d '{
      "worker_id": "worker-vietful-tenant01",
      "tenant_id": "tenant01",
      "source_type": "VIETFUL"
    }'
  ```

- **Start Worker**:
  ```bash
  curl -X POST "http://localhost:8001/api/workers/worker-shopify-tenant01/start"
  curl -X POST "http://localhost:8001/api/workers/worker-vietful-tenant01/start"
  ```

- **Stop Worker**:
  ```bash
  curl -X POST "http://localhost:8001/api/workers/worker-shopify-tenant01/stop"
  ```

- **Delete Worker**:
  ```bash
  curl -X DELETE "http://localhost:8001/api/workers/worker-shopify-tenant01"
  ```

---

## 📁 Repository Structure

```text
.
├── app/
│   ├── core/
│   │   ├── config.py         # Environment & Application Settings
│   │   ├── database.py       # SQLAlchemy Async/Sync Engines & Sessions
│   │   └── logger.py         # Custom Structured JSON Logging Formatter
│   ├── engine/
│   │   ├── base_worker.py    # Abstract Base Worker & PostgreSQL UPSERT Logic
│   │   ├── normalizer.py    # Data Normalizer (Shopify & Vietful -> UnifiedProduct)
│   │   ├── shopify_worker.py # Shopify Cron Scheduled Worker (Batch 5 items)
│   │   ├── vietful_worker.py # Vietful Event Listener Worker (Redis Pub/Sub)
│   │   └── worker_manager.py # Worker Lifecycle Manager & DB Startup Recovery
│   ├── mock/
│   │   ├── schemas/          # Pydantic Schemas for External Payloads
│   │   └── services/         # Mock Storage & Local Dummy Seed Generator (15 items)
│   ├── models/
│   │   ├── product.py        # MasterProduct Model & Dynamic Tenant Product Table Builder
│   │   └── worker.py         # WorkerConfig ORM Model
│   ├── routers/
│   │   ├── shopify_router.py # REST API for Shopify Mock Service
│   │   ├── vietful_router.py # REST API for Vietful Mock Service
│   │   └── worker_router.py  # REST API for Worker CRUD Operations
│   └── main.py               # Application Entrypoint & Lifespan Bootstrapping
├── alembic/                  # Alembic Database Migration Scripts
├── docker-compose.yml        # Docker infrastructure (PostgreSQL & Redis)
├── requirements.txt          # Python Dependencies
├── .env                      # Environment Variables
└── README.md                 # System Documentation
```

---

## 📜 License

This project is submitted for technical evaluation under the **MIT License**. All rights reserved.
