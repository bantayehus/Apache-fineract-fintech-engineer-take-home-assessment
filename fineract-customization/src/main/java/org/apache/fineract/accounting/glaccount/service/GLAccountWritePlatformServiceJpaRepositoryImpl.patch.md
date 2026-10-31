# Patch for GLAccountWritePlatformServiceJpaRepositoryImpl (Part A behaviours)

**Target file (1.15.0):**  
`fineract-accounting/src/main/java/org/apache/fineract/accounting/glaccount/service/GLAccountWritePlatformServiceJpaRepositoryImpl.java`  
(or the equivalent location under fineract-provider / fineract-core depending on exact module layout of the pinned tag)

## Required behaviour (enforced inside Fineract)

1. Persist `external_reference` on the GL account (unique).
2. Same external_reference + **identical** payload → return the existing account (idempotent create).
3. Same external_reference + **different** payload → throw conflict (409).
4. Permission model remains the existing `CREATE_GLACCOUNT` (or whatever the platform uses).
5. Schema change via Liquibase (already provided).

## Recommended implementation approach

Inside the `createGLAccount(JsonCommand command)` method (or the private helper that does the actual persist):

```java
// 1. Extract external reference early
final String externalReference = command.stringValueOfParameterNamedAllowingNull("externalReference");
// also accept "external_reference" for flexibility with the Integration Service payload

if (StringUtils.isNotBlank(externalReference)) {
    final Optional<GLAccount> existingOpt = this.glAccountRepository.findByExternalReference(externalReference);

    if (existingOpt.isPresent()) {
        final GLAccount existing = existingOpt.get();

        // Compare the fields that constitute the "payload" for identity
        final boolean identical =
                Objects.equals(existing.getName(), command.stringValueOfParameterNamed("name"))
                && Objects.equals(existing.getGlCode(), command.stringValueOfParameterNamed("glCode"))
                && Objects.equals(existing.getType(), command.integerValueSansLocaleOfParameterNamed("type"))
                && Objects.equals(existing.getUsage(), command.integerValueSansLocaleOfParameterNamed("usage"))
                // add any other fields you consider part of the identity
                ;

        if (identical) {
            // Idempotent success – return the existing resource
            return new CommandProcessingResultBuilder()
                    .withCommandId(command.commandId())
                    .withEntityId(existing.getId())
                    .withResourceIdAsString(existing.getId().toString())
                    .build();
        } else {
            throw new GLAccountExternalReferenceConflictException(externalReference);
        }
    }
}

// 2. Proceed with normal creation (existing code path)
//    Make sure the new GLAccount instance receives setExternalReference(externalReference)

// 3. On DataIntegrityViolationException that mentions the unique constraint,
//    re-throw as the conflict exception for a clean API response.
```

## Repository addition

Add to `GLAccountRepository` (Spring Data):

```java
Optional<GLAccount> findByExternalReference(String externalReference);
```

## Permission

No change required – the existing `@CommandType(entity = "GLACCOUNT", action = "CREATE")` (or the permission check already present in the command handler) continues to protect the endpoint.

## Why this design

- All consistency rules live inside Fineract’s transaction boundary.
- The unique DB constraint is the last line of defence against races.
- Application-level check gives the clean “identical → 200 existing / different → 409” semantics required by the assessment.
- Dead code is avoided; the path is exercised by the unit + integration tests supplied in this package.