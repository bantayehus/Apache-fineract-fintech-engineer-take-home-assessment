/**
 * Thrown when an attempt is made to create a GL account with an external_reference
 * that already exists but the payload differs from the existing account.
 *
 * Maps to HTTP 409 Conflict (or Fineract's equivalent PlatformApiDataValidationException /
 * AbstractPlatformDomainRuleException that the API layer turns into 409).
 */
package org.apache.fineract.accounting.glaccount.exception;

import org.apache.fineract.infrastructure.core.exception.AbstractPlatformDomainRuleException;

public class GLAccountExternalReferenceConflictException extends AbstractPlatformDomainRuleException {

    public GLAccountExternalReferenceConflictException(final String externalReference) {
        super("error.msg.glaccount.external.reference.conflict",
                "A GL account with external reference `" + externalReference
                        + "` already exists with a different payload.",
                externalReference);
    }
}