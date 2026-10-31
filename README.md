# Fintech Engineer Take-Home Assessment
## Apache Fineract (Java/Spring Boot) + Python ERP and Integration: Reliable Financial Integration

**Candidate:** Bantayehu Man  
**Position:** Fineract Developer – Inkomoko  
**Submission deadline:** Saturday 31st October 2026, 23:00  

### Tiers Completed
- [x] **Tier 1 – Core (Parts A–G)** – required
- [x] **Tier 2 – Reliability (Parts H–K)** – required
- [ ] **Tier 3 – Stretch (Part L)** – optional (partial: accounting mapping unit tests + reconciliation outcomes)

### Pinned Versions
| Component              | Version / Tag      | Notes                                      |
|------------------------|--------------------|--------------------------------------------|
| Apache Fineract        | **1.15.0**         | Official release tag                       |
| JDK                    | **21**             | Required by Fineract 1.15+                 |
| Build tool             | Gradle (upstream)  |                                            |
| Python                 | **3.12**           |                                            |
| FastAPI                | latest stable      | Chosen for async, OpenAPI, type safety     |
| PostgreSQL             | **16**             |                                            |
| Docker Compose         | 2.x                | One-command start                          |

### Quick Start
```bash
# Clone / extract the submission
cd fintech-fineract-assessment

# Build the customized Fineract image (first time only – takes several minutes)
./scripts/build-fineract.sh

# Start everything
docker compose up -d --build

# Wait for health
./scripts/wait-for-services.sh

# Seed Fineract (office, currency, loan product, API user)
./scripts/seed-fineract.sh

# Run simulations
make simulate-core
make simulate-duplicates
make simulate-concurrency
make simulate-failures
make simulate-reconciliation
```

### Running Tests
```bash
# Java (inside fineract-customization or via the built image)
./scripts/run-java-tests.sh

# Python
cd integration-service && pytest -q --cov=app
cd ../mock-erp && pytest -q --cov=app
```

### Repository Layout
```
fintech-fineract-assessment/
├── README.md
├── ARCHITECTURE.md
├── API.md
├── SIMULATIONS.md
├── DECISIONS.md
├── docker-compose.yml
├── fineract-customization/          # Java patch, Liquibase, JUnit tests, Dockerfile
├── integration-service/             # FastAPI Integration Service
├── mock-erp/                        # FastAPI Mock ERP
├── fineract/configuration/          # seed scripts, office/product JSON
├── scripts/                         # build, seed, simulate helpers
├── evidence/                        # simulation outputs
└── postman/                         # collection
```

### Evidence of Java Work
- Patch against tag `1.15.0` lives in `fineract-customization/`
- Liquibase migration adds `external_reference` (unique) to `acc_gl_account`
- New / extended command handler enforces idempotent create + conflict semantics
- JUnit unit + integration tests included
- Custom Docker image is built from source with the patch applied

### Language Ownership
- **Fineract customization** → pure Java / Spring Boot (inside the Fineract codebase)
- **Mock ERP** → Python + FastAPI
- **Integration Service** → Python + FastAPI
- No thin wrappers used to satisfy either requirement.

See `ARCHITECTURE.md`, `API.md`, `DECISIONS.md` and `SIMULATIONS.md` for full design, contracts and evidence.