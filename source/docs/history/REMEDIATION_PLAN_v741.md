# Build 741 native Windows archive sync remediation

Fix native Windows re-inventory metadata backup finalization: finish the ZIP, flush and fsync the writable stream, close it, then atomically publish it. A durability failure still prevents inventory replacement and preserves prior metadata. Build Process v169 and database masters unchanged.

Retain the four-pass inventory regression and add deterministic Windows-like descriptor and failed-sync tests. Preserve mandatory native acceptance. Previous review remediation is retained in the archived Build 740 plan.
