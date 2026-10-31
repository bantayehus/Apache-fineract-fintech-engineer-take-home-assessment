# Patch notes for GLAccount entity (Fineract 1.15.0)

**File:** `fineract-core/src/main/java/org/apache/fineract/accounting/glaccount/domain/GLAccount.java`

## Changes required

1. Add field:
```java
@Column(name = "external_reference", length = 100, unique = true)
private String externalReference;
```

2. Update the `@Table` uniqueConstraints if desired (DB constraint is authoritative via Liquibase).

3. In the static factory / create method (or the place where a new GLAccount is instantiated from JsonCommand), accept and set `externalReference`.

4. Expose getter/setter (Lombok already present in 1.15.0 via `@Getter` / `@Setter`).

5. In `update(JsonCommand)` method, optionally support changing the reference only when null → non-null (or treat as immutable after create – recommended for assessment).

## Recommended create snippet (inside existing factory)

```java
public static GLAccount fromJson(final JsonCommand command, final GLAccount parent, final CodeValue tag) {
    // ... existing extraction of name, glCode, type, usage, etc. ...

    final String externalReference = command.stringValueOfParameterNamed("externalReference"); // or external_reference

    return new GLAccount()
            .setName(name)
            .setGlCode(glCode)
            // ... other fields ...
            .setExternalReference(externalReference);
}
```

The unique constraint on the column guarantees that a second insert with the same external_reference will fail at the database level; the write service (next file) translates that into the required 409 / idempotent behaviour.