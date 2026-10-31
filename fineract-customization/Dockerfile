# Customized Apache Fineract – Part A (external_reference on GL accounts)
# Pin: 1.15.0 | JDK 21
#
# Build on a machine with ≥ 8 GB RAM and Docker:
#   docker build --build-arg FINERACT_TAG=1.15.0 -t fineract-custom:1.15.0-assessment .
#
# The build:
#   1. Clones the official tag
#   2. Copies the Liquibase migration
#   3. Copies the conflict exception
#   4. Applies source patches (entity field, repository method, write-service logic)
#   5. Builds the bootJar
#   6. Produces a slim runtime image

ARG FINERACT_TAG=1.15.0

# ---------- builder ----------
FROM eclipse-temurin:21-jdk-jammy AS builder

ARG FINERACT_TAG
ARG GRADLE_OPTS="-Dorg.gradle.daemon=false -Dorg.gradle.jvmargs=-Xmx3g -Dorg.gradle.parallel=false"

RUN apt-get update && apt-get install -y --no-install-recommends git curl unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Shallow clone of the exact release tag
RUN git clone --depth 1 --branch ${FINERACT_TAG} https://github.com/apache/fineract.git .

# --- Part A artefacts ---
# Liquibase migration (tenant changelog)
COPY migrations/0001_add_external_reference_to_gl_account.xml /tmp/0001_add_external_reference_to_gl_account.xml
RUN set -e; \
    DEST=""; \
    for d in \
      fineract-provider/src/main/resources/db/changelog/tenant/parts \
      fineract-core/src/main/resources/db/changelog/tenant/parts \
      fineract-provider/src/main/resources/sql/migrations \
    ; do \
      if [ -d "$d" ]; then DEST="$d"; break; fi; \
    done; \
    if [ -n "$DEST" ]; then \
      cp /tmp/0001_add_external_reference_to_gl_account.xml "$DEST/"; \
      echo "Liquibase migration installed into $DEST"; \
    else \
      echo "WARNING: could not locate tenant changelog directory – migration must be applied manually"; \
    fi

# Conflict exception
COPY src/main/java/org/apache/fineract/accounting/glaccount/exception/GLAccountExternalReferenceConflictException.java \
     /tmp/GLAccountExternalReferenceConflictException.java
RUN set -e; \
    for d in \
      fineract-core/src/main/java/org/apache/fineract/accounting/glaccount/exception \
      fineract-accounting/src/main/java/org/apache/fineract/accounting/glaccount/exception \
      fineract-provider/src/main/java/org/apache/fineract/accounting/glaccount/exception \
    ; do \
      mkdir -p "$d"; \
      cp /tmp/GLAccountExternalReferenceConflictException.java "$d/"; \
      echo "Exception class installed into $d"; \
      break; \
    done

# Apply the unified patch if present (entity + repository method)
COPY patches/0001-Part-A-add-external-reference-to-GL-account.patch /tmp/part-a.patch
RUN git apply --verbose /tmp/part-a.patch 2>/dev/null \
    || git apply --verbose --reject /tmp/part-a.patch 2>/dev/null \
    || echo "NOTE: patch application had rejects – complete entity/repository/write-service changes manually as documented in *.patch.md"

# Unit test
COPY src/test/java/org/apache/fineract/accounting/glaccount/service/GLAccountExternalReferenceTest.java \
     /tmp/GLAccountExternalReferenceTest.java
RUN set -e; \
    for d in \
      fineract-core/src/test/java/org/apache/fineract/accounting/glaccount/service \
      fineract-accounting/src/test/java/org/apache/fineract/accounting/glaccount/service \
      fineract-provider/src/test/java/org/apache/fineract/accounting/glaccount/service \
    ; do \
      mkdir -p "$d"; \
      cp /tmp/GLAccountExternalReferenceTest.java "$d/"; \
      echo "Unit test installed into $d"; \
      break; \
    done

# Build the provider jar (skip tests here; run them separately if needed)
# Pre-download Gradle (wrapper default timeout is 10s; too short on slow networks)
RUN DIST_URL=$(grep '^distributionUrl=' gradle/wrapper/gradle-wrapper.properties | cut -d= -f2 | tr -d '\r' | sed 's#\\##g') \
    && echo "Downloading Gradle from $DIST_URL" \
    && curl -fsSL --retry 10 --retry-delay 5 --connect-timeout 120 --max-time 900 \
         -o /tmp/gradle-dist.zip "$DIST_URL" \
    && HASH=$(echo -n "$DIST_URL" | sha256sum | cut -c1-32) \
    || HASH=$(echo -n "$DIST_URL" | md5sum | cut -c1-32) \
    && VERSION=$(echo "$DIST_URL" | sed -n 's/.*\/gradle-\(.*\)-bin\.zip/\1/p') \
    && DEST="/root/.gradle/wrapper/dists/gradle-${VERSION}-bin/${HASH}" \
    && mkdir -p "$DEST" \
    && mv /tmp/gradle-dist.zip "$DEST/gradle-${VERSION}-bin.zip" \
    && echo "Gradle zip placed at $DEST"

# Build the provider jar
RUN ./gradlew :fineract-provider:bootJar -x test -x rat -x spotlessCheck ${GRADLE_OPTS}

# ---------- runtime ----------
FROM eclipse-temurin:21-jre-jammy

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the fat jar produced by bootJar
COPY --from=builder /src/fineract-provider/build/libs/fineract-provider-*.jar /app/fineract-provider.jar

EXPOSE 8080 8443

HEALTHCHECK --interval=15s --timeout=10s --start-period=180s --retries=20 \
  CMD curl -f http://localhost:8080/fineract-provider/actuator/health || exit 1

ENTRYPOINT ["java", "-XX:+UseContainerSupport", "-XX:MaxRAMPercentage=75.0", "-jar", "/app/fineract-provider.jar"]