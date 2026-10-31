# Building the customized Fineract image (Part A)

**Pinned version:** Apache Fineract **1.15.0**  
**JDK:** 21  
**Build tool:** Gradle (wrapper included in upstream)

This environment cannot complete a full Fineract build (no Docker daemon, ~1.2 GB RAM).  
Run the steps below on a machine with **≥ 8 GB RAM**, **≥ 15 GB free disk**, and Docker.

---

## Option A – One-command Docker build (recommended)

```bash
cd fintech-fineract-assessment/fineract-customization

# Build (clones 1.15.0, applies Part A changes, produces image)
docker build \
  --build-arg FINERACT_TAG=1.15.0 \
  -t fineract-custom:1.15.0-assessment \
  .

# Verify
docker run --rm fineract-custom:1.15.0-assessment \
  java -jar /app/fineract-provider.jar --version || true
```

Then from the assessment root:

```bash
# Point docker-compose at the image you just built
# (or keep the build: section in docker-compose.yml)
docker compose up -d
./scripts/wait-for-services.sh
./scripts/seed-fineract.sh
```

---

## Option B – Local source patch + build (best for interview live demo)

```bash
# 1. Clone the exact tag
git clone --branch 1.15.0 --depth 1 https://github.com/apache/fineract.git
cd fineract

# 2. Apply the Part A patch
git apply ../fintech-fineract-assessment/fineract-customization/patches/0001-Part-A-add-external-reference-to-GL-account.patch

# 3. Copy the Liquibase migration into the tenant changelog
#    (exact path may be fineract-provider or fineract-core depending on layout)
cp ../fintech-fineract-assessment/fineract-customization/migrations/0001_add_external_reference_to_gl_account.xml \
   fineract-provider/src/main/resources/db/changelog/tenant/parts/ \
   2>/dev/null || \
cp ../fintech-fineract-assessment/fineract-customization/migrations/0001_add_external_reference_to_gl_account.xml \
   fineract-core/src/main/resources/db/changelog/tenant/parts/

# 4. Manually complete the write-service changes described in:
#    fineract-customization/src/main/java/.../GLAccountWritePlatformServiceJpaRepositoryImpl.patch.md
#    (lookup-before-insert + identical-payload short-circuit + conflict exception)

# 5. Copy the unit test
cp ../fintech-fineract-assessment/fineract-customization/src/test/java/org/apache/fineract/accounting/glaccount/service/GLAccountExternalReferenceTest.java \
   fineract-core/src/test/java/org/apache/fineract/accounting/glaccount/service/ \
   2>/dev/null || true

# 6. Build
./gradlew :fineract-provider:bootJar -x test

# 7. Run unit tests for Part A
./gradlew :fineract-core:test --tests GLAccountExternalReferenceTest

# 8. Build a Docker image from the jar (or use the upstream Dockerfile with your jar)
```

---

## Option C – Official image for baseline only (does NOT satisfy Part A)

```bash
docker pull apache/fineract:1.15.0   # or :latest if 1.15.0 tag is not published as such
```

Use this only to validate the Python services against an unmodified Fineract.  
The assessment requires a **real change inside Fineract** (Liquibase + command-handler behaviour), so the final submission must use the custom image from Option A or B.

---

## What the customisation must demonstrate (evidence)

After the custom image is running with a clean DB:

```bash
# 1. Create GL account with external_reference
curl -u mifos:password -H "Fineract-Platform-TenantId: default" \
  -H "Content-Type: application/json" \
  -d '{"name":"Loan Receivable","glCode":"1200","type":1,"usage":1,"manualEntriesAllowed":true,"externalReference":"GL-1200"}' \
  http://localhost:8080/fineract-provider/api/v1/glaccounts

# 2. Identical payload again → same resourceId (idempotent)
# 3. Same externalReference, different name → 409 Conflict
# 4. Unauthenticated call → 401 / permission error
```

Capture the responses in `evidence/java-part-a/`.

---

## Resource notes

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 4 GB | 8 GB+ |
| Disk | 10 GB free | 20 GB free |
| Time (first build) | ~10–25 min | depends on network & CPU |

If the Docker build runs out of memory, add to the `docker build` command:

```bash
--build-arg GRADLE_OPTS="-Dorg.gradle.daemon=false -Dorg.gradle.jvmargs=-Xmx3g"
```

and ensure Docker Desktop / the daemon has at least 4–6 GB allocated.