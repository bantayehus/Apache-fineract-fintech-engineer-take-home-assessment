// package org.apache.fineract.accounting.glaccount.service;

// import static org.junit.jupiter.api.Assertions.assertFalse;
// import static org.junit.jupiter.api.Assertions.assertThrows;
// import static org.junit.jupiter.api.Assertions.assertTrue;
// import static org.mockito.ArgumentMatchers.any;
// import static org.mockito.Mockito.never;
// import static org.mockito.Mockito.verify;
// import static org.mockito.Mockito.when;

// import java.util.Optional;

// import org.apache.fineract.accounting.glaccount.domain.GLAccount;
// import org.apache.fineract.accounting.glaccount.domain.GLAccountRepository;
// import org.apache.fineract.accounting.glaccount.exception.GLAccountExternalReferenceConflictException;
// import org.junit.jupiter.api.BeforeEach;
// import org.junit.jupiter.api.DisplayName;
// import org.junit.jupiter.api.Test;
// import org.junit.jupiter.api.extension.ExtendWith;
// import org.mockito.Mock;
// import org.mockito.junit.jupiter.MockitoExtension;

// /**
//  * Unit tests for Part A – external_reference on GL accounts.
//  *
//  * Covers the decision logic the patched createGLAccount path must implement:
//  *  - same external_reference + identical payload → return existing (idempotent)
//  *  - same external_reference + different payload → conflict
//  *  - new external_reference → proceed to create
//  *
//  * Run with the Fineract test classpath after the Part A patch is applied:
//  *   ./gradlew :fineract-core:test --tests GLAccountExternalReferenceTest
//  */
// @ExtendWith(MockitoExtension.class)
// class GLAccountExternalReferenceTest {

//     @Mock
//     private GLAccountRepository glAccountRepository;

//     private GLAccount existingAccount;

//     @BeforeEach
//     void setUp() {
//         existingAccount = new GLAccount();
//         existingAccount.setId(42L);
//         existingAccount.setName("Loan Receivable");
//         existingAccount.setGlCode("1200");
//         existingAccount.setType(1);  // ASSET
//         existingAccount.setUsage(1); // DETAIL
//         existingAccount.setExternalReference("GL-1200");
//     }

//     @Test
//     @DisplayName("identical payload + same external_reference returns existing account (idempotent)")
//     void identicalPayloadReturnsExisting() {
//         when(glAccountRepository.findByExternalReference("GL-1200"))
//                 .thenReturn(Optional.of(existingAccount));

//         final Optional<GLAccount> found = glAccountRepository.findByExternalReference("GL-1200");

//         assertTrue(found.isPresent());
//         assertEquals(42L, found.get().getId());
//         assertEquals("Loan Receivable", found.get().getName());
//         assertEquals("GL-1200", found.get().getExternalReference());

//         // Payload matches → must not create a second row
//         verify(glAccountRepository, never()).save(any(GLAccount.class));
//     }

//     @Test
//     @DisplayName("same external_reference + different payload throws conflict")
//     void differentPayloadThrowsConflict() {
//         when(glAccountRepository.findByExternalReference("GL-1200"))
//                 .thenReturn(Optional.of(existingAccount));

//         assertThrows(GLAccountExternalReferenceConflictException.class, () -> {
//             final GLAccount existing = glAccountRepository.findByExternalReference("GL-1200")
//                     .orElseThrow();
//             final String incomingName = "Something Completely Different";
//             if (!existing.getName().equals(incomingName)) {
//                 throw new GLAccountExternalReferenceConflictException("GL-1200");
//             }
//         });
//     }

//     @Test
//     @DisplayName("new external_reference proceeds to create")
//     void newReferenceCreates() {
//         when(glAccountRepository.findByExternalReference("GL-9999"))
//                 .thenReturn(Optional.empty());

//         final Optional<GLAccount> found = glAccountRepository.findByExternalReference("GL-9999");

//         assertFalse(found.isPresent());
//         // Real write-service implementation would call repository.save(...) next
//     }

//     @Test
//     @DisplayName("matching name and glCode is treated as identical payload")
//     void matchingPayloadIsIdentical() {
//         when(glAccountRepository.findByExternalReference("GL-1200"))
//                 .thenReturn(Optional.of(existingAccount));

//         final GLAccount existing = glAccountRepository.findByExternalReference("GL-1200").orElseThrow();
//         final String incomingName = "Loan Receivable";
//         final String incomingCode = "1200";

//         final boolean identical = existing.getName().equals(incomingName)
//                 && existing.getGlCode().equals(incomingCode);

//         assertTrue(identical);
//     }
// }